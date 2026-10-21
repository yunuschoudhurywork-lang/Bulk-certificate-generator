# Phase 2 Bulk Certificate Generation Implementation Review

API routes and integration tests for end-to-end certificate generation workflow. The implementation connects existing Phase 1 services (job management, PDF generation, Celery task orchestration) through three FastAPI endpoints: create job, get status, and download certificate. All 21 integration tests pass; 4 tests skipped pending Docker environment.

**Watch for:** Race condition between counter increment and job finalization (confirmed), computed field asymmetry in response schema (confirmed), absence of path traversal validation in download endpoint (confirmed).

**Verdict**: NEEDS_CHANGES

## High-level view

The three API endpoints wire directly to the existing service layer without introducing middleware or transformation logic. Job creation atomically writes both the job record and all certificate records in a single transaction, then queues the Celery task outside that transaction boundary. The computed fields for pending_count and progress_percentage derive values at serialization time from the counter columns, removing those columns from the database model and ensuring clients always see consistent calculations. The download endpoint constructs file paths by concatenating the storage base directory with the relative path from the certificate record; this is unsafe without validation because a malicious path value in the database could reach files outside the storage directory.

The Celery task uses atomic SQL UPDATE statements to increment completed_count and failed_count directly at the database level, preventing lost updates when multiple workers process certificates for the same job. Job finalization reads the current counters and writes the final status and completed_at timestamp, but the finalization logic runs *after* the last counter increment completes, creating a gap where a concurrent read could observe completed+failed < total with status already set to COMPLETED. This race is low-probability in the single-worker MVP but becomes a visible inconsistency under load.

Test coverage addresses all three endpoints, pagination, status filtering, and error cases (404s for missing resources, 422s for validation failures). The skipped tests target actual Celery task execution with database transactions, which requires the Docker environment and falls outside the scope of this unit-test-focused review pass. The tests use mocks appropriately: Celery task queueing is mocked to prevent worker spawning, but service and database calls execute normally against the test database, verifying the full stack below the Celery boundary.

<details>
<summary>Issues (5)</summary>

1. **BLOCKING — Path traversal in certificate download** — The download endpoint constructs `Path(settings.certificate_storage_path) / cert.file_path` without validating that the resolved path stays within the storage directory. A certificate record with file_path="../../../etc/passwd" would escape the storage boundary. Validate that `file_path.resolve()` starts with `storage_path.resolve()` before serving the file.

2. **BLOCKING — Race condition between counter increment and job finalization** — The Celery task increments completed_count or failed_count after processing each certificate, then finalizes the job status when all certificates are processed. Between the last increment commit and the finalization commit, a client reading the job sees (completed + failed) equal to total but status still "PROCESSING", or sees status "COMPLETED" but counters that don't sum to total. Finalize the job in the same transaction as the last counter update, or add a database check constraint.

3. **NON-BLOCKING — Computed field asymmetry in JobResponse** — pending_count and progress_percentage are @computed_field properties but still have type annotations in the field list. This creates confusion about whether they're settable or read-only. Remove them from the explicit field definitions; @computed_field alone is sufficient.

4. **NON-BLOCKING — Test database cleanup issue flagged but not fixed** — The verification report notes that 2 unit tests fail when run after integration tests due to database cleanup issues, dismissing this as "not a code defect." Isolation failures between test suites make tests nondeterministic. The conftest.py changes add savepoint-based isolation, but the failure pattern suggests some tests bypass this fixture. Investigate which tests fail and ensure the fixture covers all cases.

5. **NON-BLOCKING — Celery task route configuration adds no value** — The celery_app.py diff routes generate_certificates_for_job to queue "default", which is already the Celery default. This configuration is dead code. Remove it or document the intent (e.g., placeholder for future multi-queue routing).

</details>

<details>
<summary>Details</summary>

## Job creation and Celery task queueing

The POST /jobs endpoint accepts a CreateJobRequest containing 1-1000 recipients, validates the count against settings.max_recipients_per_job (returns 400 if exceeded), calls JobService.create_job_with_recipients to write the job and all certificate records atomically, then queues the Celery task with `generate_certificates_for_job.delay(str(job.id))`. The job write and task queue are separate operations: if the task queue fails, the job exists in the database with no worker processing it.

The validation check in the endpoint catches the max_recipients_per_job configuration value, which is distinct from the hard-coded Pydantic bound (max_length=1000). The error for exceeding the limit returns 400 Bad Request, but Pydantic's own bounds return 422 Unprocessable Entity. The test `test_create_job_exceeds_max_recipients` expects 422 because the test creates a request larger than the Pydantic max_length, hitting Pydantic validation before the endpoint's business rule check. If the Pydantic bound is raised above max_recipients_per_job, the test will break.

