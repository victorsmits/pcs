# CycloStats — Refonte complète multi-provider

Tu travailles sur le dépôt GitHub :

```text
victorsmits/pcs
```

Tu dois réaliser une refonte profonde de l’application CycloStats afin de supprimer sa dépendance structurelle à ProCyclingStats et de la transformer en plateforme cycliste route multi-provider, robuste, traçable et extensible.

Tu dois modifier réellement le code, les modèles, les migrations, les tâches, l’administration, les tests, la documentation et le déploiement. Ne produis pas uniquement un plan théorique.

---

# 1. Objectif produit

CycloStats doit devenir une plateforme centrée sur les principales courses cyclistes sur route de chaque saison.

Le système doit agréger plusieurs sources de données sans exposer leur structure interne au reste de l’application.

Il doit prendre en charge :

* les séries de courses récurrentes ;
* les éditions annuelles ;
* les courses d’un jour ;
* les courses par étapes ;
* les étapes et prologues ;
* les parcours et profils ;
* les points clés ;
* les listes de départ ;
* les équipes et coureurs ;
* les résultats ;
* les classements annexes ;
* les abandons et non-partants ;
* les données live lorsque disponibles ;
* les Championnats du monde ;
* les Championnats d’Europe ;
* les Jeux olympiques les années concernées ;
* les championnats nationaux route et contre-la-montre ;
* la provenance et la fraîcheur de chaque donnée.

Le périmètre initial est le cyclisme sur route élite :

```text
ME = Hommes Élite
WE = Femmes Élite
```

L’architecture devra pouvoir accueillir ultérieurement :

* U23 ;
* juniors ;
* cyclo-cross ;
* piste ;
* VTT ;
* gravel ;
* para-cyclisme.

Ne pas implémenter ces disciplines maintenant, mais ne pas verrouiller le modèle exclusivement sur la route.

---

# 2. Contraintes non négociables

## 2.1 Suppression du contournement PCS

Supprimer du runtime :

* `curl_cffi` ;
* `cloudscraper` ;
* toute impersonation de navigateur ;
* toute tentative de contournement Cloudflare ;
* toute rotation de proxy ou d’adresse IP ;
* toute reconstruction de session destinée à contourner un blocage ;
* les commentaires ou noms de fonctions parlant de « bypass ».

Aucune source ne doit être interrogée en contournant un contrôle d’accès.

Supprimer ces dépendances de `requirements.txt` dès qu’elles ne sont plus nécessaires.

## 2.2 Aucun accès fournisseur depuis une requête web

Une vue Django, une API, un serializer, un template ou une recherche utilisateur ne doit jamais effectuer directement une requête HTTP vers un fournisseur.

Le chemin obligatoire est :

```text
Fournisseur externe
        ↓
Worker d’ingestion
        ↓
Validation et normalisation
        ↓
Fusion dans le domaine canonique
        ↓
PostgreSQL / Redis
        ↓
API et vues en lecture locale
```

Le site doit continuer à fonctionner lorsque tous les fournisseurs sont désactivés ou indisponibles.

## 2.3 Pas d’identifiant fournisseur dans le domaine canonique

Supprimer progressivement du domaine les champs comme :

```text
pcs_id
pcs_live_id
points_pcs
```

Les identifiants externes doivent être conservés uniquement dans des tables de correspondance provider.

Un slug provenant d’un fournisseur ne doit jamais constituer l’identité canonique d’une entité.

## 2.4 Pas de source unique obligatoire

Chaque fonction métier doit fonctionner avec :

* zéro provider actif, en lecture locale ;
* un seul provider ;
* plusieurs providers concurrents ;
* des providers couvrant seulement certaines capacités ;
* un provider temporairement indisponible.

## 2.5 Préservation des données existantes

La migration doit être non destructive.

Avant de supprimer ou renommer un champ :

1. introduire le nouveau modèle ;
2. migrer les données existantes ;
3. vérifier les contraintes ;
4. basculer les lectures et écritures ;
5. conserver temporairement une couche de compatibilité ;
6. supprimer le legacy dans une migration ultérieure.

Ne jamais vider les tables pour simplifier la migration.

---

# 3. Architecture cible

Conserver une architecture de modular monolith Django.

Ne pas créer de microservices.

Créer ou restructurer les applications ainsi :

```text
catalog/
    Domaine canonique
    Coureurs
    Équipes
    Séries
    Éditions
    Étapes
    Startlists
    Résultats
    Championnats

providers/
    Définition des fournisseurs
    Registre
    Capacités
    Clients HTTP autorisés
    Adaptateurs spécifiques
    Correspondances d’identifiants
    Santé des fournisseurs

ingestion/
    Orchestration
    DTO normalisés
    Validation
    Résolution d’identité
    Fusion
    Provenance
    Conflits
    Synchronisations
    Tâches Celery

live/
    État live canonique
    Groupes
    Événements
    Snapshots
    Notifications

api/
    API publique versionnée
    API d’administration si nécessaire

core/
    Configuration transverse
    Cache
    Observabilité
    Utilitaires indépendants des providers
```

Une variante proche est acceptable si les responsabilités restent clairement séparées.

Créer une décision d’architecture dans :

```text
docs/architecture/multi-provider.md
```

Cette documentation doit expliquer :

* les limites entre applications ;
* le flux d’ingestion ;
* le modèle de provenance ;
* la résolution des conflits ;
* le fonctionnement du live ;
* la procédure d’ajout d’un provider.

---

# 4. Domaine canonique

## 4.1 Séparer série et édition

Le modèle actuel `Race` mélange la course récurrente et son édition annuelle.

Introduire :

```python
class RaceSeries(models.Model):
    public_id: UUID
    canonical_slug: str
    current_name: str
    gender_category: str
    discipline: str
    format: str
    scope: str
    primary_country: str | None
    importance: str
    active: bool
    aliases: JSON
    metadata: JSON
```

Valeurs principales :

```text
discipline:
- road

format:
- one_day
- stage_race
- championship_road_race
- championship_itt

scope:
- regular
- world_championship
- continental_championship
- national_championship
- olympic

importance:
- P0
- P1
- P2
- P3
```

Une série représente une identité historique stable :

```text
tour-de-france
renewi-tour
national-championship:BE:ME:road-race
world-championship:WE:itt
```

Introduire ensuite :

```python
class RaceEdition(models.Model):
    public_id: UUID
    series: ForeignKey[RaceSeries]
    year: int
    edition_number: int | None
    official_name: str
    classification: str
    status: str
    start_date: date | None
    end_date: date | None
    host_country: str | None
    start_location: str
    finish_location: str
    distance_km: Decimal | None
    is_stage_race: bool
    metadata: JSON
```

Contraintes :

```text
unique(series, year)
index(year, start_date)
index(series, year)
index(status)
index(classification)
```

Le modèle actuel `Race` doit d’abord recevoir une relation vers `RaceSeries`, puis devenir progressivement `RaceEdition`.

Éviter un renommage destructif immédiat.

## 4.2 Alias et changements de nom

Les noms commerciaux changent, mais l’identité doit rester stable.

Prévoir :

```python
class RaceSeriesAlias(models.Model):
    series: ForeignKey[RaceSeries]
    name: str
    normalized_name: str
    valid_from_year: int | None
    valid_to_year: int | None
    locale: str
```

Exemples :

```text
renewi-tour
- Renewi Tour
- Benelux Tour
- BinckBank Tour
- Eneco Tour

adac-cyclassics
- ADAC Cyclassics
- BEMER Cyclassics
- Hamburg Cyclassics

great-sprint-classic
- The Great Sprint Classic
- Classic Brugge-De Panne
- Driedaagse Brugge-De Panne
```

Le changement de nom d’un sponsor ne doit jamais créer automatiquement une nouvelle série.

