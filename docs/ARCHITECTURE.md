# Architecture Overview

## Backend

The backend uses FastAPI with a modular package layout under backend/app. Modules are separated by responsibility:
- api: routing entry points
- core: shared configuration and application wiring
- models: SQLAlchemy models
- schemas: request and response validation models
- services: business logic
- repositories: persistence abstraction
- connectors: third-party integration points
- utils: shared helper functions

## Frontend

The frontend uses React with TypeScript and Vite, organized into reusable UI, page, layout, hook, service, and type modules.

## Data Layer

SQLite is configured for development, and Alembic is initialized for future schema migrations.
