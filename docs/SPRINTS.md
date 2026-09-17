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

## Sprint 6.11 - Multi-Source Public Job Connectors

- Support Greenhouse boards and Lever public job postings through the approved source registry
- Greenhouse uses the public boards API: `https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true`; no credentials are required
- Lever uses the public postings API: `https://api.lever.co/v0/postings/{site}?mode=json`; no credentials are required
- Configure sources by registering a board or site with its source name, identifier, enabled state, connector type, and optional source settings
- Both connectors preserve stable source job IDs, source URLs, titles, descriptions, locations, employment information when supplied, and publication timestamps when supplied
- Public endpoint availability, response shape, and usage limits remain source-specific; clients should use responsible request rates and avoid aggressive parallel fetching
- All sources use the existing IngestionService, source-plus-job-ID idempotency, update behavior, and ingestion audit records
- LinkedIn scraping, authentication bypass, browser automation, paid APIs, and credential storage are intentionally excluded
- Cross-source duplicate merging is deferred; the same posting from different sources remains as separate source records

## Sprint 6.12 - Job Source Expansion & Production Source Configuration

- Add Ashby public job-board ingestion alongside Greenhouse and Lever
- Supported public source types are Greenhouse boards, Lever sites, and Ashby board slugs
- Configure additional real public boards/sites with `GREENHOUSE_BOARDS`, `LEVER_SITES`, and `ASHBY_BOARDS` as comma-separated environment values; Stripe Greenhouse remains the only built-in default
- Ashby uses `https://api.ashbyhq.com/posting-api/job-board/{board}` without credentials; Lever and Greenhouse remain unauthenticated public endpoints documented in Sprint 6.11
- Preserve source URLs, apply URLs, source timestamps, source metadata, stable external IDs, idempotent updates, and ingestion audit records
- Engagement labels are normalized only from explicit source fields, including contract, contract-to-hire, C2C, W2, full-time, part-time, and internship where supplied; values are never inferred from generic descriptions
- The existing scheduler discovers all enabled registry configurations, invokes the existing IngestionService, and retains per-source isolation and overlap locking
- Public endpoint response shapes and usage limits remain source-specific; configurations should use valid public boards and responsible request rates
- LinkedIn scraping, browser automation, authentication bypass, paid APIs, credential storage, and fake/demo job data are not implemented
- Cross-source duplicate merging remains intentionally deferred

## Sprint 7.0 - Job Hunter Dashboard & Opportunity Workflow

- Add a recruiter-focused Job Hunter workspace with newest-first opportunities, compact rows, freshness indicators, and a detail panel
- Support server-side keyword, engagement, work arrangement, location, company, source, freshness, and paginated listing filters
- Add authenticated per-user viewed, saved, and hidden workflow state without making status global across users
- Preserve source and external job identifiers as the primary duplicate identity; fuzzy cross-source merging remains out of scope
- Keep source/application links external and explicit, with source metadata and descriptions available in the detail view
- Existing ingestion, audit, source registry, scheduler, authorization, and submission workflows remain unchanged
- Limitations: list pagination uses response metadata headers, and frontend status actions require an authenticated session

## Sprint 8.1 - Automatic Source Discovery Foundation

- Add a bounded, persisted source discovery service for explicit Greenhouse, Lever, and Ashby board candidates
- Validate each candidate through its official public jobs endpoint before registering it as ingestion-eligible
- Persist discovered board identity, endpoint, company/source metadata, validation state, timestamps, eligibility, and rejection reason
- Persist discovery-run audit counts for candidates, discovered, validated, and rejected sources
- Promote validated boards into the existing source registry so the existing IngestionService and scheduler perform ingestion without duplicated persistence logic
- Configure deployment-provided candidates through `DISCOVERY_CANDIDATES` as a bounded JSON list; no arbitrary website crawling or fictional default boards are added
- Scheduled cycles attempt discovery before normal source ingestion when candidates are configured, while preserving disabled-scheduler behavior, per-source locks, and failure isolation
- Manual callers can invoke `SourceDiscoveryService.discover(...)`; no new public endpoint or authorization surface was added in this slice
- Requests are limited to 25 candidates per discovery run and use the connectors' existing bounded public endpoint timeouts
- LinkedIn scraping, browser automation, authentication bypass, CAPTCHA/rate-limit/robots circumvention, and credentialed sources remain excluded