## 4.3 Étapes

Faire évoluer `Stage` pour prendre en charge autre chose qu’un simple numéro entier.

Ajouter :

```text
stage_key
sequence
display_label
stage_kind
```

Exemples de `stage_key` :

```text
prologue
1
2
3a
3b
itt-7
```

Valeurs de `stage_kind` :

```text
road
itt
ttt
prologue
split_stage
```

Conserver les champs utiles existants :

* départ ;
* arrivée ;
* distance ;
* profil ;
* dénivelé ;
* pente finale ;
* image ou géométrie du parcours ;
* altitude minimum et maximum.

Aucun commentaire ou champ ne doit rester spécifiquement lié à PCS.

## 4.4 Coureurs

Le modèle canonique d’un coureur ne doit pas dépendre d’un slug provider.

Utiliser :

```python
class Rider(models.Model):
    public_id: UUID
    canonical_slug: str
    full_name: str
    normalized_name: str
    birthdate: date | None
    nationality: str
    gender_category: str
    height_cm: Decimal | None
    weight_kg: Decimal | None
    photo_url: str
    metadata: JSON
```

Règles :

* conserver les PK existantes lors de la migration ;
* générer un `public_id` stable ;
* ne jamais fusionner deux coureurs sur le nom uniquement ;
* utiliser, dans l’ordre, mapping existant, identifiant externe stable, date de naissance, nationalité et nom normalisé ;
* placer les correspondances ambiguës dans une file de résolution manuelle.

## 4.5 Équipes

Séparer l’identité historique de l’équipe et sa saison :

```python
class TeamIdentity(models.Model):
    public_id: UUID
    canonical_slug: str
    current_name: str
    primary_country: str
    aliases: JSON
```

```python
class TeamSeason(models.Model):
    identity: ForeignKey[TeamIdentity]
    year: int
    official_name: str
    abbreviation: str
    country: str
    level: str
    jersey_url: str
```

Le modèle actuel `Team` peut temporairement servir de `TeamSeason`.

Ajouter d’abord `TeamIdentity`, migrer les données, puis renommer proprement dans une phase ultérieure.

## 4.6 Startlists

Faire évoluer `StartListEntry` en participation canonique.

Champs attendus :

```text
edition
stage nullable
rider
team_season nullable
bib
role
status
confirmed_at
withdrawn_at
source_updated_at
```

Statuts :

```text
expected
confirmed
dns
started
dnf
otl
dsq
finished
```

## 4.7 Résultats

Le résultat doit pouvoir représenter :

* résultat d’étape ;
* classement général ;
* points ;
* montagne ;
* jeunes ;
* équipes ;
* course d’un jour ;
* championnat ;
* contre-la-montre.

Utiliser des champs normalisés :

```text
rank
status
elapsed_time_ms
gap_ms
gap_laps
points
uci_points
bonus_seconds
penalty_seconds
raw_display_time
```

Ne pas stocker uniquement les écarts sous forme de texte.

Conserver un champ d’affichage brut uniquement comme secours.

Supprimer `points_pcs` du domaine après migration.

## 4.8 Championnats

Les championnats utilisent le même modèle `RaceSeries` et `RaceEdition`.

Ne pas créer un système parallèle inutile.

### Championnats du monde

Créer les séries :

```text
world-championship:ME:road-race
world-championship:ME:itt
world-championship:WE:road-race
world-championship:WE:itt
```

### Championnats d’Europe

Créer :

```text
european-championship:ME:road-race
european-championship:ME:itt
european-championship:WE:road-race
european-championship:WE:itt
```

### Jeux olympiques

Créer :

```text
olympic-games:ME:road-race
olympic-games:ME:itt
olympic-games:WE:road-race
olympic-games:WE:itt
```

Ne créer une édition que les années où l’épreuve existe.

### Championnats nationaux

Créer quatre séries par pays :

```text
national-championship:{COUNTRY}:ME:road-race
national-championship:{COUNTRY}:ME:itt
national-championship:{COUNTRY}:WE:road-race
national-championship:{COUNTRY}:WE:itt
```

Utiliser les codes ISO 3166-1 alpha-2.

Pays P1 :

```text
BE FR IT ES NL GB DE CH DK NO SI PT US AU CO
```

Pays P2 :

```text
AT CA IE LU PL CZ SK HU SE FI NZ EC ER ZA JP
```

Créer une commande idempotente :

```bash
python manage.py seed_national_championships
```

Elle doit créer ou mettre à jour les séries sans dupliquer les données.

## 4.9 Règnes de champions

Créer un modèle dérivé :

```python
class ChampionReign(models.Model):
    rider: ForeignKey[Rider]
    series: ForeignKey[RaceSeries]
    edition: ForeignKey[RaceEdition]
    country: str | None
    gender_category: str
    championship_type: str
    valid_from: date
    valid_until: date | None
```

Après validation des résultats définitifs d’un championnat, recalculer les règnes de champions.

Ne pas modifier directement un règne sur la base d’un résultat provisoire.

---

# 5. Catalogue des courses

Créer un fichier déclaratif versionné :

```text
catalog/seeds/road_series.yaml
```

Il contient les identités récurrentes, jamais les dates codées en dur.

Format indicatif :

```yaml
- slug: tour-de-france
  name: Tour de France
  category: ME
  discipline: road
  format: stage_race
  scope: regular
  priority: P0
  countries: [FR]
  aliases: []
```

Créer une commande :

```bash
python manage.py seed_road_series
```

Elle doit être :

* idempotente ;
* testée ;
* transactionnelle ;
* non destructive ;
* capable de mettre à jour les alias ;
* incapable d’effacer une série absente du YAML sans option explicite.

## 5.1 P0 — Hommes

```text
tour-de-france
giro-ditalia
vuelta-a-espana
milano-sanremo
ronde-van-vlaanderen
paris-roubaix
liege-bastogne-liege
il-lombardia
```

## 5.2 P0 — Femmes

```text
tour-de-france-femmes
giro-ditalia-women
vuelta-espana-femenina
ronde-van-vlaanderen-women
paris-roubaix-femmes
liege-bastogne-liege-femmes
strade-bianche-donne
milano-sanremo-donne
```

Ajouter également en P0 :

* Championnats du monde ME/WE, route et ITT ;
* Jeux olympiques ME/WE, route et ITT.

## 5.3 P1 — Hommes, courses par étapes

```text
paris-nice
tirreno-adriatico
volta-ciclista-a-catalunya
itzulia-basque-country
tour-de-romandie
criterium-du-dauphine
tour-de-suisse
```

## 5.4 P1 — Hommes, classiques

```text
omloop-het-nieuwsblad
strade-bianche
e3-saxo-classic
gent-wevelgem
dwars-door-vlaanderen
amstel-gold-race
fleche-wallonne
clasica-san-sebastian
grand-prix-cycliste-de-quebec
grand-prix-cycliste-de-montreal
```

## 5.5 P1 — Femmes, courses par étapes

```text
itzulia-women
vuelta-a-burgos-feminas
tour-de-suisse-women
tour-de-romandie-feminin
tour-of-britain-women
```

## 5.6 P1 — Femmes, classiques

```text
omloop-het-nieuwsblad-women
trofeo-alfredo-binda
gent-wevelgem-women
dwars-door-vlaanderen-women
amstel-gold-race-women
fleche-wallonne-feminine
```

Ajouter en P1 :

* Championnats d’Europe ME/WE, route et ITT ;
* championnats nationaux des quinze pays P1.

## 5.7 P2 — Hommes

```text
santos-tour-down-under
cadel-evans-great-ocean-road-race
uae-tour
great-sprint-classic
eschborn-frankfurt
copenhagen-sprint
tour-de-pologne
adac-cyclassics
renewi-tour
bretagne-classic
tour-of-guangxi
```

