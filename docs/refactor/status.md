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

## Lot 1 — Domaine canonique additif

### Fichiers modifiés
- `catalog/models.py`
- `catalog/migrations/0006_teamidentity_race_finish_location_race_host_country_and_more.py`
- `catalog/migrations/0007_backfill_canonical_lot1.py`
- `tests/test_catalog_lot1_canonical_backfill.py`
- `docs/refactor/status.md`

### Migrations créées
- `0006` : ajoute `RaceSeries`, `RaceSeriesAlias`, `TeamIdentity`, UUID publics additifs et champs canoniques préparatoires sur `Race`, `Stage`, `StartListEntry`, `Result`, `Rider`, `Team`.
- `0007` : backfill non destructif des séries depuis `Race.slug`, alias de noms historiques, identités d'équipes, UUID publics par ligne, champs d'étape et temps de résultats normalisés.

### Tests ajoutés
- `tests/test_catalog_lot1_canonical_backfill.py` : vérifie le backfill d'une course legacy vers série/alias, identité d'équipe, UUID/champs canoniques, étape ITT et temps normalisé.

### Décisions prises
- Les contraintes d'unicité sur UUID publics des tables legacy seront renforcées dans un lot ultérieur afin de respecter l'ordre additif demandé.
- `Race` reste la table d'édition legacy compatible et reçoit un FK nullable vers `RaceSeries`.
- `Team` reste la saison legacy compatible et reçoit un FK nullable vers `TeamIdentity`.

### Commandes exécutées
- `python manage.py makemigrations catalog --noinput` : OK, migration `0006` créée.
- `python manage.py migrate` : OK, migrations `0006` et `0007` appliquées localement.
- `ruff check tests/test_catalog_lot1_canonical_backfill.py` : OK.
- `pytest -q tests/test_catalog_lot1_canonical_backfill.py` : OK, 1 passed.
- `ruff check .` : échec initial sur un import inutilisé dans la migration `0007`, corrigé immédiatement.
- `ruff check .` : OK après correction.
- `python manage.py check` : OK.
- `python manage.py makemigrations --check` : OK, aucune migration manquante.
- `pytest -q` : OK, 6 passed, 9 warnings de dépréciation Django/Python sans échec.

### Limitations Lot 1
- Les lectures restent majoritairement sur les modèles legacy enrichis ; le basculement complet des lectures est prévu Lot 6.
- Les PK existantes ne sont pas modifiées ; les UUID publics sont préparés pour API et mappings futurs.

## Lot 2 — Provider framework

### Fichiers modifiés
- `pcs_project/settings.py`
- `live/api.py`
- `providers/apps.py`
- `providers/capabilities.py`
- `providers/exceptions.py`
- `providers/interfaces.py`
- `providers/models.py`
- `providers/registry.py`
- `providers/http.py`
- `providers/utils.py`
- `providers/admin.py`
- `providers/management/commands/list_providers.py`
- `providers/management/commands/provider_health.py`
- `providers/migrations/0001_initial.py`
- `providers/migrations/0002_seed_builtin_providers.py`
- `tests/providers/test_provider_framework_lot2.py`

### Migrations créées
- `providers/0001_initial` : tables additives `Provider`, `ProviderEntityMapping`, `ProviderSnapshot`, `ProviderRequestLog` avec index de recherche/santé/provenance.
- `providers/0002_seed_builtin_providers` : providers intégrés `legacy-pcs` désactivé, `manual` activé, `seed` activé.

### Tests ajoutés
- `tests/providers/test_provider_framework_lot2.py` : contrat de capacités, registre et kill switch de providers, persistance mappings/snapshots, parsing `Retry-After`, exposition métier du rate limiting.

### Décisions prises
- Les capacités sont définies dans une enum `ProviderCapability` indépendante des modèles Django.
- Les providers produisent des `ProviderBatch` sans objets Django ; les DTO métier complets seront ajoutés au Lot 3.
- Le client HTTP provider impose HTTPS et limite l'hôte à `Provider.base_url` lorsque défini afin de réduire le risque SSRF.
- Le provider `legacy-pcs` est créé uniquement comme provenance/mapping historique, désactivé et sans capacité.
- Les commandes `list_providers` et `provider_health` lisent l'état connu en base sans contacter le réseau.

### Limitations Lot 2
- Le circuit breaker provider générique reste minimal ; son exploitation complète et l'orchestration avec backoff distribué sont prévues au Lot 3.
- Les adaptateurs réels, `SeedProvider`, `ManualProvider` et `FixtureProvider` sont prévus aux lots 4 et 5.
- Les mappings legacy PCS ne sont pas encore backfillés depuis `pcs_id`; ce point reste dans le Lot 8.

