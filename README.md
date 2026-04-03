# 🚴 CycloStats

Application Django complète pour le cyclisme professionnel, alternative à [procyclingstats.com](https://www.procyclingstats.com), basée sur [pcs-scraper](https://pypi.org/project/pcs-scraper/).

## Fonctionnalités

- **Coureurs** — Profils, historique de carrière, comparaison, statistiques par saison
- **Courses** — Résultats GC, étapes, calendrier interactif, palmarès
- **Équipes** — Effectifs, résultats par saison
- **Classements** — UCI/PCS individuels et par équipes
- **Recherche** — Autocomplétion globale
- **API REST** — Endpoints JSON complets (DRF)
- **Admin** — Interface Django admin complète
- **Sync** — Commande de synchronisation via pcs-scraper

## Installation rapide

```bash
# 1. Créer un environnement virtuel
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer l'environnement
copy .env.example .env      # Windows
# cp .env.example .env      # Linux/macOS

# 4. Migrations
python manage.py makemigrations riders races teams rankings core
python manage.py migrate

# 5. Créer un superutilisateur
python manage.py createsuperuser

# 6. Lancer le serveur
python manage.py runserver
```

Accéder à : http://127.0.0.1:8000/

## Synchronisation des données

```bash
# Importer toutes les courses et équipes d'une saison
python manage.py sync_data --year 2024 --type all

# Importer des coureurs spécifiques
python manage.py sync_data --type riders --slugs tadej-pogacar remco-evenepoel jonas-vingegaard

# Importer les équipes seulement
python manage.py sync_data --year 2024 --type teams

# Importer les courses seulement
python manage.py sync_data --year 2024 --type races
```

## API REST

Documentation interactive disponible sur `/api/`

Endpoints principaux :
- `GET /api/riders/` — Liste des coureurs
- `GET /api/riders/{id}/` — Détail coureur
- `GET /api/riders/{id}/results/` — Résultats d'un coureur
- `GET /api/races/` — Liste des courses
- `GET /api/races/{id}/results/` — Résultats d'une course
- `GET /api/teams/` — Liste des équipes
- `GET /api/results/` — Tous les résultats

## Structure du projet

```
pcs/
├── core/          # Vues principales, API, services communs
├── riders/        # Coureurs, résultats, statistiques
├── races/         # Courses, étapes, listes de départ
├── teams/         # Équipes, effectifs
├── rankings/      # Classements UCI/PCS
├── templates/     # Templates HTML (Bootstrap 5)
├── static/        # CSS/JS personnalisés
└── pcs_project/   # Configuration Django
```

## Technologies

- Django 4.2
- pcs-scraper 0.2.0
- Django REST Framework
- Bootstrap 5 + Bootstrap Icons
- Chart.js
- FullCalendar.js
- BeautifulSoup4

## Licence

Usage personnel et éducatif uniquement. Données © procyclingstats.com.