## 5.8 P2 — Femmes

```text
santos-tour-down-under-women
cadel-evans-great-ocean-road-race-women
uae-tour-women
great-sprint-classic-women
copenhagen-sprint-women
classic-lorient-agglomeration
tour-of-chongming-island
tour-of-guangxi-women
```

Ajouter en P2 les championnats nationaux des quinze pays P2.

## 5.9 P3 — Hommes, courses par étapes

```text
volta-ao-algarve
tour-of-oman
alula-tour
tour-of-the-alps
deutschland-tour
tour-of-britain
tour-de-wallonie
quatre-jours-de-dunkerque
arctic-race-of-norway
tour-of-norway
```

## 5.10 P3 — Hommes, courses d’un jour

```text
kuurne-bruxelles-kuurne
le-samyn
scheldeprijs
brabantse-pijl
milano-torino
giro-dell-emilia
gran-piemonte
tre-valli-varesine
paris-tours
japan-cup
```

## 5.11 P3 — Femmes

```text
simac-ladies-tour
tour-of-scandinavia
thuringen-ladies-tour
tour-de-belgique-women
tour-feminin-international-des-pyrenees
nokere-koerse-women
scheldeprijs-women
brabantse-pijl-women
```

P3 doit être présent dans le catalogue, mais son ingestion peut être désactivée par défaut.

---

# 6. Modèle provider

Créer un modèle de fournisseur :

```python
class Provider(models.Model):
    key: str
    name: str
    provider_type: str
    enabled: bool
    base_url: str
    capabilities: JSON
    authority_level: str
    attribution_text: str
    terms_url: str
    license_metadata: JSON
    default_cache_ttl: int
    min_request_interval_seconds: Decimal
    max_requests_per_minute: int | None
    health_status: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error: str
```

Valeurs de `provider_type` :

```text
official_governing_body
official_organizer
official_timing
national_federation
licensed_commercial
community
manual
fixture
legacy
```

Ne jamais stocker de clé API ou secret en clair dans cette table.

Stocker seulement le nom de la variable d’environnement attendue, par exemple :

```text
credential_env_prefix=PROVIDER_UCI
```

## 6.1 Capacités

Définir une enum :

```text
CALENDAR
RACE_SERIES
RACE_EDITIONS
STAGES
ROUTE
PROFILE
KEYPOINTS
RIDERS
TEAMS
STARTLIST
RESULTS
CLASSIFICATIONS
LIVE_STATE
LIVE_GROUPS
LIVE_EVENTS
IMAGES
```

Chaque provider déclare explicitement ses capacités.

Une orchestration ne doit jamais appeler une méthode pour laquelle le provider ne déclare pas la capacité.

## 6.2 Interface commune

Créer une interface typée similaire à :

```python
class CyclingProvider(ABC):
    key: str
    capabilities: frozenset[ProviderCapability]

    def healthcheck(self) -> ProviderHealth:
        ...

    def fetch_calendar(self, query: CalendarQuery) -> ProviderBatch:
        ...

    def fetch_race_edition(self, query: RaceEditionQuery) -> ProviderBatch:
        ...

    def fetch_stages(self, query: StageQuery) -> ProviderBatch:
        ...

    def fetch_startlist(self, query: StartListQuery) -> ProviderBatch:
        ...

    def fetch_results(self, query: ResultsQuery) -> ProviderBatch:
        ...

    def fetch_live(self, query: LiveQuery) -> ProviderBatch:
        ...
```

Les méthodes non prises en charge doivent lever une exception métier explicite :

```text
ProviderCapabilityNotSupported
```

Ne pas renvoyer silencieusement une liste vide pour masquer une capacité absente.

## 6.3 DTO normalisés

Utiliser Pydantic 2 ou des dataclasses strictement validées.

Créer notamment :

```text
NormalizedRaceSeries
NormalizedRaceEdition
NormalizedStage
NormalizedRoutePoint
NormalizedKeyPoint
NormalizedRider
NormalizedTeamIdentity
NormalizedTeamSeason
NormalizedStartListEntry
NormalizedResult
NormalizedClassification
NormalizedLiveSnapshot
NormalizedLiveGroup
NormalizedLiveEvent
```

Chaque objet normalisé doit contenir :

```text
provider_key
external_id
external_url
observed_at
source_updated_at nullable
confidence
payload_version
```

Les DTO ne doivent pas contenir d’objets Django.

Les providers produisent des DTO. Le moteur d’ingestion transforme ensuite les DTO en modèles canoniques.

---

# 7. Providers à prévoir

## 7.1 Providers à implémenter complètement

### SeedProvider

Source des séries déclarées dans les fichiers YAML.

Capacités :

```text
RACE_SERIES
```

### ManualProvider

Permet les corrections et ajouts manuels depuis l’administration.

Les valeurs manuelles validées ont la priorité maximale.

Elles doivent conserver :

* auteur ;
* date ;
* justification ;
* ancienne valeur ;
* nouvelle valeur.

### FixtureProvider

Provider de test hors ligne.

Il doit permettre de simuler :

* une source officielle ;
* une source secondaire ;
* des données conflictuelles ;
* un provider lent ;
* un timeout ;
* un `429 Retry-After` ;
* un `403` ;
* une réponse invalide ;
* un live qui évolue.

Il doit être utilisé dans la suite de tests d’intégration.

## 7.2 Providers officiels ou autorisés

Préparer des adaptateurs séparés pour :

```text
UciProvider
NationalFederationProvider
OrganizerProvider
TimingProvider
PcsOfficialApiProvider
CommercialProvider
```

`PcsOfficialApiProvider` doit être désactivé par défaut et ne fonctionner qu’avec un accès API officiel et des credentials configurés.

Ne jamais réutiliser le scraper PCS existant dans ce provider.

## 7.3 Adaptateurs organisateurs

Prévoir une classe de base, puis des implémentations indépendantes lorsque des sources légitimes et stables sont identifiées :

```text
AsoProvider
RcsSportProvider
FlandersClassicsProvider
RaceCenterProvider
```

Ne pas inventer d’endpoint.

Avant d’activer un provider réel, documenter dans :

```text
docs/providers/{provider-key}.md
```

Les éléments suivants :

* source utilisée ;
* propriétaire ;
* type d’accès ;
* documentation ;
* conditions d’utilisation ;
* attribution ;
* capacités ;
* limites ;
* politique de cache ;
* fréquence autorisée ;
* format des identifiants ;
* comportement en cas d’erreur.

Lorsqu’aucun accès documenté ou autorisé n’existe, livrer le squelette désactivé plutôt qu’un scraper agressif.

## 7.4 Sources communautaires

Une source communautaire ne doit être activée que si son usage est compatible avec ses conditions.

Elle ne doit jamais écraser automatiquement une donnée officielle déjà acceptée.

---

# 8. Correspondances d’identifiants

Créer un modèle générique de mapping :

```python
class ProviderEntityMapping(models.Model):
    provider: ForeignKey[Provider]
    entity_type: str
    content_type: ForeignKey[ContentType]
    object_id: int
    canonical_object: GenericForeignKey
    external_id: str
    external_slug: str
    external_url: str
    external_name: str
    metadata: JSON
    first_seen_at: datetime
    last_seen_at: datetime
    verified: bool
```

Contraintes :

```text
unique(provider, entity_type, external_id)
index(provider, entity_type, external_slug)
index(content_type, object_id)
```

Ordre de résolution d’identité :

1. mapping vérifié existant ;
2. external ID déjà connu ;
3. clé canonique explicitement fournie ;
4. alias exact normalisé ;
5. critères métier fiables ;
6. candidat à validation manuelle.

Ne pas effectuer de fusion automatique risquée.

Pour les coureurs, ne jamais fusionner sur le nom seul.

Pour les éditions, utiliser au minimum série canonique et année.