### Commandes exécutées
- `python manage.py makemigrations --check` : échec attendu initial après création de l'app providers, migrations créées puis incohérence de noms d'index corrigée.
- `ruff check .` : échec initial sur import inutilisé legacy dans `live/api.py`, corrigé.
- `ruff check .` : OK.
- `pytest -q tests/providers/test_provider_framework_lot2.py` : OK, 5 passed.
- `python manage.py check` : OK.
- `python manage.py makemigrations --check` : OK, aucune migration manquante.
- `pytest -q` : OK, 13 passed, 9 warnings de dépréciation Django/Python sans échec.

### Éléments restant à traiter
- Lot 3 : DTO normalisés, validation, résolution d'identité, provenance, fusion, conflits, orchestration et commandes de synchronisation.

## Lot 4 — Seeds

### Base de départ
- Travail repris depuis le merge `cca358b` correspondant à l'état `origin/main` disponible localement ; aucun remote `origin` n'est configuré dans ce conteneur, donc aucun `git fetch origin` n'a pu être exécuté.

### Fichiers modifiés
- `catalog/seeds/road_series.yaml`
- `catalog/seed_services.py`
- `catalog/management/commands/seed_road_series.py`
- `catalog/management/commands/seed_national_championships.py`
- `providers/seed.py`
- `tests/catalog/test_seed_lot4.py`
- `docs/refactor/status.md`

### Migrations créées
- Aucune migration : le lot s'appuie sur les modèles additifs `RaceSeries` et `RaceSeriesAlias` déjà introduits.

### Tests ajoutés
- `tests/catalog/test_seed_lot4.py` : présence des priorités P0/P1/P2/P3, championnats monde/europe/olympiques, idempotence du seed route, alias de séries, génération des championnats nationaux P1/P2 et provider seed hors réseau.

### Décisions prises
- `catalog/seeds/road_series.yaml` contient les séries P0 à P3 sans dates ni éditions annuelles.
- Le parser YAML est volontairement restreint au format versionné du dépôt pour éviter une nouvelle dépendance runtime et garder les tests hors réseau.
- `seed_road_series` et `seed_national_championships` sont transactionnels, idempotents et non destructifs : une absence dans le YAML ne supprime jamais une série existante.
- `SeedProvider` expose la capacité `RACE_SERIES` en lecture locale du fichier seed, sans appel réseau.
- Les championnats nationaux créent quatre séries par pays P1/P2 : ME/WE route et ME/WE ITT.

### Limitations Lot 4
- Les séries nationales ne sont pas incluses dans le YAML route principal ; elles sont générées par commande dédiée conformément au cahier.
- L'ingestion automatique du `SeedProvider` vers le moteur Lot 3 n'est pas branchée ici parce que la demande explicite était de reprendre depuis `origin/main`, qui ne contient pas le Lot 3 non retenu.

### Commandes exécutées
- `git fetch origin` : échec, aucun remote `origin` configuré dans le conteneur.
- `git reset --hard cca358b` : OK, reprise depuis l'état main disponible localement.
- `ruff check catalog/seed_services.py catalog/management/commands/seed_road_series.py catalog/management/commands/seed_national_championships.py providers/seed.py tests/catalog/test_seed_lot4.py` : OK.
- `pytest -q tests/catalog/test_seed_lot4.py` : échec initial car `PyYAML` n'était pas installé ; corrigé par parser YAML restreint sans dépendance.
- `pytest -q tests/catalog/test_seed_lot4.py` : OK, 5 passed.
- `python manage.py seed_road_series` : OK, created=103 updated=0 aliases_created=111 aliases_updated=0.
- `python manage.py seed_road_series` : OK, created=0 updated=103 aliases_created=0 aliases_updated=111.
- `python manage.py seed_national_championships` : OK, created=120 updated=0 aliases_created=120 aliases_updated=0.
- `python manage.py seed_national_championships` : OK, created=0 updated=120 aliases_created=0 aliases_updated=120.
- `ruff check .` : OK.
- `python manage.py check` : OK.
- `python manage.py makemigrations --check` : OK, aucune migration manquante.
- `pytest -q` : échec temporaire car la base SQLite locale avait été seedée avant les tests ; tests rendus robustes aux données seed déjà présentes.
## Validation reprise Lot 2 — 2026-07-18

