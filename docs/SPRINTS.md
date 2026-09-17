# Sprint Plan

## Sprint 1 - Foundation

- Create repository structure
- Initialize backend and frontend foundations
- Add documentation and project setup files
- Prepare database and CI scaffolding

## Future Sprints

- Domain modeling and API design
- Authentication and users
- Contract ingestion and processing workflows
- Integrations and analytics

## Sprint 6.6 - Candidate Submission Workflow

- Add company-scoped submissions linking candidates to jobs
- Enforce recruiter ownership and company-admin visibility boundaries
- Support submission status progression and duplicate prevention

## Sprint 6.7 - Submission Review Workspace & Controlled Lifecycle

- Add filtered submission review for recruiters and company admins
- Enforce controlled submission status transitions
- Record authorized submission status history
- Integrate authenticated submission review in the frontend

## Sprint 6.8 - Job Ingestion & Discovery

- Add public job-source ingestion with normalized Greenhouse job data
- Preserve source identity and skip duplicate jobs during repeated ingestion
- Add source metadata, posted dates, source links, and ingestion outcome reporting
- Support job discovery filters, viewed/bookmarked filters, deterministic pagination, and posted-date ordering
- Display ingested job source and posted-date information in the jobs workspace

## Sprint 6.9 - Multi-Source Ingestion Foundation

- Add an approved source registry with configurable Greenhouse board identifiers and enabled state
- Support idempotent multi-board ingestion with updates for changed source jobs
- Persist ingestion run status, counts, timestamps, and error messages for future scheduler integration
- Keep scheduled execution out of scope while exposing a reusable ingestion service boundary

## Sprint 6.10 - Scheduled Ingestion Foundation

- Add a testable scheduler service that invokes the existing IngestionService for enabled registry configurations
- Use a configurable daily default of 5:00 AM in `America/New_York`, with explicit timezone-aware schedule calculations
- Isolate source failures and prevent overlapping runs for the same source configuration with process-local locks
- Keep scheduler startup integration as an explicit service boundary; no scheduler runs during application import
- Configure `SCHEDULER_ENABLED`, `SCHEDULER_HOUR`, `SCHEDULER_MINUTE`, and `SCHEDULER_TIMEZONE` through environment settings
- The process-local overlap protection is not a distributed lock and requires a single scheduler process in production
- A future deployment can call `run_if_due` from a dedicated worker, cron wrapper, or managed job process without changing ingestion logic
- LinkedIn scraping, browser automation, and paid APIs remain intentionally out of scope
