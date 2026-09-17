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
