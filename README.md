# HikePlanner
Noah Bogonoa | bogonoa1 | ZHAW FS2026

Schätzt die Gehzeit einer Wanderung basierend auf Distanz und Höhenmetern.
Inspiriert von: https://blog.mimacom.com/data-collection-scrapy-hiketime-prediction/

## Daten
* Rohdaten: https://www.kaggle.com/datasets/roccoli/gpx-hike-tracks
* GPX-Tracks von hikr.org
* Bereinigung und Feature-Extraktion mit gpxpy

## Dependency Management
* `pyproject.toml` mit allen Dependencies
* `uv.lock` für reproduzierbare Builds
* Python 3.13.7 (pinned)

## Pipeline (GitHub Actions)
1. Rohdaten von Azure Blob Storage herunterladen
2. GPX-Tracks bereinigen (collect-curate.py)
3. Features extrahieren und in MongoDB laden (transform-validate.py)
4. Modell trainieren und in Azure Blob Storage speichern (train_model.py)
5. Docker Image bauen und auf Azure deployen

## Training & Modell
* Linear Regression (Baseline)
* GradientBoostingRegressor (Default)
* GradientBoostingRegressor (Tuned) — GridSearchCV Hyperparameter-Tuning
* RandomForestRegressor (Tuned) — GridSearchCV Hyperparameter-Tuning
* Bestes Modell wird automatisch ausgewählt und deployed

## App
* Backend: Python Flask (`backend/app.py`)
* Frontend: SvelteKit (`frontend/`)
* 4 Zeitschätzungen: GBR, Linear Regression, DIN33466, SAC
* Bonus: Interaktive Leaflet-Karte mit Open-Meteo API für Höhenmeter

## Deployment
* Docker Container
* GitHub Container Registry (GHCR)
* Azure App Service (Linux, F1)
* Automatisches Deployment via GitHub Actions

## Installation (lokal)
* `uv venv .venv`
* `uv sync`
* Frontend build: `cd frontend && npm install && npm run build`
* Backend starten: `uv run flask --app backend/app.py run`

## Azure Blob Storage
* Modell wird versioniert gespeichert (`hikeplanner-model-{version}`)
* Verbindung via `AZURE_STORAGE_CONNECTION_STRING`
* Als Umgebungsvariable für Docker und als Secret für GitHub Actions