## Sprint 8.2 - Compliant Automatic Discovery Providers

- Add a provider abstraction for bounded public ATS board enumeration
- Add a disabled-by-default `PublicJsonCatalogProvider` that reads an explicitly configured HTTPS JSON catalog from an allowlisted host
- Catalog entries are accepted only for Greenhouse, Lever, or Ashby and only when their jobs endpoint uses the corresponding official ATS domain/path
- Every provider candidate still passes the existing connector-backed public endpoint validation before persistence and SourceRegistry promotion
- Persist provider provenance, discovery keys, provider metadata, duplicate counts, provider results, failed providers, and discovery duration
- Merge the same ATS source/identifier across providers into one discovered source record
- Scheduled discovery runs before normal ingestion when automatic discovery is explicitly enabled and configured; provider failure does not stop configured-source ingestion
- No reliable official board-directory enumeration endpoint was found for Greenhouse, Lever, or Ashby, so no ATS crawler or search-engine scraping was introduced
- Explicit `DISCOVERY_CANDIDATES` remains supported and is the recommended path until a trusted public catalog is configured
- LinkedIn scraping, browser automation, arbitrary crawling, authentication bypass, CAPTCHA/robots/rate-limit circumvention, and uncontrolled network discovery remain excluded

## Sprint 8.2 Provider Extension - Verified ATS Company Catalog

- Add `AtsCompanyCatalogProvider` for the third-party `kalil0321/ats-scrapers` company directory
- The provider fetches only `https://storage.stapply.ai/jobhive/v1/manifest.json` and its Greenhouse, Lever, and Ashby CSV directory URLs
- Allowed catalog hosts are `storage.stapply.ai`, `raw.githubusercontent.com`, and `github.com`; candidate source URLs must use the official ATS hosts
- Configure with `ATS_CATALOG_DISCOVERY_ENABLED=false` and `ATS_CATALOG_MANIFEST_URL=https://storage.stapply.ai/jobhive/v1/manifest.json`
- The catalog is discovery-only seed data, not official ATS data; every row still passes existing official connector validation before eligibility, registry promotion, or ingestion
- The repository is MIT licensed, but the third-party dataset's separate licensing/provenance should be treated cautiously and is not copied into this repository
- Provider defaults cap each ATS directory at 25 rows per run, reject malformed/unsupported/duplicate rows, enforce response size and timeout limits, and preserve provider provenance

## Sprint 8.3 - Controlled Automatic Ingestion

- Connect validated discovery-promoted sources to the existing scheduler and IngestionService
- Keep automatic ingestion disabled by default with `AUTOMATIC_INGESTION_ENABLED=false`
- Configure `AUTOMATIC_INGESTION_MAX_SOURCES_PER_RUN=10`, `AUTOMATIC_INGESTION_MAX_JOBS_PER_SOURCE=100`, and `AUTOMATIC_INGESTION_TIMEOUT_SECONDS=30`
- Run explicit/configured sources through their existing scheduler path, then select only validated active discovered sources not already configured explicitly
- Select discovered sources deterministically by most recently validated timestamp and prevent duplicate source selection
- Preserve official Greenhouse, Lever, and Ashby connector validation, source-plus-job identity, idempotency, updates, ingestion audit, and per-source failure isolation
- Automatic ingestion never reads jobs from the third-party catalog directly; catalog entries remain discovery-only seeds
- Discovery runs record automatic-ingestion selected, succeeded, and failed counts when a discovery run is present
- No frontend changes, LinkedIn scraping, browser automation, arbitrary crawling, or unofficial ATS access were added