## Computed fields in JobResponse

The schema change converts pending_count and progress_percentage from stored fields to @computed_field properties. pending_count returns `self.total_recipients - self.completed_count - self.failed_count`. progress_percentage returns `(completed_count + failed_count) / total_recipients * 100`, rounded to two decimals, with a zero-check to avoid division by zero.

The schema still defines both fields with type annotations in the field list, creating asymmetry: they're computed but appear as if they're stored. This causes confusion about whether they're settable or read-only. All current code uses `JobResponse.model_validate(job)`, which works correctly, but manual construction with `model_construct(pending_count=10)` would fail because pending_count is no longer settable.

## Certificate listing with pagination and status filtering

The GET /jobs/{job_id}/certificates endpoint calls CertificateService.get_certificates_by_job with optional status filtering and pagination (limit, offset). The endpoint builds a download_url for each certificate only if its status is "SUCCESS"; otherwise download_url is None.

The endpoint verifies the job exists before querying certificates. If the job doesn't exist, it returns 404. If the job exists but has no certificates matching the status filter, the response returns an empty list with total=0.

## Certificate download and file serving

The GET /certificates/{cert_id}/download endpoint retrieves the certificate record, checks status == "SUCCESS", constructs the full file path as `Path(settings.certificate_storage_path) / cert.file_path`, verifies the file exists, and returns a FileResponse with media_type="application/pdf" and a Content-Disposition header containing a filename formatted as `{recipient_name_with_underscores}_{cert_id}.pdf`.

The file path construction `storage_path / cert.file_path` is unsafe. If cert.file_path contains path traversal sequences like "../../../etc/passwd", the resolved path escapes the storage directory. Python's Path / operator normalizes some traversal, but `Path("/data/certificates") / "../../../etc/passwd"` resolves to "/etc/passwd". The endpoint checks `file_path.exists()`, so an attacker who can control the file_path column in the database can read arbitrary files on the server. This is a **confirmed** path traversal vulnerability.

Mitigation: after constructing `file_path = storage_path / cert.file_path`, resolve both paths and verify the file path starts with the storage path:

```python
storage_path_resolved = storage_path.resolve()
file_path_resolved = file_path.resolve()
if not file_path_resolved.is_relative_to(storage_path_resolved):
    logger.error(f"Path traversal attempt: {cert.file_path}")
    raise HTTPException(status_code=404, detail="Certificate file not found on server")
```

The `is_relative_to` method was added in Python 3.9. This project uses Python 3.12, so it's available. Alternatively, check `str(file_path_resolved).startswith(str(storage_path_resolved))`, but `is_relative_to` is more robust against edge cases like trailing slashes and symlinks.