---

# 9. Provenance, snapshots et conflits

## 9.1 Snapshot source

Créer :

```python
class SourceSnapshot(models.Model):
    provider: ForeignKey[Provider]
    resource_type: str
    external_key: str
    source_url: str
    fetched_at: datetime
    source_updated_at: datetime | None
    http_status: int | None
    content_type: str
    content_hash: str
    payload: JSON | None
    raw_text: Text | None
    expires_at: datetime | None
    request_metadata: JSON
```

Éviter de dupliquer un payload identique grâce à `content_hash`.

Prévoir une politique de rétention configurable, surtout pour le live.

## 9.2 Import normalisé

Créer :

```python
class NormalizedImport(models.Model):
    snapshot: ForeignKey[SourceSnapshot]
    entity_type: str
    external_id: str
    normalized_payload: JSON
    schema_version: str
    validation_status: str
    validation_errors: JSON
```

## 9.3 Provenance de champ

Créer :

```python
class FieldProvenance(models.Model):
    content_type: ForeignKey[ContentType]
    object_id: int
    field_name: str
    provider: ForeignKey[Provider]
    snapshot: ForeignKey[SourceSnapshot] | None
    observed_at: datetime
    accepted_at: datetime
    confidence: Decimal
    value_hash: str
    manual_override: bool
```

Le système doit pouvoir expliquer :

```text
Quelle source a fourni cette valeur ?
Quand a-t-elle été observée ?
Est-elle encore fraîche ?
Quelle règle l’a sélectionnée ?
```

## 9.4 Conflits

Créer :

```python
class DataConflict(models.Model):
    entity_type: str
    content_type: ForeignKey[ContentType]
    object_id: int
    field_name: str
    current_value: JSON
    proposed_value: JSON
    current_provider: ForeignKey[Provider] | None
    proposed_provider: ForeignKey[Provider]
    status: str
    resolution: str
    resolved_by: ForeignKey[User] | None
    created_at: datetime
    resolved_at: datetime | None
```

Statuts :

```text
open
auto_resolved
manually_resolved
ignored
```

---

# 10. Règles de fusion

Ne pas attribuer une priorité globale unique à chaque provider.

La priorité dépend du type de donnée.

Ordre général :

```text
1. Override manuel validé
2. Organisme officiel compétent pour le champ
3. Chronométreur ou organisateur officiel
4. Fédération nationale ou équipe officielle
5. Fournisseur commercial sous licence
6. Source communautaire
7. Donnée legacy
```

Matrice recommandée :

```text
Classification UCI :
UCI > organisateur > commercial > communautaire

Dates et statut du calendrier :
UCI ou organisateur officiel > commercial > communautaire

Résultats :
chronométreur officiel > organisateur > fédération/UCI > commercial > communautaire

Startlist :
organisateur/chronométreur > équipe officielle > commercial > communautaire

Parcours, étapes et points clés :
organisateur > chronométreur > commercial > communautaire

Live :
chronométreur ou organisateur > commercial licencié > autre source autorisée

Biographie coureur :
fédération/équipe/UCI > commercial > communautaire

Correction manuelle :
toujours prioritaire jusqu’à révocation explicite
```

Règles supplémentaires :

* ne pas remplacer une valeur non vide par une valeur vide ;
* préférer une valeur plus récente seulement si l’autorité est comparable ;
* ne pas écraser une valeur manuelle ;
* journaliser toute différence significative ;
* mettre en conflit les écarts de résultat, date, distance ou identité ;
* permettre un seuil de tolérance pour les mesures numériques ;
* rendre les fusions idempotentes ;
* exécuter les écritures dans une transaction ;
* verrouiller l’entité canonique pendant une fusion concurrente.

Créer des classes de stratégie :

```text
MergePolicy
FieldRule
MergeDecision
MergeResult
ConflictDetector
```

Ne pas disperser les `if provider == ...` dans les modèles ou les vues.

---

# 11. Orchestration des synchronisations

## 11.1 Tâches

Créer des tâches explicites :

```text
sync_season_calendar
sync_race_edition
sync_race_stages
sync_race_startlist
sync_race_results
sync_race_live
finalize_race
reconcile_provider_mappings
resolve_data_conflicts
refresh_provider_health
```

Chaque tâche doit recevoir :

```text
provider_key
canonical_entity_id
force
correlation_id
```

Éviter les tâches qui découvrent implicitement tout l’univers sans limite.

## 11.2 Verrous distribués

Utiliser Redis pour garantir un seul fetch simultané pour :

```text
provider + resource_type + external_key
```

Exemple de clé :

```text
ingestion-lock:{provider}:{resource_type}:{external_key}
```

Ne pas utiliser seulement `time.sleep` par worker.

## 11.3 Rate limiting global

Créer un limiteur Redis partagé entre :

* tous les workers Celery ;
* toutes les instances web ;
* tous les conteneurs ;
* toutes les tâches du même provider.

Respecter :

* `Retry-After` ;
* quotas configurés ;
* intervalle minimum ;
* limites par host ;
* limites par provider.

Aucune boucle de retry rapide.

## 11.4 Circuit breaker par provider

Le circuit breaker doit être indépendant pour chaque provider.

États :

```text
closed
open
half_open
disabled
```

Comportement :

* `401/403` : ne pas essayer de contourner ; ouvrir ou désactiver selon configuration ;
* `429` : respecter `Retry-After` ;
* timeout et `5xx` : retry borné avec backoff exponentiel et jitter ;
* réponse invalide : journaliser et placer le snapshot en échec ;
* erreur de parsing : ne pas supprimer les données canoniques existantes.

## 11.5 Cache

Le cache doit être défini par ressource.

Ordres de grandeur par défaut, configurables et subordonnés aux règles du provider :

```text
série : 30 jours
édition passée : 7 jours
édition future : 6 heures
startlist éloignée : 24 heures
startlist proche : 30 minutes
résultat final : 30 jours
live : selon quota, jamais inférieur à la limite fournisseur
```

Un `force=True` ne doit pas contourner un rate limit ni un verrou.

## 11.6 Polling live adaptatif

Valeurs par défaut configurables :

```text
Plus de 24 h avant : aucun poll live
Entre 24 h et 2 h avant : toutes les 30 min
Entre 2 h et 30 min avant : toutes les 5 min
Entre 30 min avant et départ : toutes les 60 s
Course active P0/P1 : toutes les 30 s au plus rapide
Course active P2 : toutes les 60 s au plus rapide
Après arrivée : +2 min, +10 min, +60 min, puis arrêt
```

Ces valeurs ne doivent jamais être plus agressives que les conditions du provider.

Un seul provider live principal est sélectionné pour une course à un instant donné. Un provider secondaire peut servir de fallback, mais ne doit pas doubler systématiquement le trafic.

---

# 12. Refonte du live

Supprimer les champs spécifiques PCS du modèle live.

Remplacer l’état unique mutable par :

```python
class LiveSession(models.Model):
    edition: ForeignKey[RaceEdition]
    stage: ForeignKey[Stage] | None
    status: str
    active_provider: ForeignKey[Provider] | None
    is_active: bool
    started_at: datetime | None
    finished_at: datetime | None
    last_observed_at: datetime | None
    freshness_status: str
```

Créer un snapshot :

```python
class LiveSnapshot(models.Model):
    session: ForeignKey[LiveSession]
    provider: ForeignKey[Provider]
    observed_at: datetime
    race_status: str
    km_done: Decimal | None
    km_to_go: Decimal | None
    average_speed_kmh: Decimal | None
    payload: JSON
```

Pour éviter une croissance illimitée :

* conserver tous les événements ;
* conserver les snapshots fréquents sur une courte période ;
* compacter ou purger les snapshots selon une politique de rétention ;
* conserver les snapshots importants : départ, changements de groupe, points clés, arrivée.

