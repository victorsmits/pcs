# Déploiement — PCS Live (`pcs.victorsmits.com`)

Stack : **web** (gunicorn) + **worker** (Celery) + **beat** (planificateur) + **PostgreSQL** + **Redis**, derrière un reverse proxy externe qui termine le TLS.

## 1. Prérequis serveur
- Docker + Docker Compose.
- Un reverse proxy (nginx/Traefik/Caddy) qui :
  - pointe `pcs.victorsmits.com` vers le conteneur web (port `8800`),
  - termine le HTTPS et transmet l'en-tête `X-Forwarded-Proto: https`.

## 2. Configuration (`.env`)
Copier `.env.example` en `.env` et renseigner :
```
SECRET_KEY=<clé aléatoire forte>
DEBUG=False
ALLOWED_HOSTS=pcs.victorsmits.com,www.pcs.victorsmits.com
POSTGRES_PASSWORD=<mot de passe fort>
DOCKER_HUB_USERNAME=victorsmits
CURRENT_SEASON=2026

# Connexion admin via Google (optionnel mais recommandé)
GOOGLE_CLIENT_ID=<...>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<...>
ADMIN_EMAILS=victor.smits@shippingbo.com
```

### OAuth Google
Dans Google Cloud Console → *Credentials* → **OAuth client ID** (Web) :
- **Authorized redirect URI** : `https://pcs.victorsmits.com/accounts/google/login/callback/`

## 3. Build & démarrage
```bash
# Build de l'image (CSS Tailwind compilé + collectstatic inclus)
docker build -t victorsmits/pcs-live:latest .

# (optionnel) push vers le registre
# docker push victorsmits/pcs-live:latest

# Démarrage de la stack
docker compose -f docker-compose.prod.yml up -d
```
Au démarrage, le service **web** applique les migrations et initialise les
planifications (`setup_beat`). Les **statics** sont servis par WhiteNoise depuis
l'image (collectés au build).

## 4. Premier accès admin
- Via Google : `https://pcs.victorsmits.com/admin/login/` → « Se connecter avec Google »
  (l'email doit être dans `ADMIN_EMAILS` → devient automatiquement superuser).
- Ou créer un superuser classique :
  ```bash
  docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
  ```

## 5. Données initiales
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py sync_calendar
docker compose -f docker-compose.prod.yml exec web python manage.py live_discover
```
Ensuite, les tâches périodiques (worker + beat) prennent le relais :
- `live: poll sessions actives` — 15 s
- `live: découverte du jour` — 10 min
- `catalog: sync calendrier` — quotidien (nouvelles courses)
- `catalog: upgrade profils image` — 6 h

## 6. Supervision (admin)
- **Periodic tasks / Intervals / Crontabs** : planifications (modifiables, « Exécuter maintenant »).
- **Task results** : historique des exécutions.
- **Sessions live** : activer / suspendre.
- **Logs de synchronisation** : suivi des fetchs PCS.

## 7. Mise à jour
```bash
git pull
docker build -t victorsmits/pcs-live:latest .
docker compose -f docker-compose.prod.yml up -d
```

## Notes
- Données © ProCyclingStats — usage personnel.
- Le flux live repose sur le polling HTML de PCS ; un seul chemin de scraping
  (worker), throttle intégré, cache Redis.