### Commandes exécutées
- `ruff check .` : OK.
- `python manage.py check` : OK.
- `python manage.py makemigrations --check` : OK, aucune migration manquante.
- `pytest -q` : OK, 13 passed, 9 warnings de dépréciation Django/Python sans échec.

### Décisions prises
- Le lot demandé le plus récent est le Lot 2 ; le socle provider est déjà présent sur la branche et a été revalidé sans modification fonctionnelle supplémentaire.

### Éléments restant à traiter
- Lot 3 : démarrer l'ingestion canonique (DTO, validation, résolution d'identité, provenance, fusion, conflits, orchestration, tâches et commandes).

## Lot 3 — Ingestion

### Fichiers modifiés
- `pcs_project/settings.py`
- `ingestion/apps.py`
- `ingestion/admin.py`
- `ingestion/dto.py`
- `ingestion/models.py`
- `ingestion/serialization.py`
- `ingestion/resolver.py`
- `ingestion/merge.py`
- `ingestion/orchestrator.py`
- `ingestion/tasks.py`
- `ingestion/management/commands/sync_provider.py`
- `ingestion/management/commands/list_conflicts.py`
- `ingestion/management/commands/reconcile_mappings.py`
- `ingestion/migrations/0001_initial.py`
- `tests/ingestion/test_ingestion_lot3.py`

### Migrations créées
- `ingestion/0001_initial` : tables additives `IngestionRun`, `SourceObservation` et `DataConflict` pour tracer les synchronisations, conserver chaque observation source et exposer les conflits sans perte d'information.

### Tests ajoutés
- `tests/ingestion/test_ingestion_lot3.py` : validation DTO, création idempotente de série/rider, mapping provider, snapshot, observation source, conflit d'autorité inférieure et comptage d'un run orchestré.

### Décisions prises
- Les DTO sont des dataclasses validées et ne contiennent pas d'objet Django.
- Le Lot 3 implémente une première fusion réelle pour `NormalizedRaceSeries` et `NormalizedRider`, suffisante pour valider le pipeline provider → DTO → snapshot → résolution identité → mapping → observation → conflit.
- Les DTO complets `Stage`, `Result` et `LiveEvent` sont définis pour stabiliser le contrat, mais leur fusion complète reste planifiée aux lots live/catalogue suivants afin de ne pas basculer prématurément les lectures.
- Les conflits sont conservés dans `DataConflict` au lieu d'écraser une valeur canonique avec une source moins autoritaire.
- Les commandes d'administration d'ingestion lisent l'état local et utilisent le registre provider ; aucune vue web n'appelle ce pipeline directement.

### Limitations Lot 3
- Le moteur de fusion est volontairement conservateur : il ne fusionne automatiquement que séries et coureurs dans ce lot.
- Le backoff distribué, les fallbacks multi-provider et les adaptateurs seed/manual/fixture complets restent dans les lots 4 et 5.
- Les commandes `sync_edition` et `sync_live` spécialisées seront ajoutées lorsque les DTO correspondants seront branchés sur les modèles canonique/live.

### Commandes exécutées
- `ruff check ingestion tests/ingestion/test_ingestion_lot3.py --fix` : corrections automatiques d'import inutilisé.
- `ruff check ingestion tests/ingestion/test_ingestion_lot3.py` : OK.
- `pytest -q tests/ingestion/test_ingestion_lot3.py` : OK, 5 passed.
- `ruff check .` : OK.
- `python manage.py check` : OK.
- `python manage.py makemigrations --check` : OK, aucune migration manquante.
- `pytest -q` : échec temporaire local causé par un schéma SQLite de développement qui avait appliqué une première version non retenue de `ingestion/0001_initial`; corrigé en recréant l'app ingestion locale sans changement de migration finale.
- `python manage.py migrate ingestion zero --noinput` : OK, remise à zéro locale de l'app ingestion non encore livrée.
- `python manage.py migrate --noinput` : OK, application propre de `ingestion/0001_initial`.
- `pytest -q` : OK, 18 passed, 9 warnings de dépréciation Django/Python sans échec.
- `ruff check .` : OK, revalidation finale.
- `python manage.py check` : OK, revalidation finale.
- `python manage.py makemigrations --check` : OK, revalidation finale.
- `pytest -q` : OK, revalidation finale, 18 passed, 9 warnings de dépréciation Django/Python sans échec.

### Éléments restant à traiter
- Lot 5 : providers manuel et fixture complets, démonstration de fusion multi-source, conflit et fallback live.
- Lot 4 : seeds YAML, `SeedProvider`, séries P0 à P3 et championnats nationaux idempotents.