Les groupes doivent référencer les coureurs canoniques lorsque le mapping est connu.

Conserver temporairement les informations non résolues dans :

```text
unresolved_riders
```

Les vues live doivent lire exclusivement ces modèles locaux.

Supprimer `_maybe_refresh` et toute synchronisation déclenchée par la consultation de la page.

---

# 12 bis — Timeline complète, faits de course et notifications

La timeline, les faits de course, les abonnements et les notifications Web Push sont des fonctionnalités critiques.

La refonte ne doit supprimer, dégrader ou simplifier aucune fonctionnalité existante sans remplacement testé.

Le passage au multi-provider doit au minimum préserver :

* la timeline chronologique ;
* les marqueurs kilométriques ;
* le texte des événements ;
* les événements de départ ;
* les rappels avant départ ;
* les événements de chute ;
* les derniers kilomètres ;
* les ascensions finales ;
* l’arrivée ;
* le vainqueur ;
* le suivi individuel d’une course ;
* les abonnements Web Push ;
* la déduplication des notifications ;
* le nettoyage des abonnements expirés ;
* l’ouverture de la bonne page au clic ;
* le fonctionnement sans clés VAPID ;
* l’absence d’impact d’un échec de notification sur l’ingestion live.

## 12 bis.1 Modèle canonique des événements

Remplacer le modèle `LiveEvent` dépendant d’un numéro de séquence provider par un modèle canonique :

```python
class RaceEvent(models.Model):
    public_id = models.UUIDField(...)
    session = models.ForeignKey(LiveSession, ...)
    stage = models.ForeignKey(Stage, null=True, blank=True, ...)
    event_type = models.CharField(...)
    status = models.CharField(...)
    title = models.CharField(...)
    text = models.TextField(...)
    occurred_at = models.DateTimeField(null=True, blank=True)
    observed_at = models.DateTimeField()
    race_km = models.DecimalField(null=True, blank=True, ...)
    km_to_go = models.DecimalField(null=True, blank=True, ...)
    sort_key = models.BigIntegerField(...)
    importance = models.CharField(...)
    confidence = models.DecimalField(...)
    metadata = models.JSONField(...)
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL
    )
    retracted_at = models.DateTimeField(null=True, blank=True)
```

Créer également :

```python
class ProviderEventObservation(models.Model):
    event = models.ForeignKey(RaceEvent, ...)
    provider = models.ForeignKey(Provider, ...)
    snapshot = models.ForeignKey(SourceSnapshot, ...)
    external_id = models.CharField(...)
    external_sequence = models.CharField(...)
    raw_type = models.CharField(...)
    raw_marker = models.CharField(...)
    raw_text = models.TextField(...)
    raw_html = models.TextField(...)
    observed_at = models.DateTimeField(...)
    payload = models.JSONField(...)
```

Le contenu HTML externe ne doit jamais être directement rendu.

Il doit être :

* conservé uniquement comme observation brute lorsque juridiquement autorisé ;
* nettoyé avant toute utilisation ;
* transformé en texte ou structure canonique ;
* considéré comme non fiable.

## 12 bis.2 Taxonomie des faits de course

Prévoir au minimum les types suivants :

```text
race_scheduled
race_reminder
neutral_start
race_start
attack
counter_attack
breakaway_created
rider_joined_group
rider_dropped
group_split
group_merge
peloton_reformation
gap_update
crash
mechanical
puncture
bike_change
medical_assistance
abandon
dns
dnf
otl
dsq
penalty
neutralization
race_resumed
route_change
weather_alert
feed_zone
climb_start
climb_summit
intermediate_sprint
bonus_sprint
classification_update
last_20_km
last_10_km
last_5_km
flamme_rouge
final_climb
finish
stage_winner
provisional_result
official_result
result_corrected
general_classification_update
points_classification_update
kom_classification_update
youth_classification_update
team_classification_update
free_text
```

Cette taxonomie doit être extensible sans migration pour chaque nouveau type provider.

Les providers peuvent produire des types bruts différents. Chaque adaptateur doit les convertir vers cette taxonomie.

Lorsqu’aucune correspondance fiable n’existe, utiliser `free_text` sans inventer une classification.

## 12 bis.3 Participants et groupes concernés

Créer une relation structurée entre événements, coureurs et équipes :

```python
class RaceEventParticipant(models.Model):
    event = models.ForeignKey(RaceEvent, ...)
    rider = models.ForeignKey(Rider, null=True, blank=True, ...)
    team_season = models.ForeignKey(TeamSeason, null=True, blank=True, ...)
    role = models.CharField(...)
    external_name = models.CharField(...)
```

Exemples de rôles :

```text
subject
winner
attacker
crashed
abandoned
penalized
joined_group
left_group
leader
```

Un événement ne doit pas dépendre uniquement d’un nom inclus dans une phrase.

## 12 bis.4 Déduplication multi-provider

Ne jamais supposer que deux providers utilisent le même numéro de séquence.

Utiliser successivement :

1. mapping explicite déjà validé ;
2. identifiant externe du provider ;
3. relation de correction ou remplacement fournie par la source ;
4. empreinte canonique ;
5. rapprochement prudent ;
6. création de deux événements distincts en cas de doute.

L’empreinte canonique peut utiliser :

```text
session
event_type
fenêtre temporelle
kilomètre
coureurs concernés
groupes concernés
texte normalisé
```

Un rapprochement incertain ne doit pas supprimer un événement.

Il doit créer un conflit ou conserver les deux observations.

## 12 bis.5 Ordre, corrections et suppressions

Conserver séparément :

```text
external_sequence
occurred_at
observed_at
ingested_at
sort_key
```

Les événements peuvent arriver en retard ou dans le désordre.

Le système doit savoir :

* insérer un événement ancien ;
* corriger un événement ;
* retirer une information erronée ;
* rattacher plusieurs observations au même fait ;
* indiquer qu’une information est provisoire ;
* afficher la dernière version valide ;
* conserver l’historique de correction.

Une correction ne doit jamais supprimer silencieusement l’événement original.

## 12 bis.6 Conservation de la timeline

Conserver tous les événements canoniques.

La rétention courte des snapshots live ne doit pas s’appliquer à la timeline.

Les événements, corrections et provenance constituent l’historique durable de la course.

L’API doit prendre en charge :

```text
pagination
since
before
event_type
importance
rider
team
```

Prévoir :

```text
GET /api/v1/stages/{public_id}/timeline/
GET /api/v1/stages/{public_id}/timeline/?since=...
```

Conserver une route de compatibilité avec l’API live actuelle.

## 12 bis.7 Moteur de notifications canonique

Séparer strictement :

```text
RaceEvent
    ↓
NotificationRule
    ↓
NotificationCandidate
    ↓
NotificationDelivery
    ↓
Web Push
```

L’ingestion d’un événement ne doit pas envoyer directement une notification dans la même transaction.

Créer une tâche Celery dédiée.

Créer :

```python
class NotificationRule(models.Model):
    key = models.CharField(...)
    enabled = models.BooleanField(...)
    event_types = models.JSONField(...)
    minimum_priority = models.CharField(...)
    race_priorities = models.JSONField(...)
    cooldown_seconds = models.IntegerField(...)
    template_title = models.CharField(...)
    template_body = models.TextField(...)
```

```python
class NotificationDelivery(models.Model):
    subscription = models.ForeignKey(PushSubscription, ...)
    event = models.ForeignKey(RaceEvent, null=True, blank=True, ...)
    delivery_type = models.CharField(...)
    deduplication_key = models.CharField(...)
    status = models.CharField(...)
    attempts = models.IntegerField(...)
    last_http_status = models.IntegerField(null=True, blank=True)
    scheduled_at = models.DateTimeField(...)
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(...)
```

