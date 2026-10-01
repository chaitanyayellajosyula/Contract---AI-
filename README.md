# Contract Hunter AI

Contract Hunter AI is a full-stack SaaS foundation for contract intelligence workflows, recruiting operations, and sourcing automation. The repository is currently focused on a professional engineering baseline so the product can grow in a structured and maintainable way.

## What this repository contains

- A modular FastAPI backend foundation with package separation for API, core, models, schemas, services, repositories, connectors, and utilities
- A React + TypeScript + Vite + Tailwind frontend scaffold for future interface development
- Comprehensive documentation for product direction, architecture, database strategy, delivery planning, and engineering standards
- SQLAlchemy and Alembic scaffolding for future persistence layers
- Container and CI starter configuration for local and automated validation

## Repository layout

- backend/: application and service infrastructure
- frontend/: UI foundation and client-side structure
- docs/: product, architecture, database, sprint, and engineering design documents
- plugins/: extension point for future integrations
- database/: database configuration and migration assets
- tests/: test infrastructure placeholder
- docker/: containerization support
- .github/: CI workflow foundation
- assets/, scripts/, config/, logs/: operational scaffolding for future growth

## Current scope

This phase intentionally includes only project foundation work:
- repository structure and module boundaries
- starter backend and frontend configuration
- connector and model architecture placeholders
- documentation and engineering governance files

No business logic, no scraper implementation, no connector execution paths, and no UI workflows are implemented yet.

## Getting started

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose -f docker/docker-compose.yml up
```

### Automatic ingestion

- `AUTOMATIC_INGESTION_ENABLED` defaults to `false` and enables scheduled ingestion for discovered ATS sources.
- `AUTOMATIC_INGESTION_MAX_SOURCES_PER_RUN` defaults to `10`; `AUTOMATIC_INGESTION_MAX_JOBS_PER_SOURCE` defaults to `100`.
- `AUTOMATIC_INGESTION_TIMEOUT_SECONDS` defaults to `30`.
- `AUTOMATIC_INGESTION_FAILURE_THRESHOLD` defaults to `3`. Reaching it starts a temporary cooldown; successful recovery resets failures and clears the cooldown.
- `AUTOMATIC_INGESTION_HEALTH_COOLDOWN_SECONDS` defaults to `3600` and controls the wait before an unhealthy discovered source can be tried again.

## Project status

The foundation is ready for the next stage of implementation, including domain modeling, API route design, and connector integration architecture.