The filename sanitization replaces spaces with underscores (`safe_name = cert.recipient_name.replace(" ", "_")`), but does not remove or escape other characters that could break the Content-Disposition header (e.g., quotes, semicolons, backslashes). For a recipient_name like `John "Doe"; rm -rf /`, the header becomes `attachment; filename="John_"Doe";_rm_-rf_/_{cert_id}.pdf"`, which terminates the filename at the first unescaped quote. This is not a security issue (the filename is only metadata in the HTTP header, it doesn't affect the file served), but it breaks the download experience for edge-case names. A production implementation should use `werkzeug.utils.secure_filename` or a similar library to sanitize filenames, or percent-encode non-ASCII and special characters per RFC 6266.

## Celery task and atomic counter updates

The Celery task iterates through all PENDING certificates for the job, generates a PDF for each, and updates the certificate status and job counters. Counter updates use SQL UPDATE statements that increment the column value at the database level:

```python
db.execute(
    update(GenerationJob)
    .where(GenerationJob.id == job_uuid)
    .values(completed_count=GenerationJob.completed_count + 1)
)
```

This prevents lost updates under concurrent access. If two workers process certificates for the same job simultaneously, both can increment completed_count without conflict, because the database executes each increment atomically.

After processing all certificates, the task finalizes the job status by reading the current counters, determining the final status (COMPLETED, COMPLETED_WITH_ERRORS, or FAILED), and writing the status and completed_at timestamp. The finalization commit is separate from the last counter increment commit. Between the last `db.execute(update...)` commit and the finalization commit, the job's counters reflect a completed job (completed + failed = total), but the status is still "PROCESSING". A client reading the job during this window sees an inconsistent state. The gap is small (milliseconds), but it exists.

The race is **confirmed**: the task commits each counter increment immediately after processing a certificate, then finalizes the job in a separate transaction after the loop completes. The intermediate state is logically inconsistent (all work is done but status hasn't updated), but it doesn't break correctness (the job eventually reaches the correct final state). Mitigation: finalize the job in the same transaction as the last counter update, or add a database check constraint that enforces `status != 'COMPLETED' OR (completed_count + failed_count = total_recipients)`.

## Recipient-level failure isolation

The Celery task wraps each certificate's processing in a try/except block that catches all exceptions, marks the certificate as FAILED, increments the failed_count, and continues to the next certificate. The exception handler logs the error with `exc_info=True` to capture the full traceback.

The task also performs runtime validation of recipient data using `RecipientInput.model_validate()` before generating the PDF. If validation fails, the exception handler catches the ValidationError, marks the certificate as FAILED with error_message="Data validation failed: {details}", increments failed_count, and continues. This belt-and-suspenders approach catches edge cases like data corruption between API validation and task execution, or certificates created directly in the database for testing.

## Test coverage and skipped tests

The integration tests cover job creation with valid and invalid inputs, job status retrieval, certificate listing with pagination and status filtering, and certificate download for SUCCESS, PENDING, FAILED, and missing-file cases.

21 integration tests pass, 4 are skipped. The skipped tests require actual Celery task execution with database transactions, which depends on the Docker environment and a running Celery worker. The skipped tests cover failure isolation (one recipient fails, others succeed), all-failure cases, timestamp verification, and validation error handling at processing time.

The verification report notes that 2 unit tests fail when run after integration tests, but pass in isolation. This indicates a test isolation issue: integration tests leave database state behind that breaks unit tests. The conftest.py changes add savepoint-based isolation for async sessions, but the failure pattern suggests either some tests bypass this fixture or the savepoint mechanism doesn't fully isolate state. This is a **confirmed** test infrastructure issue.

## API contract and error handling

The three endpoints return appropriate HTTP status codes: 201 for job creation, 200 for retrieval/download, 400 for recipient count exceeding limit, 404 for missing resources, 422 for Pydantic validation failures.

The 404 responses include a detail message identifying what was not found. The download endpoint distinguishes between "certificate not found", "not available for download" (status != SUCCESS), and "file not found on server" (file missing from disk).

The job creation endpoint's validation error for exceeding max_recipients returns 400, but Pydantic validation errors return 422. This inconsistency is acceptable: 400 represents a business rule violation, 422 represents a data structure violation.

The certificate download endpoint returns 404 for PENDING and FAILED certificates with detail "Certificate {id} is not available for download (status: {status})". This message leaks the certificate's status to unauthenticated clients. If this API is public, a client can enumerate UUIDs and determine which certificates exist and their status.

## pyproject.toml dependency changes

The diff removes `psycopg2-binary==2.9.9` and adds `email-validator==2.2.0`. The psycopg2-binary removal is correct: the async FastAPI app uses asyncpg, and the Celery task converts the database URL at runtime to use psycopg2. However, the Celery task's URL conversion assumes the database URL starts with "postgresql+asyncpg://". If the URL format changes, the task's sync engine creation will break.

The email-validator addition is required by Pydantic's EmailStr type, which is used in RecipientInput. Pydantic 2.x requires email-validator to validate email fields. This dependency was missing, so EmailStr validation would fail at runtime. The addition fixes a **confirmed** missing dependency.

## Untracked files

The git status shows untracked workflow artifacts in `.agents/tasks/` (phase1-report.md, phase2-coder-verification.md, etc.). These document planning and verification steps but aren't required for the application to function. For this review, they're out of scope.

The untracked API route files (jobs.py, certificates.py) and test files are the core Phase 2 deliverables and should be committed.

</details>

<details>
<summary>File map</summary>

Modified files:
- `app/core/celery_app.py` — Added task_routes configuration (dead code: routes to default queue)
- `app/main.py` — Registered jobs and certificates routers with /api/v1 prefix
- `app/schemas/job.py` — Converted pending_count and progress_percentage to @computed_field properties
- `pyproject.toml` — Removed psycopg2-binary, added email-validator
- `tests/conftest.py` — Added savepoint-based transaction isolation fixture for async sessions
- `tests/unit/test_file_manager.py` — Updated filename sanitization test expectations
- `tests/unit/test_pdf_generator.py` — Fixed invalid output path test to use a reliably failing scenario

New files:
- `app/api/routes/jobs.py` — POST /jobs, GET /jobs/{id}, GET /jobs/{id}/certificates
- `app/api/routes/certificates.py` — GET /certificates/{id}/download
- `tests/integration/test_api_jobs.py` — 12 tests for job creation, retrieval, certificate listing
- `tests/integration/test_api_certificates.py` — 6 tests for certificate download
- `tests/integration/test_workflow.py` — 3 active + 4 skipped end-to-end workflow tests
- `tests/unit/test_certificate_service.py` — 10 tests for CertificateService
- `tests/unit/test_job_service.py` — 12 tests for JobService

Full diff: `git diff HEAD` (staged and unstaged changes)

</details>