Ajouter une contrainte d’unicité sur :

```text
subscription + deduplication_key
```

Les notifications doivent être idempotentes même si :

* une tâche Celery est rejouée ;
* un snapshot est réimporté ;
* un événement est observé par plusieurs providers ;
* le worker redémarre ;
* un provider envoie deux fois le même événement.

## 12 bis.8 Notifications obligatoires

Conserver au minimum les notifications actuellement disponibles :

```text
Rappel avant départ
Départ
Chute importante
Derniers kilomètres
Ascension finale
Arrivée
Vainqueur
```

Ajouter la capacité de notifier, sans forcément tout activer par défaut :

```text
Échappée formée
Écart important
Incident d’un favori
Abandon d’un favori
Neutralisation
Reprise de course
Sommet d’un col important
Sprint intermédiaire
Flamme rouge
Résultats provisoires
Résultats officiels
Correction de résultat
Changement de leader
```

Les règles trop bruyantes doivent être désactivées par défaut.

## 12 bis.9 Préférences d’abonnement

Conserver le suivi anonyme par course.

Faire évoluer `RaceFollow` afin de pouvoir mémoriser :

```text
course suivie
types d’événements souhaités
niveau minimal d’importance
rappel avant départ activé
résultat final activé
incidents activés
derniers kilomètres activés
```

Une migration doit convertir chaque suivi existant en suivi « toutes les notifications historiques activées ».

## 12 bis.10 Tags Web Push

Ne pas utiliser un tag identique pour tous les événements d’une session.

Utiliser une clé stable par événement :

```text
race-event:{event.public_id}
```

Utiliser des tags spécifiques pour les événements mutables :

```text
race-status:{session.public_id}
live-gap:{session.public_id}
provisional-result:{stage.public_id}
```

Ainsi :

* une mise à jour du même fait peut remplacer sa version précédente ;
* deux faits différents ne s’écrasent pas mutuellement.

## 12 bis.11 Fiabilité des envois

Conserver le nettoyage automatique des abonnements répondant `404` ou `410`.

Ajouter :

* retries bornés pour erreurs temporaires ;
* backoff ;
* métriques d’envoi ;
* statut par livraison ;
* aucune répétition infinie ;
* timeout ;
* limite de concurrence ;
* journalisation sans endpoint complet ni clés ;
* commande de test Web Push ;
* possibilité de désactiver immédiatement les envois.

Un échec Web Push ne doit jamais faire échouer :

* le fetch provider ;
* la normalisation ;
* la fusion ;
* la sauvegarde de l’événement ;
* la progression du live.

## 12 bis.12 Migration sans perte

Avant de basculer :

1. inventorier tous les comportements actuels ;
2. exporter les comptes et volumes existants ;
3. migrer `LiveEvent` vers `RaceEvent` ;
4. migrer les numéros de séquence vers `ProviderEventObservation` ;
5. migrer `PushSubscription` sans modifier les endpoints ;
6. migrer `RaceFollow` vers le nouveau modèle ;
7. migrer les drapeaux de notification ;
8. conserver les anciennes tables ;
9. activer un dual-read temporaire ;
10. comparer les timelines ;
11. comparer les notifications candidates ;
12. supprimer le legacy uniquement après validation.

Créer une commande :

```bash
python manage.py audit_live_feature_parity
```

Elle doit vérifier :

* nombre de sessions ;
* nombre d’événements ;
* nombre d’abonnements ;
* nombre de courses suivies ;
* événements sans mapping ;
* suivis orphelins ;
* événements dupliqués ;
* notifications historiques migrées ;
* différences entre ancienne et nouvelle timeline.

## 12 bis.13 Tests de parité obligatoires

Créer des fixtures rejouant une course entière.

Tester :

```text
timeline vide
départ
événements historiques présents au démarrage
attaque
création d’une échappée
changement d’écart
chute
abandon
montée finale
derniers kilomètres
arrivée
vainqueur tardif
correction du vainqueur
événement reçu deux fois
événement reçu par deux providers
événement reçu en retard
retrait d’un événement erroné
provider principal indisponible
bascule vers fallback
retour au provider principal
redémarrage du worker
rejeu d’une tâche
abonnement Web Push expiré
push désactivé
push temporairement en erreur
clic sur une notification
```

La bascule vers le nouveau live est interdite tant que les tests de parité ne passent pas.

## 12 bis.14 Critères de non-régression

La fonctionnalité live n’est considérée comme migrée que si :

* aucun événement historique n’est perdu ;
* les événements nouveaux sont persistés avant notification ;
* la timeline reste consultable sans provider ;
* les abonnements existants restent valides ;
* le bouton Suivre fonctionne ;
* les sept catégories de notifications historiques fonctionnent ;
* aucune notification n’est envoyée deux fois ;
* deux événements différents ne se remplacent pas ;
* les abonnements morts sont nettoyés ;
* une erreur push ne bloque pas le live ;
* une correction provider est visible ;
* chaque événement possède une provenance ;
* les tests de parité passent.
- Le profil détaillé reste visible pour les étapes déjà importées.
- Les points d’altitude existants sont migrés sans perte.
- Les cols et sprints restent affichés.
- La tête de course est positionnée sur le profil.
- Les groupes et écarts restent affichés.
- Le mode d’estimation actuel est préservé.
- Une position estimée est explicitement identifiée.
- Une position exacte remplace automatiquement l’estimation lorsqu’elle arrive.
- Une source indisponible ne fait pas disparaître le dernier snapshot valide.
- Le changement de provider ne recrée pas tous les groupes en doublon.
- La progression continue après redémarrage des workers.
- Le front n’interroge jamais directement le provider.

---

# 13. API publique

Versionner l’API :

```text
/api/v1/
```

Endpoints cibles :

```text
GET /api/v1/race-series/
GET /api/v1/race-series/{slug}/
GET /api/v1/editions/
GET /api/v1/editions/{public_id}/
GET /api/v1/editions/{public_id}/stages/
GET /api/v1/editions/{public_id}/startlist/
GET /api/v1/editions/{public_id}/results/
GET /api/v1/stages/{public_id}/
GET /api/v1/stages/{public_id}/results/
GET /api/v1/stages/{public_id}/live/
GET /api/v1/riders/
GET /api/v1/riders/{public_id}/
GET /api/v1/teams/
GET /api/v1/champions/
```

Filtres importants :

```text
year
priority
category
classification
country
scope
format
status
live
```

Les réponses publiques doivent être provider-agnostic.

Ajouter un bloc de métadonnées :

```json
{
  "freshness": {
    "status": "fresh",
    "observed_at": "...",
    "stale_after": "..."
  },
  "sources": [
    {
      "provider": "uci",
      "observed_at": "...",
      "authority": "official_governing_body"
    }
  ]
}
```

Ne pas exposer les payloads bruts ni les secrets.

Conserver temporairement les anciennes routes avec :

* redirections ;
* serializers de compatibilité ;
* avertissement de dépréciation ;
* tests de non-régression.

---

# 14. Recherche

La recherche publique doit être uniquement locale.

Elle doit interroger :

* coureurs canoniques ;
* alias des coureurs ;
* équipes ;
* alias d’équipes ;
* séries ;
* alias de séries ;
* éditions.

Supprimer toute recherche distante automatique.

Créer une commande d’administration distincte pour chercher ou importer depuis un provider lorsque cela est explicitement demandé.

---

# 15. Administration Django

Ajouter des écrans admin pour :

* providers ;
* santé des providers ;
* capacités ;
* mappings ;
* snapshots ;
* imports invalides ;
* conflits ;
* overrides manuels ;
* synchronisations ;
* séries ;
* éditions ;
* couverture des courses ;
* fraîcheur des données.

Actions admin :

