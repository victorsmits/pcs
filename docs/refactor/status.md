# Statut refonte multi-provider

## Lot en cours
Lot 0 — Audit et garde-fou.

## Inventaire fonctionnel actuel
- Catalogue : calendrier, pages course/étape/coureur/équipe, classements PCS/UCI/team, startlists, résultats, historique d'éditions.
- Profil : images de profil, points d'altitude JSON, min/max altitude, cols et sprints, SVG local.
- Live : sessions par étape, km faits/restants, vitesse moyenne, groupes, écarts, position de tête et estimation de groupe à partir de l'écart/vitesse, timeline `LiveEvent`.
- Notifications : abonnements Web Push anonymes, suivi d'une course, rappel, départ, arrivée, événements live, nettoyage abonnements expirés.

## Dépendances PCS identifiées
- `core/pcs_client.py` et `core/pcs_circuit.py`.
- Services catalogue : calendrier, détails course/étape, résultats, classements, startlist, coureurs, équipes, profils.
- Services live et tâches Celery : découverte et polling PCS.
- Vues catalogue/API live : refresh à la demande, recherche distante PCS, backfill paresseux.
- Champs legacy : `Rider.pcs_id`, `Team.pcs_id`, `Race.pcs_id`, `LiveSession.pcs_live_id`, `Result.points_pcs`.

## Données à migrer ultérieurement
- Identifiants PCS vers mappings `legacy-pcs`.
- Courses `Race` vers séries/éditions.
- Teams vers identités/saisons.
- LiveEvent vers RaceEvent + observations provider.
- Flags de notification vers livraisons dédupliquées.

## Fichiers modifiés
- `pcs_project/settings.py`
- `core/pcs_client.py`
- `live/tasks.py`
- `live/api.py`
- `catalog/views.py`
- `catalog/search.py`
- `docs/architecture/multi-provider.md`
- `docs/refactor/status.md`
- `tests/test_no_provider_network_in_views.py`

## Migrations créées
Aucune au Lot 0.

## Tests ajoutés
- `tests/test_no_provider_network_in_views.py` : garde-fou empêchant les vues/API/search d'appeler le client PCS en configuration normale.

## Décisions prises
- Kill switch `PCS_LEGACY_ENABLED=False` par défaut.
- Les vues ne déclenchent plus de synchronisation ou backfill provider ; elles affichent la donnée locale existante.
- Les tâches PCS retournent un résultat idempotent `pcs_legacy_disabled` tant que le kill switch est désactivé.

## Limitations
- Lot 0 ne crée pas encore les nouveaux modèles multi-provider ni les migrations legacy.
- Le code de parsing PCS reste présent pour compatibilité transitoire, mais non appelé par le runtime web normal.

## Commandes exécutées
- `python -m py_compile catalog/views.py catalog/search.py live/tasks.py live/api.py core/pcs_client.py` : OK.
- `ruff check .` : OK.
- `python manage.py check` : OK.
- `python manage.py makemigrations --check` : OK, aucune migration non créée.
- `pytest -q` : OK, 5 passed, 9 warnings de dépréciation Django/Python sans échec.

## Éléments restant à traiter
- Lot 1 : introduire le domaine canonique additif (`RaceSeries`, alias, UUID publics, `TeamIdentity`, champs d'étapes/résultats) et tests de migration.
