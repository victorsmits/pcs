# --- Étape 1 : build du CSS Tailwind ---
FROM node:20-slim AS cssbuilder
WORKDIR /app
COPY package.json package-lock.json* tailwind.config.js ./
RUN npm ci
COPY static ./static
COPY templates ./templates
RUN npm run build:css

# --- Étape 2 : dépendances Python ---
FROM python:3.13-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Étape 3 : image de production ---
FROM python:3.13-slim AS production
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
# nodejs : moteur JS de secours pour cloudscraper (curl_cffi reste prioritaire)
# tesseract-ocr : lecture de l'axe d'altitude des profils image (échelle en mètres)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl nodejs tesseract-ocr && rm -rf /var/lib/apt/lists/*

RUN groupadd -r django && useradd -r -g django django
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .
# CSS Tailwind compilé depuis l'étape 1 (écrase le fichier versionné)
COPY --from=cssbuilder /app/static/css/app.css ./static/css/app.css

RUN mkdir -p /app/staticfiles && python manage.py collectstatic --noinput \
    && chown -R django:django /app

USER django
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=30s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--worker-tmp-dir", "/tmp", "pcs_project.wsgi:application"]