```text
Synchroniser avec le provider sélectionné
Rejouer un snapshot
Valider un mapping
Fusionner deux entités
Refuser une fusion
Choisir la valeur d’un conflit
Créer un override manuel
Révoquer un override
Désactiver un provider
Tester la santé du provider
```

Les actions dangereuses doivent demander une confirmation dans l’admin.

Créer une vue de couverture indiquant, par course :

```text
calendar
stages
route
startlist
results
live
last success
freshness
active provider
fallback provider
```

---

# 16. Interface utilisateur

Adapter les pages existantes sans refaire tout le design.

Afficher :

* nom canonique ;
* nom officiel de l’édition ;
* priorité P0/P1/P2/P3 ;
* statut ;
* données disponibles ;
* heure de dernière mise à jour ;
* indicateur frais/périmé/indisponible ;
* source principale ;
* fallback éventuel ;
* live local.

Ne pas afficher un écran vide lorsqu’un provider est indisponible.

Afficher la dernière donnée connue avec un avertissement de fraîcheur.

Les notifications push doivent être générées depuis les événements live canoniques, jamais directement depuis un payload provider.

---

# 17. Migration du legacy PCS

Créer un provider :

```text
legacy-pcs
```

Il est :

```text
enabled = false
provider_type = legacy
```

Utiliser ce provider uniquement pour préserver la provenance des données existantes.

Migrer :

```text
Rider.pcs_id
Team.pcs_id
Race.pcs_id
LiveSession.pcs_live_id
```

vers `ProviderEntityMapping`.

Migrer les valeurs existantes de `points_pcs` vers une structure de résultat source ou un champ legacy, puis supprimer progressivement ce champ du domaine canonique.

Déplacer les fixtures actuelles PCS vers :

```text
tests/fixtures/providers/legacy_pcs/
```

Elles peuvent rester utiles pour vérifier la migration ou les parsers legacy, mais aucun test runtime principal ne doit dépendre d’un accès PCS.

Supprimer après bascule :

```text
core/pcs_client.py
core/pcs_circuit.py
```

ou les déplacer dans un module `legacy` non chargé, uniquement si une migration transitoire l’exige.

Supprimer les appels PCS de :

* `catalog/services.py` ;
* `catalog/search.py` ;
* `live/services.py` ;
* `live/tasks.py` ;
* `live/views.py` ;
* `live/api.py` ;
* commandes de synchronisation ;
* vues de détail ;
* tâches Celery Beat.

---

# 18. Configuration

Variables générales :

```text
PROVIDERS_ENABLED=seed,manual
PROVIDER_HTTP_TIMEOUT_SECONDS=20
PROVIDER_DEFAULT_MAX_RETRIES=3
PROVIDER_SNAPSHOT_RETENTION_DAYS=30
LIVE_SNAPSHOT_RETENTION_HOURS=48
```

Variables par provider :

```text
PROVIDER_UCI_ENABLED=false
PROVIDER_UCI_BASE_URL=
PROVIDER_UCI_TOKEN=
PROVIDER_UCI_MIN_INTERVAL_SECONDS=
PROVIDER_UCI_REQUESTS_PER_MINUTE=
```

Ne pas exiger qu’une variable d’un provider désactivé soit définie.

Valider la configuration au démarrage.

Une erreur de configuration d’un provider désactivé ne doit pas empêcher Django de démarrer.

---

# 19. Observabilité

Utiliser des logs JSON structurés.

Chaque synchronisation doit inclure :

```text
correlation_id
provider
capability
resource_type
canonical_id
external_id
attempt
duration_ms
http_status
cache_hit
lock_acquired
records_received
records_created
records_updated
conflicts_created
status
```

Créer des métriques ou, au minimum, des agrégats accessibles dans l’admin :

```text
provider_requests_total
provider_failures_total
provider_rate_limited_total
provider_circuit_open
provider_sync_duration
provider_last_success_timestamp
provider_records_imported
provider_conflicts_total
live_snapshot_age
```

Créer des endpoints :

```text
/health/
/health/providers/
```

`/health/` vérifie l’application, PostgreSQL et Redis.

`/health/providers/` fournit l’état connu sans contacter tous les fournisseurs à chaque requête.

---

# 20. Sécurité et conformité

Règles obligatoires :

* aucun secret dans Git ;
* aucun token dans les logs ;
* aucune URL signée exposée ;
* redaction des headers sensibles ;
* validation stricte des URLs de provider ;
* protection contre SSRF ;
* timeout sur chaque requête ;
* taille maximale des réponses ;
* types MIME validés ;
* aucun parsing arbitraire de code distant ;
* aucune exécution JavaScript distante ;
* aucune instruction extraite d’un payload externe ne doit être exécutée ;
* documentation des droits d’utilisation et d’attribution ;
* possibilité de supprimer toutes les données provenant d’un provider donné.

Ajouter une commande :

```bash
python manage.py purge_provider_data --provider KEY --dry-run
```

Le mode `--dry-run` est obligatoire.

La suppression doit respecter les données canoniques partagées par plusieurs sources et ne pas supprimer une entité encore justifiée par une autre source.

---

# 21. Tests

Ajouter :

```text
pytest
pytest-django
coverage
respx ou responses
freezegun
```

Aucun test ne doit dépendre d’Internet.

## 21.1 Tests de contrat provider

Créer une suite commune exécutée pour chaque provider :

```text
test_declared_capabilities_match_methods
test_normalized_schema_validation
test_timeout_handling
test_429_retry_after
test_403_does_not_bypass
test_5xx_backoff
test_invalid_payload
test_idempotent_import
test_mapping_reuse
test_snapshot_created
test_logs_do_not_contain_secrets
```

## 21.2 Tests du moteur de fusion

Couvrir :

* valeur vide contre valeur existante ;
* source officielle contre communautaire ;
* nouvelle source plus récente mais moins autoritaire ;
* override manuel ;
* résultat en conflit ;
* dates incompatibles ;
* coureur ambigu ;
* alias de course ;
* renommage commercial ;
* import identique rejoué ;
* import concurrent ;
* rollback transactionnel ;
* résolution manuelle.

## 21.3 Tests de migration

Créer des tests qui partent d’un état proche du schéma actuel et vérifient :

* conservation des coureurs ;
* conservation des équipes ;
* conservation des courses ;
* création correcte des séries ;
* conservation des résultats ;
* création des mappings legacy PCS ;
* fonctionnement des anciennes URLs ;
* absence de doublons.

## 21.4 Tests live

Couvrir :

* démarrage ;
* progression ;
* changement de groupe ;
* événement dupliqué ;
* arrivée ;
* provider principal indisponible ;
* fallback ;
* donnée périmée ;
* arrêt du polling ;
* rétention des snapshots ;
* notifications envoyées une seule fois.

## 21.5 Tests de non-régression réseau

Créer un test global qui échoue si une vue ou une API tente un accès réseau.

Les tests web doivent fonctionner avec toutes les variables provider désactivées.

---

# 22. Qualité du code

Ajouter et configurer :

```text
ruff
```

Exécuter au minimum :

```bash
ruff check .
python manage.py check
python manage.py makemigrations --check
pytest
```

Ne pas masquer les erreurs avec des `except Exception: pass`.

Lorsqu’un échec doit être toléré :

* capturer une exception ciblée ;
* journaliser le contexte ;
* renvoyer un résultat métier explicite ;
* conserver les dernières données valides.

Utiliser :

* annotations de types ;
* transactions ;
* contraintes de base ;
* indexes explicites ;
* services testables ;
* fonctions courtes ;
* noms indépendants d’un provider.

---

# 23. Commandes de gestion attendues

Créer :

