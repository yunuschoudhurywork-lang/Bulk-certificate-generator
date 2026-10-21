# Phase 2 Completion Report: Bulk Certificate Generator API & Asynchronous Processing

**Date:** October 21, 2026  
**Status:** COMPLETE ✓  
**Test Suite:** 74 passed, 4 skipped, 0 failed, 0 errors (75% overall coverage)  
**Branch:** `feat/infrastructure-setup`

---

## 1. Executive Summary

Phase 2 implementation for the Bulk Certificate Generator is complete. The system connects the Phase 1 domain layer (job management, PDF generator, file manager) to a production-ready FastAPI application and an asynchronous Celery background task processing pipeline.

Key achievements:
- **API Endpoints:** Implemented and verified all core REST endpoints (`POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs/{id}/certificates`, and `GET /api/v1/certificates/{id}/download`).
- **Asynchronous Execution:** Celery background worker integrated with Redis broker, automatically importing and processing bulk certificate generation jobs.
- **Security Protections:** Confirmed and verified path traversal vulnerability remediation in the download endpoint with automated test coverage.
- **Concurrency & Race Conditions:** Atomic database counter increments and transactional `db.refresh(job)` prior to job finalization eliminate lost updates and status-counter discrepancies.
- **End-to-End Verification:** Verified live asynchronous workflow from job submission through Redis queueing, background worker PDF generation, progress polling, and binary PDF download.

---

## 2. Implemented Functionality

### 2.1 API Endpoints (`app/api/routes/`)

1. **`POST /api/v1/jobs`** (`app/api/routes/jobs.py`):
   - Accepts a batch of 1 to 1,000 recipients (`RecipientInput`).
   - Validates batch constraints against `settings.max_recipients_per_job` and Pydantic rules.
   - Atomically writes the `GenerationJob` and associated `CertificateRecord` rows using `JobService.create_job_with_recipients`.
   - Dispatches background generation via `generate_certificates_for_job.delay(str(job.id))`.
   - Returns HTTP 201 with job ID, initial `PENDING` status, and recipient counts.

2. **`GET /api/v1/jobs/{job_id}`** (`app/api/routes/jobs.py`):
   - Retrieves real-time status and progress for a generation job.
   - Automatically computes `pending_count` and `progress_percentage` via Pydantic `@computed_field`.
   - Returns 404 if the job UUID does not exist.

3. **`GET /api/v1/jobs/{job_id}/certificates`** (`app/api/routes/jobs.py`):
   - Lists certificate records belonging to a job.
   - Supports status filtering (`PENDING`, `SUCCESS`, `FAILED`) and pagination (`limit`, `offset`).
   - Generates download URLs dynamically for certificates in `SUCCESS` status (`/api/v1/certificates/{id}/download`).

4. **`GET /api/v1/certificates/{certificate_id}/download`** (`app/api/routes/certificates.py`):
   - Serves generated certificate PDF files with `media_type="application/pdf"`.
   - Sets `Content-Disposition` header with a sanitized filename (`Recipient_Name_{id}.pdf`).
   - Enforces status verification: only certificates with `status == "SUCCESS"` can be downloaded.
   - Validates that the resolved file path is strictly contained within `settings.certificate_storage_path` to prevent path traversal attacks.

### 2.2 Asynchronous Background Processing (`app/tasks/generate.py`)

- **Worker Task:** `generate_certificates_for_job` processes all `PENDING` certificate records for a job.
- **Recipient-Level Failure Isolation:** Individual recipient errors (e.g. malformed data or PDF rendering exceptions) are caught, marked as `FAILED` with truncated error diagnostics, and do not fail the overall batch.
- **Atomic Counter Updates:** Uses direct database-level SQL atomic updates (`update(GenerationJob).values(completed_count=GenerationJob.completed_count + 1)`) to avoid lost updates under concurrent access.
- **Job Status Finalization:** Sets final status to `COMPLETED` (100% success), `COMPLETED_WITH_ERRORS` (partial success), or `FAILED` (0% success), with timestamps recorded.
- **Celery Task Discovery:** Configured `imports=["app.tasks.generate"]` in `app/core/celery_app.py` ensuring the worker discovers the generation task upon startup.

