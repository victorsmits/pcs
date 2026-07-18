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

## Lot 2 — socle provider implémenté

Le socle provider est désormais isolé dans l'application Django `providers` :

- `Provider` décrit l'état connu, les capacités déclarées, l'autorité, l'attribution, les limites de débit et la santé persistée.
- `ProviderEntityMapping` conserve les identifiants externes séparément du domaine canonique.
- `ProviderSnapshot` conserve les payloads observés, leur hash et leur validité pour rejouer ou auditer une ingestion.
- `ProviderRequestLog` garde une trace d'observabilité par requête autorisée.
- `CyclingProvider` définit le contrat commun et lève `ProviderCapabilityNotSupported` lorsqu'une capacité non déclarée est appelée.
- `ProviderHttpClient` impose HTTPS, vérifie l'hôte attendu, applique un rate limiting minimal et transforme `403`/`429` en exceptions métier sans contournement.

Les providers intégrés seedés sont `seed`, `manual` et `legacy-pcs`. `legacy-pcs` reste désactivé et ne possède aucune capacité de runtime.


## Lot 3 — ingestion canonique implémentée

L'application `ingestion` matérialise le flux provider-agnostic avant toute bascule de lecture :

1. un provider produit des DTO normalisés dataclass (`NormalizedRaceSeries`, `NormalizedRider`, `NormalizedStage`, `NormalizedResult`, `NormalizedLiveEvent`) ;
2. `IngestionOrchestrator` crée un `IngestionRun`, vérifie que le batch contient uniquement des DTO, puis délègue au moteur de fusion ;
3. `MergeEngine` valide le DTO, persiste un `ProviderSnapshot`, résout ou crée l'identité canonique via `IdentityResolver`, met à jour `ProviderEntityMapping` et crée une `SourceObservation` ;
4. si une valeur entrante diffère d'une valeur canonique et n'est pas plus autoritaire, `DataConflict` conserve l'écart au lieu de supprimer ou d'écraser l'information ;
5. les commandes `sync_provider`, `list_conflicts` et `reconcile_mappings` exposent l'administration du pipeline sans accès fournisseur depuis les vues.

La fusion automatique du Lot 3 est limitée aux séries et coureurs pour rester additive. Les DTO étape/résultat/live stabilisent le contrat des lots suivants sans supprimer les flux legacy tant que la parité n'est pas validée.