```bash
python manage.py seed_road_series
python manage.py seed_national_championships
python manage.py list_providers
python manage.py provider_health --provider KEY
python manage.py sync_provider --provider KEY --year 2026
python manage.py sync_edition --edition UUID --provider KEY
python manage.py sync_live --stage UUID --provider KEY
python manage.py reconcile_mappings
python manage.py list_conflicts
python manage.py purge_provider_data --provider KEY --dry-run
```

Toutes les commandes doivent :

* retourner un code d’erreur correct ;
* fournir un résumé lisible ;
* supporter `--verbosity` ;
* être idempotentes lorsque pertinent ;
* ne pas masquer un échec provider.

---

# 24. Plan d’implémentation obligatoire

Réaliser la refonte en lots cohérents.

## Lot 0 — Audit et garde-fou

* analyser le dépôt ;
* écrire `docs/architecture/multi-provider.md` ;
* ajouter `PCS_LEGACY_ENABLED=false` ;
* empêcher tout nouvel appel PCS par défaut ;
* désactiver les tâches PCS existantes ;
* ajouter un test garantissant l’absence de requête PCS en configuration normale.

## Lot 1 — Domaine canonique

* introduire `RaceSeries` ;
* relier les `Race` existantes à une série ;
* ajouter UUID publics ;
* introduire aliases ;
* introduire `TeamIdentity` ;
* préparer les nouveaux champs d’étape et de résultat ;
* créer les migrations et tests de données.

## Lot 2 — Provider framework

* créer `providers` ;
* capacités ;
* registre ;
* modèles ;
* mappings ;
* snapshots ;
* santé ;
* exceptions ;
* clients HTTP sécurisés ;
* rate limiting ;
* circuit breakers ;
* tests de contrat.

## Lot 3 — Ingestion

* créer DTO ;
* validation ;
* identity resolver ;
* provenance ;
* moteur de fusion ;
* conflits ;
* orchestrateur ;
* tâches Celery ;
* commandes d’administration.

## Lot 4 — Seeds

* créer `road_series.yaml` ;
* implémenter `SeedProvider` ;
* créer les séries P0 à P3 ;
* générer les championnats nationaux ;
* vérifier l’idempotence.

## Lot 5 — Providers manuels et fixtures

* implémenter `ManualProvider` ;
* implémenter `FixtureProvider` ;
* démontrer une fusion multi-source ;
* démontrer un conflit ;
* démontrer un fallback live.

## Lot 6 — Bascule du catalogue

* remplacer les services PCS par l’ingestion ;
* rendre la recherche locale ;
* adapter les vues ;
* adapter l’admin ;
* adapter l’API ;
* maintenir les routes legacy.

## Lot 7 — Bascule du live

* créer snapshots et état canonique ;
* supprimer les refresh déclenchés par le front ;
* adapter les notifications ;
* rendre le polling adaptatif ;
* ajouter fallback et fraîcheur.

## Lot 8 — Migration legacy PCS

* créer les mappings legacy ;
* migrer les champs spécifiques ;
* supprimer les dépendances de bypass ;
* supprimer les appels runtime ;
* conserver uniquement les fixtures utiles.

## Lot 9 — Provider réel initial

Choisir le premier provider réel uniquement parmi les sources dont l’accès est explicitement autorisé et documenté.

Avant l’implémentation :

* créer sa documentation ;
* définir ses capacités ;
* définir ses limites ;
* ajouter ses fixtures ;
* exécuter les tests de contrat.

Ne pas bloquer toute la refonte si aucun provider externe légalement exploitable n’est disponible. Le système doit déjà être complet avec seed, manuel et fixtures.

## Lot 10 — Documentation et finalisation

* mettre à jour le README ;
* retirer la description « alternative basée sur PCS » ;
* documenter l’installation ;
* documenter l’ajout d’un provider ;
* documenter les commandes ;
* documenter les migrations ;
* documenter les limites ;
* mettre à jour Docker et `.env.example` ;
* exécuter tous les tests.

---

# 25. Compatibilité et stratégie de déploiement

Le déploiement doit pouvoir s’effectuer sans interruption destructive.

Prévoir :

1. déploiement des nouveaux modèles ;
2. exécution des migrations additives ;
3. seed des séries ;
4. migration des données legacy ;
5. activation des nouvelles lectures ;
6. vérification ;
7. désactivation des anciennes tâches ;
8. suppression du legacy lors d’un déploiement ultérieur.

Créer une documentation :

```text
docs/deployment/multi-provider-migration.md
```

Inclure :

* sauvegarde PostgreSQL ;
* commandes de migration ;
* contrôle des volumes ;
* rollback applicatif ;
* rollback des tâches ;
* vérifications post-déploiement ;
* procédure de réactivation temporaire de la lecture legacy locale, sans accès PCS.

---

# 26. Critères d’acceptation

La refonte n’est terminée que lorsque tous les points suivants sont vrais.

## Domaine

* une série et une édition sont deux entités distinctes ;
* les changements de sponsor sont gérés par alias ;
* les championnats nationaux sont générés pour les pays P1 et P2 ;
* les séries P0 à P3 sont seedées ;
* les données existantes sont conservées.

## Providers

* plusieurs providers peuvent coexister ;
* chaque provider déclare ses capacités ;
* un provider peut être désactivé ;
* les mappings sont persistés ;
* les snapshots sont persistés ;
* les conflits sont visibles ;
* les overrides manuels fonctionnent.

## Réseau

* aucune vue ne contacte de fournisseur ;
* aucune API ne contacte de fournisseur ;
* la recherche est locale ;
* le rate limiter est global ;
* les verrous sont distribués ;
* les `403` ne déclenchent aucun contournement ;
* les `429` respectent `Retry-After`.

## PCS

* `curl_cffi` supprimé ;
* `cloudscraper` supprimé ;
* plus d’impersonation ;
* plus de polling PCS ;
* plus de recherche PCS ;
* les identifiants PCS existants sont migrés en mappings legacy ;
* l’application fonctionne sans accès à `procyclingstats.com`.

## Live

* le live est stocké localement ;
* les snapshots ont une provenance ;
* le front affiche la fraîcheur ;
* le polling est adaptatif ;
* le fallback est testé ;
* les notifications restent dédupliquées.

## Qualité

* migrations propres ;
* tests verts ;
* aucune dépendance Internet dans les tests ;
* documentation à jour ;
* `ruff check .` passe ;
* `python manage.py check` passe ;
* `python manage.py makemigrations --check` passe ;
* `pytest` passe.

---

# 27. Méthode de travail attendue

Avant chaque lot :

1. examiner les fichiers concernés ;
2. identifier les dépendances ;
3. écrire ou adapter les tests ;
4. effectuer les migrations additives ;
5. implémenter ;
6. lancer les tests ciblés ;
7. lancer les contrôles globaux ;
8. documenter les décisions importantes.

Créer des commits cohérents par lot.

Ne pas regrouper toute la refonte dans un unique commit illisible.

Ne pas supprimer de code fonctionnel avant que son remplacement soit testé.

Ne pas demander de validation pour chaque décision mineure. Utiliser les choix définis dans ce document comme décisions par défaut.

Lorsqu’une hypothèse importante reste impossible à vérifier :

* choisir l’option la plus réversible ;
* l’isoler derrière une interface ou un feature flag ;
* la documenter ;
* continuer le reste de la refonte.

---

# 28. Rapport final demandé

À la fin, fournir :

```text
1. Résumé des changements
2. Architecture finale
3. Modèles ajoutés ou modifiés
4. Migrations réalisées
5. Providers implémentés
6. Providers préparés mais désactivés
7. Données legacy migrées
8. Appels PCS supprimés
9. Tests ajoutés
10. Résultats des commandes de validation
11. Limitations restantes
12. Prochain provider réel recommandé
13. Procédure exacte de déploiement
```

Mentionner honnêtement tout critère non rempli.

Ne jamais déclarer la refonte terminée si les tests, migrations ou contrôles ne passent pas.