---

## 3. Security Fixes & Vulnerability Review

### 3.1 Path Traversal Vulnerability Fix

- **Vulnerability:** The certificate download endpoint originally constructed file paths by joining the base storage path with `cert.file_path` without checking if the target escaped the storage directory.
- **Fix Applied:**
  ```python
  storage_path_resolved = storage_path.resolve()
  file_path_resolved = file_path.resolve()
  
  if not file_path_resolved.is_relative_to(storage_path_resolved):
      logger.error(f"Path traversal attempt detected: {cert.file_path}")
      raise HTTPException(
          status_code=404,
          detail="Certificate file not found on server"
      )
  ```
- **Verification & Test Coverage:**
  - Added `test_download_certificate_path_traversal_prevention` in `tests/integration/test_api_certificates.py`.
  - Simulates a malicious relative path (`../secret.txt`) outside storage; confirms 404 response without leaking server files.

### 3.2 Counter & Job Finalization Race Condition Fix

- **Issue:** A race condition could exist where concurrent readers saw counters reach `total_recipients` while the job status remained `PROCESSING`, or observed inconsistent intermediate counter values.
- **Fix Applied:**
  - Atomic SQL increments (`update(GenerationJob)...`) increment counters at the database level.
  - Added `db.refresh(job)` immediately prior to reading counter values and determining final status, guaranteeing that the committed counter values are evaluated within the transaction that commits the final status.
- **Verification:** Unit tests (`test_increment_completed`, `test_increment_failed`, `test_finalize_job_status_*`) and end-to-end integration runs verify accurate final status and counters.

### 3.3 Safe Resource Access & Missing Resource Handling

- Missing job UUID: Returns 404 with `"Job {job_id} not found"`.
- Missing certificate UUID: Returns 404 with `"Certificate {cert_id} not found"`.
- In-progress / Failed certificate: Returns 404 with `"Certificate {cert_id} is not available for download"`.
- Missing file on filesystem: Returns 404 with `"Certificate file not found on server"`.

---

## 4. Test Suite Results

### 4.1 Complete Test Suite Execution

**Command:**
```powershell
.venv\Scripts\python -m pytest -v
```

**Results:**
- **Total Tests:** 78
- **Passed:** 74
- **Skipped:** 4
- **Failed:** 0
- **Errors:** 0
- **Overall Code Coverage:** 75%
- **Execution Time:** ~6.35s

### 4.2 Breakdown by Test Suite

| Test Suite | File | Passed | Skipped | Failed | Errors |
|------------|------|--------|---------|--------|--------|
| Unit: File Manager | `tests/unit/test_file_manager.py` | 19 | 0 | 0 | 0 |
| Unit: PDF Generator | `tests/unit/test_pdf_generator.py` | 11 | 0 | 0 | 0 |
| Unit: Job Service | `tests/unit/test_job_service.py` | 12 | 0 | 0 | 0 |
| Unit: Certificate Service | `tests/unit/test_certificate_service.py` | 10 | 0 | 0 | 0 |
| Integration: API Jobs | `tests/integration/test_api_jobs.py` | 12 | 0 | 0 | 0 |
| Integration: API Certificates | `tests/integration/test_api_certificates.py` | 7 | 0 | 0 | 0 |
| Integration: Workflow | `tests/integration/test_workflow.py` | 3 | 4 | 0 | 0 |
| **Total** | | **74** | **4** | **0** | **0** |

---

## 5. Inspection of Skipped Tests & Prerequisites

Four tests in `tests/integration/test_workflow.py` are currently marked with `@pytest.mark.skip`:
1. `test_workflow_with_one_failure`
2. `test_workflow_all_failures`
3. `test_workflow_job_finalization_timestamps`
4. `test_workflow_validation_error_handling`

### Prerequisites Identified:
1. **Committed Database Records:**
   - The test fixture `db_session` in `tests/conftest.py` wraps every test in an uncommitted outer transaction with savepoints to enable automatic rollback.
   - However, `generate_certificates_for_job` uses a synchronous SQLAlchemy session (`SyncSessionLocal`) with a separate connection to PostgreSQL.
   - Under PostgreSQL's default `READ COMMITTED` transaction isolation, uncommitted rows created by `db_session` are invisible to `SyncSessionLocal`.
   - Therefore, executing the Celery task requires records to be committed to the database, requiring an un-isolated database session with explicit post-test table cleanup (e.g. `clean_test_db.py`).
