# Fixtures PCS (captures réelles)

Capturées le 2026-06-20 via `curl_cffi` (impersonate chrome) — Cloudflare passe sans souci depuis le serveur.
Source : Tour of Slovenia 2026 (étape 4 en direct, étape 3 terminée), + pages génériques.

## Fichiers

| Fichier | Contenu | Usage test |
|---|---|---|
| `home.html` | Page d'accueil (LiveStats, résultats du jour, prochaines courses, classements) | parser home / détection courses du jour |
| `calendar_2026_wt.html` | `races.php?year=2026&circuit=1` (WorldTour) | parser calendrier → liste Race |
| `race_overview.html` | `/race/tour-of-slovenia/2026` | parser course + liste étapes |
| `stage_results.html` | Étape 4 (en cours, table partielle) | parser résultats (cas live/partiel) |
| `stage_results_finished.html` | Étape 3 (terminée, **113 lignes**) | parser résultats complets + bloc Race information (Vertical meters, ProfileScore…) |
| `stage_live.html` | Page **live** étape 4 | bootstrap `var data`, timeline, situation, **profil polygon (795 pts)** |
| `rider.html` | `/rider/tadej-pogacar` | parser coureur |
| `team.html` | `/team/uae-team-emirates-xrg-2026` | parser équipe |

> `live_feed.json` (`/cache_excf/livestats{id}_gb.json`) **non capturable hors navigateur** : renvoie du HTML
> (gated par contexte browser/Cloudflare) même avec Referer. Voir constat live ci-dessous.

## Constat clé pour le moteur live

- Le bootstrap `var data = {…}` est **embarqué dans `stage_live.html`** et reflète l'**état courant** au moment du fetch
  (ex. `kmdone: 18.875`, `race_status: "racing"`), pas seulement l'état initial.
- `stage_live.html` est **récupérable via curl_cffi** (200). La page contient TOUT :
  - `var data` : 59 clés (`race_status`, `kmdone/kmtogo/maxkm`, `avg_speed`, `min_ele/max_ele`,
    `keypoints` (10), `sl_riders` (118), `ls_pid`, `finished`, …).
  - `ul.timeline*` : événements (34 `<li>`), HTML pré-rendu.
  - bloc `situ*` : situation (groupes/échappée/peloton + écarts).
  - `clip-path: polygon(...)` : **profil d'altitude (795 points)** → régénération SVG.
- Le flux incrémental `/cache_excf/livestats{ls_pid}_gb.json` (polling JS 15 s) renvoie
  `{ "updates": [ {type:"timeline", seqnr, html}, {type:"nr_online", nr_online}, {type:"timeline_x", tid}, … ] }`.
  Pratique mais **browser-gated** → secondaire.

### Décision d'implémentation (affine le plan)
**Stratégie live PRIMAIRE = poller `stage_live.html` toutes les ~15 s via curl_cffi et ré-extraire
`var data` + timeline + situation + polygon.** Robuste, éprouvé, sans dépendance au JSON non documenté.
Le flux `cache_excf` reste une optimisation future (nécessiterait de répliquer cookies/headers navigateur).
