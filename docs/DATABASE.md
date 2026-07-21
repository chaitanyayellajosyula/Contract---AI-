# Database Plan

## Development Database

- SQLite is used for local development
- Database file location: database/app.db
- Alembic manages future schema changes

## Migration Strategy

- Use Alembic revision files for all schema changes
- Keep model definitions aligned with migration files
- Avoid direct manual database editing in development