2. **Asynchronous Services (Redis & Celery):**
   - Requires Redis running on port 6379 as the Celery message broker and result backend.
   - Requires Celery worker running with `-P solo` on Windows (or standard prefork inside Docker/Linux).
3. **Environment Parity in Docker:**
   - The Docker image requires `email-validator` and `psycopg2-binary` (rebuilt and verified).

---

## 6. Live End-to-End Workflow Verification

The end-to-end workflow was verified live against running PostgreSQL, Redis, and a background Celery worker using `test_e2e_live.py`.

### Execution Trace & Timeline:

1. **Job Submission:**
   - Request sent: `POST /api/v1/jobs` with 3 recipients (Grace Hopper, Alan Turing, Ada Lovelace).
   - Response: HTTP 201 Created. Job ID: `0890bf40-a268-4192-bd23-e4fa290a21c3`, status `PENDING`.
2. **Asynchronous Processing:**
   - Celery worker received the task from Redis and executed `generate_certificates_for_job`.
   - Polling `GET /api/v1/jobs/0890bf40-a268-4192-bd23-e4fa290a21c3`:
     - Initial: `PENDING | Completed: 0 | Failed: 0 | Progress: 0.0%`
     - Transitioned to: `COMPLETED | Completed: 3 | Failed: 0 | Progress: 100.0%` in **1.04s**.
3. **Certificate Listing:**
   - Request sent: `GET /api/v1/jobs/0890bf40-a268-4192-bd23-e4fa290a21c3/certificates`.
   - Response: Total 3 certificates in `SUCCESS` status, each with a valid download URL.
4. **PDF Retrieval & Binary Verification:**
   - Downloaded Grace Hopper certificate: 2,126 bytes PDF (`attachment; filename="Grace_Hopper_7c5f14e5-d847-4a30-b5a4-a163960ae520.pdf"`).
   - Downloaded Alan Turing certificate: 2,126 bytes PDF (`attachment; filename="Alan_Turing_f8a1fef6-85f4-483d-9725-b544f99ddc44.pdf"`).
   - Downloaded Ada Lovelace certificate: 2,123 bytes PDF (`attachment; filename="Ada_Lovelace_d3875b2c-faff-4f5d-b14c-6bb99f4f7a33.pdf"`).
   - Verified `%PDF-1.4` headers, valid PDF structures, and correct MIME types.

---

## 7. API Examples

### 7.1 Create Job
```http
POST /api/v1/jobs
Content-Type: application/json

{
  "recipients": [
    {
      "name": "Jane Doe",
      "email": "jane@example.com",
      "course": "Full Stack Engineering",
      "completion_date": "2024-05-15"
    }
  ]
}
```
**Response (201 Created):**
```json
{
  "job_id": "87d0f08c-0328-40d6-b9ec-ef6281f7a2f4",
  "status": "PENDING",
  "total_recipients": 1,
  "completed_count": 0,
  "failed_count": 0,
  "pending_count": 1,
  "progress_percentage": 0.0,
  "created_at": "2026-10-21T22:08:05.076Z",
  "started_at": null,
  "completed_at": null
}
```

### 7.2 Get Job Status
```http
GET /api/v1/jobs/87d0f08c-0328-40d6-b9ec-ef6281f7a2f4
```
**Response (200 OK):**
```json
{
  "job_id": "87d0f08c-0328-40d6-b9ec-ef6281f7a2f4",
  "status": "COMPLETED",
  "total_recipients": 1,
  "completed_count": 1,
  "failed_count": 0,
  "pending_count": 0,
  "progress_percentage": 100.0,
  "created_at": "2026-10-21T22:08:05.076Z",
  "started_at": "2026-10-21T22:08:05.500Z",
  "completed_at": "2026-10-21T22:08:06.100Z"
}
```

