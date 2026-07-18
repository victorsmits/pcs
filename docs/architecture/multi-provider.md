# Architecture multi-provider CycloStats

## Objectif
CycloStats devient un monolithe Django modulaire dont les vues lisent uniquement les données locales PostgreSQL/Redis. Les fournisseurs externes ne sont appelés que par des workers d'ingestion asynchrones, avec provenance et santé explicites.

## Limites applicatives cibles
- `catalog` : domaine canonique froid/tiède (séries, éditions legacy `Race`, étapes, coureurs, équipes, startlists, résultats, profils, points clés).
- `providers` : registre des fournisseurs, capacités, santé, clients HTTP autorisés, mappings externes.
- `ingestion` : DTO normalisés, validation, résolution d'identité, fusion, conflits, snapshots et tâches Celery.
- `live` : état live local, snapshots, groupes, timeline canonique, notifications découplées.
- `api` : endpoints versionnés provider-agnostic.
- `core` : configuration, cache, observabilité et utilitaires sans dépendance fournisseur.

## Flux d'ingestion
Un provider produit des DTO normalisés. L'orchestrateur vérifie ses capacités, applique verrous et rate limits, stocke un `SourceSnapshot`, valide un `NormalizedImport`, résout l'identité canonique, fusionne selon une politique de champ et crée la provenance ou un conflit. Les vues et serializers ne déclenchent jamais ce flux.

## Provenance et conflits
Chaque identifiant externe sera conservé dans un mapping provider. Chaque valeur acceptée recevra une provenance de champ. En cas d'écart non sûr, la donnée est conservée comme conflit plutôt que remplacée silencieusement.

## Live et notifications
Le live cible conserve sessions, snapshots, groupes, positions et événements canoniques. Les notifications suivent la chaîne `RaceEvent -> NotificationRule -> NotificationCandidate -> NotificationDelivery -> Web Push`, avec une clé de déduplication persistée par abonnement et événement.

## PCS legacy
Le scraping PCS est désactivé par défaut via `PCS_LEGACY_ENABLED=False`. Le provider futur `legacy-pcs` servira uniquement à préserver les mappings historiques, pas à contacter PCS au runtime normal.

## Ajout d'un provider
1. Documenter la source et ses conditions dans `docs/providers/{key}.md`.
2. Déclarer ses capacités et quotas.
3. Implémenter un adaptateur DTO sans modèles Django.
4. Ajouter fixtures hors ligne et tests de contrat.
5. Activer explicitement le provider via configuration après validation.
