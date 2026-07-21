# Engineering Rules

## Code organization

- Keep backend modules separated by responsibility.
- Use clear package boundaries for API, core, models, schemas, services, repositories, connectors, and utilities.
- Keep the frontend structure aligned with components, pages, layouts, hooks, services, and types.

## Scope discipline

- Do not implement business logic in this foundation phase.
- Do not add connector execution paths until the architecture is approved.
- Do not add feature workflows to the UI before the base structure is stable.

## Documentation expectations

- Update relevant documentation whenever the architecture changes.
- Keep module-level intent clear so new contributors can understand the project quickly.

## Quality bar

- Ensure new files are consistent with the repository conventions.
- Keep starter code simple, explicit, and easy to extend.