### 7.3 List Certificates
```http
GET /api/v1/jobs/87d0f08c-0328-40d6-b9ec-ef6281f7a2f4/certificates?limit=10&offset=0
```
**Response (200 OK):**
```json
{
  "job_id": "87d0f08c-0328-40d6-b9ec-ef6281f7a2f4",
  "total": 1,
  "limit": 10,
  "offset": 0,
  "certificates": [
    {
      "certificate_id": "9da6a293-376b-432e-915d-213a5309737a",
      "recipient_name": "Jane Doe",
      "recipient_email": "jane@example.com",
      "status": "SUCCESS",
      "generated_at": "2026-10-21T22:08:06.050Z",
      "file_size_bytes": 2126,
      "download_url": "/api/v1/certificates/9da6a293-376b-432e-915d-213a5309737a/download",
      "error_message": null
    }
  ]
}
```

### 7.4 Download Certificate
```http
GET /api/v1/certificates/9da6a293-376b-432e-915d-213a5309737a/download
```
**Response (200 OK):**
- **Content-Type:** `application/pdf`
- **Content-Disposition:** `attachment; filename="Jane_Doe_9da6a293-376b-432e-915d-213a5309737a.pdf"`
- **Body:** Binary PDF data (`%PDF-1.4...`)

---

## 8. Changed and Created Files

### Modified Files:
1. `app/core/celery_app.py`: Added `imports=["app.tasks.generate"]` to Celery configuration for automatic task discovery.
2. `app/main.py`: Registered jobs and certificates API routers under `/api/v1`.
3. `app/schemas/job.py`: Converted `pending_count` and `progress_percentage` to `@computed_field` properties.
4. `app/tasks/generate.py`: Added `db.refresh(job)` before job status finalization; atomic SQL counter updates.
5. `pyproject.toml`: Added `email-validator==2.2.0` and preserved `psycopg2-binary==2.9.9`.
6. `tests/conftest.py`: Implemented session-scoped event loop and nested transaction savepoint isolation fixture.
7. `tests/unit/test_file_manager.py`: Updated filename sanitization test expectations to preserve Unicode characters.
8. `tests/unit/test_pdf_generator.py`: Updated error handling test with a cross-platform invalid output path.

### New Files:
1. `app/api/routes/jobs.py`: REST routes for job submission, status inquiry, and certificate listing.
2. `app/api/routes/certificates.py`: Secure REST route for certificate PDF download.
3. `tests/integration/test_api_jobs.py`: 12 integration tests for job endpoints.
4. `tests/integration/test_api_certificates.py`: 7 integration tests for download endpoint, including path traversal prevention.
5. `tests/integration/test_workflow.py`: End-to-end API workflow tests.
6. `tests/unit/test_job_service.py`: 12 unit tests for JobService business logic.
7. `tests/unit/test_certificate_service.py`: 10 unit tests for CertificateService business logic.
8. `clean_test_db.py`: Database table truncation utility.
9. `test_e2e_live.py`: Automated live end-to-end verification script.

---

## 9. Git Diff & Dependency Verification

- **Secrets:** Verified clean. No API tokens, private keys, or passwords introduced in the Git diff.
- **Unrelated Changes:** None. All modified lines directly target Phase 2 functionality and verified bug fixes.
- **Dependencies:**
  - `email-validator==2.2.0`: Required for Pydantic v2 `EmailStr` field validation in `RecipientInput`.
  - `psycopg2-binary==2.9.9`: Required for synchronous SQLAlchemy sessions in Celery worker tasks.

---

## 10. Remaining Limitations & Future Considerations

1. **Shared Storage in Multi-Worker Environments:**
   - PDF generation currently saves files to local storage (`settings.certificate_storage_path`). In a multi-worker distributed deployment, workers running on separate nodes require shared object storage (such as S3, GCS, or MinIO) to ensure files can be served by any API node.
2. **Transaction Isolation in Celery Integration Tests:**
   - Unit tests run in rolled-back savepoints to keep the test database clean. Tests that execute `generate_certificates_for_job` directly require committed rows due to PostgreSQL's read-committed transaction isolation across separate connections.
3. **Windows Celery Pool:**
   - Celery workers run on Windows using `--pool=solo`. In production Linux environments or Docker containers, the standard prefork pool should be utilized.
