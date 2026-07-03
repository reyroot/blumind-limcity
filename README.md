# Limcity

Backend API for **Limcity**, a smart-city waste management platform. Citizens report
waste via WhatsApp (image + GPS); reports are classified with AI and stored as
geo-referenced data to power heatmaps for public/private waste-management optimization.

Context: Entra21 graduation project — Blumenau, SC, Brazil.

## Tech Stack

- **FastAPI** (Python 3.10+)
- **PostgreSQL + PostGIS** (geospatial)
- **SQLAlchemy 2.0 (async)** + **GeoAlchemy2**
- **Pydantic v2**
- **Meta WhatsApp Cloud API** webhooks
- Pluggable **AI waste classifier** (Strategy Pattern)

## Getting Started

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn main:app --reload
```

Copy `.env.example` to `.env` and fill in the values.

## Development

```bat
ruff check .
ruff format .
mypy .
pytest -q
```

## CI

Every push and pull request to `main` runs lint (ruff), type-checking (mypy),
and tests (pytest) via GitHub Actions across Python 3.11 and 3.12.
See `.github/workflows/ci.yml`.
