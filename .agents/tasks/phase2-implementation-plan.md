# Phase 2 — End-to-End Bulk Certificate Generation Workflow
## Implementation Plan

---

## Section 1 — Existing Functionality (Already Complete)

The following components are already implemented and working:

### Database Layer
- **Models**: `app/models/job.py` — GenerationJob model with status tracking, progress counters, and timestamps
- **Models**: `app/models/certificate.py` — CertificateRecord model with recipient info, status, and file metadata
- **Migration**: `alembic/versions/001_*.py` — Database tables created with constraints and indexes
- **Database Config**: `app/core/database.py` — Async SQLAlchemy engine and session factory using asyncpg

### Service Layer (Async for FastAPI)
- **JobService**: `app/services/job_service.py` — Complete implementation:
  - `create_job_with_recipients()` — Atomic job + certificate records creation
  - `get_job_by_id()` — Job retrieval
  - `update_job_status()` — Status transitions with timestamps
  - `increment_completed()/increment_failed()` — Progress tracking
  - `finalize_job_status()` — Final status determination (COMPLETED/COMPLETED_WITH_ERRORS/FAILED)
  - `list_jobs()` — Paginated job listing
- **CertificateService**: `app/services/certificate_service.py` — Complete implementation:
  - `get_certificates_by_job()` — Certificate retrieval with status filtering and pagination
  - `get_certificate_by_id()` — Single certificate lookup
  - `mark_certificate_success()` — Update certificate with file path and size
  - `mark_certificate_failed()` — Update certificate with error message
- **FileManager**: `app/services/file_manager.py` — Complete file path management:
  - `generate_certificate_path()` — Hierarchical path generation (job_id/cert_id.pdf)
  - `ensure_job_directory()` — Directory creation with error handling
  - `validate_storage_path()` — Storage validation on startup
- **PDFGenerator**: `app/services/pdf_generator.py` — Complete certificate generation:
  - `generate_certificate_pdf()` — ReportLab-based PDF generation with template
  - Error handling for validation, permissions, disk full

### Pydantic Schemas
- **Request**: `app/schemas/job.py` — `RecipientInput` with validation (name, email, course, completion_date)
- **Request**: `app/schemas/job.py` — `CreateJobRequest` with recipients list (1-1000 items)
- **Response**: `app/schemas/job.py` — `JobResponse` with progress tracking fields
- **Response**: `app/schemas/certificate.py` — `CertificateResponse` with download_url field

### Celery Configuration
- **Celery App**: `app/core/celery_app.py` — Configured with Redis broker, task routing, timeouts
- **Worker Task**: `app/tasks/generate.py` — **COMPLETE IMPLEMENTATION**:
  - Synchronous DB session using psycopg2 (separate from async FastAPI)
  - Iterates through PENDING certificates
  - Generates PDFs using PDFGenerator
  - Individual failure isolation (one failure doesn't stop others)
  - Atomic counter updates using SQL UPDATE statements
  - Final job status determination
  - Retry logic for database errors

### Configuration
- **Settings**: `app/core/config.py` — All configuration loaded from environment:
  - `max_recipients_per_job` — Default 1000
  - `certificate_storage_path` — Default ./data/certificates
  - Database, Redis, Celery URLs

### Testing Infrastructure
- **Fixtures**: `tests/conftest.py` — Async session with transaction isolation using savepoints
- **Service Tests**: Complete unit test coverage:
  - `tests/unit/test_job_service.py` — 12 tests covering all JobService methods
  - `tests/unit/test_certificate_service.py` — 10 tests covering all CertificateService methods
  - `tests/unit/test_file_manager.py` — File path and validation tests
  - `tests/unit/test_pdf_generator.py` — PDF generation tests

---

## Section 2 — Missing or Broken Functionality

The following components need to be created to complete the workflow:

### 1. **API Routes — POST /api/v1/jobs**
**File to create**: `app/api/routes/jobs.py`
**What's missing**: FastAPI endpoint to accept bulk certificate generation requests
**Minimal change required**:
- Endpoint receives `CreateJobRequest` (already validated by Pydantic)
- Validates recipient count against `settings.max_recipients_per_job`
- Calls `JobService.create_job_with_recipients()`
- Queues Celery task: `generate_certificates_for_job.delay(str(job.id))`
- Returns `JobResponse` with 201 status

### 2. **API Routes — GET /api/v1/jobs/{job_id}**
**File to create**: `app/api/routes/jobs.py`
**What's missing**: Endpoint to retrieve job status
**Minimal change required**:
- Parse job_id UUID from path
- Call `JobService.get_job_by_id()`
- Return 404 if not found
- Calculate `progress_percentage` = `(completed_count + failed_count) / total_recipients * 100`
- Add `pending_count` = `total_recipients - completed_count - failed_count`
- Return `JobResponse`

### 3. **API Routes — GET /api/v1/jobs/{job_id}/certificates**
**File to create**: `app/api/routes/jobs.py`
**What's missing**: Endpoint to list certificates for a job
**Minimal change required**:
- Parse job_id, limit, offset from query params
- Call `CertificateService.get_certificates_by_job()`
- Build download URL for each certificate: `/api/v1/certificates/{cert.id}/download`
- Return paginated certificate list

### 4. **API Routes — GET /api/v1/certificates/{certificate_id}/download**
**File to create**: `app/api/routes/certificates.py`
**What's missing**: Endpoint to download generated certificate PDF
**Minimal change required**:
- Parse certificate_id UUID from path
- Call `CertificateService.get_certificate_by_id()`
- Return 404 if not found
- Return 404 if status != "SUCCESS" (certificate not generated yet)
- Construct full file path: `settings.certificate_storage_path / cert.file_path`
- Return 404 if file doesn't exist on disk
- Return `FileResponse` with content_type="application/pdf"

### 5. **Router Registration**
**File to modify**: `app/main.py`
**What's missing**: Routes not registered with FastAPI app
**Minimal change required**:
- Uncomment and update the router import section
- Import `jobs` and `certificates` routers
- Add `app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])`
- Add `app.include_router(certificates.router, prefix="/api/v1", tags=["Certificates"])`

### 6. **Response Schema Enhancement**
**File to modify**: `app/schemas/job.py` — `JobResponse`
**What's missing**: `progress_percentage` and `pending_count` are defined but not computed
**Minimal change required**:
- Add `@computed_field` property for `progress_percentage`
- Add `@computed_field` property for `pending_count`
- Remove from required fields in model definition (they're computed)

### 7. **Integration Tests**
**Files to create**: 
- `tests/integration/test_api_jobs.py` — API endpoint tests
- `tests/integration/test_workflow.py` — End-to-end workflow test with mocked Celery

**What's missing**: Tests verifying the complete workflow
**Minimal change required**: See Section 4 below

---

## Section 3 — Implementation Checklist (Ordered by Dependency)

### ✅ Phase 3A: Response Schema Enhancement (Foundation)

- [ ] **1. Enhance JobResponse schema**
  - **File**: `app/schemas/job.py`
  - **Change**: Convert `progress_percentage` and `pending_count` to `@computed_field` properties
  - **Why**: These values should be computed from counters, not stored/retrieved from DB
  - **Implementation**:
    ```python
    from pydantic import computed_field
    
    @computed_field
    @property
    def pending_count(self) -> int:
        return self.total_recipients - self.completed_count - self.failed_count
    
    @computed_field
    @property
    def progress_percentage(self) -> float:
        if self.total_recipients == 0:
            return 0.0
        return round((self.completed_count + self.failed_count) / self.total_recipients * 100, 2)
    ```
  - **Verify**: Run `pytest tests/unit/test_job_service.py -v` — existing tests should pass with computed fields

### ✅ Phase 3B: API Routes Implementation (Core Workflow)

- [ ] **2. Create jobs API router**
  - **File**: `app/api/routes/jobs.py` (new file)
  - **Change**: Implement all job-related endpoints:
    - `POST /jobs` — Create bulk generation job and queue Celery task
    - `GET /jobs/{job_id}` — Get job status with progress
    - `GET /jobs/{job_id}/certificates` — List certificates for job
  - **Why**: These are the primary API endpoints for the bulk workflow
  - **Key details**:
    - Use `Depends(get_db)` for database session injection
    - Import Celery task: `from app.tasks.generate import generate_certificates_for_job`
    - Queue task after job creation: `generate_certificates_for_job.delay(str(job.id))`
    - Validate recipient count: `if len(request.recipients) > settings.max_recipients_per_job: raise HTTPException(400)`
    - Return appropriate HTTP status codes: 201 for creation, 404 for not found
    - Build JobResponse using existing schema (computed fields work automatically)
  - **Verify**: Create integration test file and test each endpoint

- [ ] **3. Create certificates API router**
  - **File**: `app/api/routes/certificates.py` (new file)
  - **Change**: Implement certificate download endpoint:
    - `GET /certificates/{certificate_id}/download` — Download generated PDF
  - **Why**: Provides retrieval mechanism for generated certificates
  - **Key details**:
    - Check certificate status == "SUCCESS" before serving file
    - Construct file path: `Path(settings.certificate_storage_path) / cert.file_path`
    - Use `FileResponse` with `media_type="application/pdf"`
    - Set `Content-Disposition` header: `attachment; filename="{recipient_name}_{cert_id}.pdf"`
    - Return 404 if certificate not found, not yet generated, or file missing from disk
  - **Verify**: Integration test with mock file

- [ ] **4. Register routers in main application**
  - **File**: `app/main.py`
  - **Change**: Import and include both routers:
    ```python
    from app.api.routes import jobs, certificates
    
    app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
    app.include_router(certificates.router, prefix="/api/v1", tags=["Certificates"])
    ```
  - **Why**: Makes endpoints accessible through FastAPI application
  - **Verify**: Start app and check `/docs` — endpoints should appear in Swagger UI

### ✅ Phase 3C: Integration Tests (Verification)

- [ ] **5. Create job API integration tests**
  - **File**: `tests/integration/test_api_jobs.py` (new file)
  - **Change**: Add integration tests for job endpoints
  - **Tests to include**:
    - `test_create_job_success` — POST valid request, verify 201 response and job created
    - `test_create_job_empty_recipients` — POST with empty list, verify 422 validation error
    - `test_create_job_exceeds_max_recipients` — POST with too many recipients, verify 400 error
    - `test_get_job_success` — GET existing job, verify response structure
    - `test_get_job_not_found` — GET non-existent job, verify 404
    - `test_list_certificates_for_job` — GET certificates for job, verify pagination
  - **Mock requirements**: Mock `generate_certificates_for_job.delay()` to prevent actual Celery task execution
  - **Verify**: `pytest tests/integration/test_api_jobs.py -v`

- [ ] **6. Create certificate API integration tests**
  - **File**: `tests/integration/test_api_certificates.py` (new file)
  - **Change**: Add integration tests for certificate download
  - **Tests to include**:
    - `test_download_certificate_success` — Download successful certificate, verify file response
    - `test_download_certificate_not_found` — Download non-existent certificate, verify 404
    - `test_download_certificate_pending` — Download pending certificate, verify 404 or appropriate error
    - `test_download_certificate_file_missing` — Certificate record exists but file deleted, verify 404
  - **Mock requirements**: Create temporary test PDF files for download tests
  - **Verify**: `pytest tests/integration/test_api_certificates.py -v`

- [ ] **7. Create end-to-end workflow test**
  - **File**: `tests/integration/test_workflow.py` (new file)
  - **Change**: Add complete workflow test (mocked Celery)
  - **Test scenario**:
    1. POST bulk job with 3 recipients
    2. Verify job created with PENDING status
    3. Verify Celery task was queued (mock)
    4. Manually call the Celery task function (bypassing queue)
    5. Verify job status updated to COMPLETED
    6. Verify all 3 certificates have SUCCESS status
    7. Verify PDF files exist on disk
    8. Attempt to download each certificate via API
  - **Mock requirements**: Use test database session; create actual PDF files in temp directory
  - **Verify**: `pytest tests/integration/test_workflow.py -v`

- [ ] **8. Create failure isolation test**
  - **File**: `tests/integration/test_workflow.py`
  - **Change**: Add test verifying one failure doesn't stop others
  - **Test scenario**:
    1. Create job with 3 recipients
    2. Mock PDF generator to fail for 2nd recipient only
    3. Run Celery task
    4. Verify job status = COMPLETED_WITH_ERRORS
    5. Verify completed_count = 2, failed_count = 1
    6. Verify 1st and 3rd certificates have SUCCESS status
    7. Verify 2nd certificate has FAILED status with error message
  - **Verify**: `pytest tests/integration/test_workflow.py::test_failure_isolation -v`

---

## Section 4 — Testing Plan

### Unit Tests (Already Complete)
✅ All service layer unit tests exist and pass (52/52 tests)

### Integration Tests (To Be Created)

#### **test_api_jobs.py**
| Test Name | Verifies | Mocks Needed |
|-----------|----------|--------------|
| `test_create_job_success` | POST /jobs creates job and queues task | `generate_certificates_for_job.delay()` |
| `test_create_job_returns_correct_response` | Response matches JobResponse schema | Same as above |
| `test_create_job_empty_recipients` | Empty list rejected with 422 | None |
| `test_create_job_exceeds_max_recipients` | Request with 1001 recipients rejected | None |
| `test_create_job_invalid_email` | Invalid email rejected with 422 | None |
| `test_create_job_future_completion_date` | Future date rejected with 422 | None |
| `test_get_job_success` | GET /jobs/{id} returns correct data | None |
| `test_get_job_not_found` | GET non-existent job returns 404 | None |
| `test_get_job_progress_calculation` | progress_percentage computed correctly | None |
| `test_list_certificates_pagination` | Certificate list pagination works | None |
| `test_list_certificates_for_nonexistent_job` | Returns empty list for unknown job | None |

#### **test_api_certificates.py**
| Test Name | Verifies | Mocks Needed |
|-----------|----------|--------------|
| `test_download_certificate_success` | GET /certificates/{id}/download serves PDF | Temp PDF file |
| `test_download_certificate_not_found` | Unknown certificate ID returns 404 | None |
| `test_download_certificate_pending_status` | PENDING certificate returns 404 | None |
| `test_download_certificate_failed_status` | FAILED certificate returns 404 | None |
| `test_download_certificate_file_missing` | SUCCESS record but missing file returns 404 | None |
| `test_download_certificate_content_type` | Response has correct content-type | Temp PDF file |
| `test_download_certificate_content_disposition` | Filename set correctly in header | Temp PDF file |

#### **test_workflow.py**
| Test Name | Verifies | Mocks Needed |
|-----------|----------|--------------|
| `test_end_to_end_workflow_success` | Complete workflow: API → task → download | Temp storage dir |
| `test_workflow_with_one_failure` | One recipient failure doesn't stop others | Mock PDF generator to fail once |
| `test_workflow_all_failures` | All failures results in FAILED status | Mock PDF generator to always fail |
| `test_workflow_concurrent_counter_safety` | Progress counters accurate under concurrency | None (relies on atomic SQL updates) |
| `test_workflow_job_finalization` | completed_at timestamp set correctly | None |
| `test_workflow_file_permissions_error` | Permission error on file write handled gracefully | Mock file write to raise PermissionError |

### Test Command
```bash
# Run all tests
pytest -v

# Run only integration tests
pytest tests/integration/ -v

# Run with coverage
pytest --cov=app --cov-report=html --cov-report=term-missing
```

---

## Section 5 — Architecture Notes

### 1. **Async/Sync Boundary**
**Decision**: FastAPI uses async (asyncpg), Celery uses sync (psycopg2)

**Rationale**:
- FastAPI naturally works with async/await and asyncpg for high-concurrency request handling
- Celery workers are synchronous by design and work better with sync database sessions
- Attempting to mix async in Celery workers adds complexity without benefit
- This is the approach already implemented in `app/tasks/generate.py`

**Implementation**:
- FastAPI routes use `AsyncSession` from `app.core.database.get_db()`
- Celery task creates its own sync engine:
  ```python
  sync_db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
  sync_engine = create_engine(sync_db_url)
  SyncSessionLocal = sessionmaker(bind=sync_engine)
  ```

### 2. **File Storage and Retrieval**

**Storage Structure**:
```
{CERTIFICATE_STORAGE_PATH}/
├── {job_id_1}/
│   ├── {cert_id_1}.pdf
│   ├── {cert_id_2}.pdf
│   └── {cert_id_3}.pdf
├── {job_id_2}/
│   └── {cert_id_4}.pdf
```

**Path Management**:
- `FileManager.generate_certificate_path(job_id, cert_id)` produces absolute path
- Database stores relative path: `{job_id}/{cert_id}.pdf`
- Download endpoint reconstructs: `Path(settings.certificate_storage_path) / cert.file_path`

**Naming Convention**:
- Files named by UUID: `{cert_id}.pdf`
- Simple, collision-free, no sanitization needed
- Download endpoint sets human-friendly filename in Content-Disposition header

**Error Handling**:
- Directory creation handled by `FileManager.ensure_job_directory()`
- Permission errors caught and logged during PDF generation
- Missing files on download return 404 (file may have been deleted externally)

### 3. **Concurrency-Safe Progress Counters**

**Problem**: Multiple workers processing same job could race on counter updates

**Solution**: Atomic SQL UPDATE statements (already implemented in `app/tasks/generate.py`)

**Implementation**:
```python
# Instead of:
# job.completed_count += 1
# db.commit()

# Use atomic update:
db.execute(
    update(GenerationJob)
    .where(GenerationJob.id == job_uuid)
    .values(completed_count=GenerationJob.completed_count + 1)
)
db.commit()
```

**Why**: SQL-level increment is atomic; prevents lost updates under concurrent access

**Note**: Single-worker deployment is expected for MVP, but this pattern ensures correctness if scaled to multiple workers later

### 4. **Job Status Transitions**

**Valid Transitions**:
```
PENDING → PROCESSING → COMPLETED (all success)
                     → COMPLETED_WITH_ERRORS (partial success)
                     → FAILED (all failed)
```

**Status Logic** (implemented in Celery task):
- `PENDING`: Job created, not yet started
- `PROCESSING`: Task has started, `started_at` timestamp set
- `COMPLETED`: All certificates successful, `failed_count = 0`
- `COMPLETED_WITH_ERRORS`: Some failures, `0 < failed_count < total_recipients`
- `FAILED`: All certificates failed, `failed_count = total_recipients`

**Finalization**: Task sets `completed_at` timestamp regardless of final status

### 5. **Error Handling Strategy**

**Certificate-Level Errors** (non-blocking):
- PDF generation failure → mark certificate FAILED, continue with others
- Validation error → mark certificate FAILED, continue with others
- File write error → mark certificate FAILED, continue with others

**Job-Level Errors** (blocking):
- Database connection failure → retry task (configured in Celery)
- Job directory creation failure → fail task immediately
- Job not found → fail task immediately

**API Errors**:
- Invalid request data → 422 Unprocessable Entity
- Job/certificate not found → 404 Not Found
- Recipient count exceeded → 400 Bad Request
- Certificate not ready for download → 404 Not Found

### 6. **Request Validation**

**Validation Layers**:
1. **Pydantic Schema** (automatic):
   - Email format validation
   - String length constraints
   - Date validation (not future)
   - Non-empty strings after whitespace strip
   
2. **API Endpoint** (custom):
   - Recipient count ≤ `settings.max_recipients_per_job`
   
3. **Celery Task** (defensive):
   - Re-validates recipient data before PDF generation
   - Catches edge cases that may have bypassed API validation

### 7. **Download URL Construction**

**Pattern**: Download URLs built in API responses, not stored in database

**Implementation**:
```python
# In certificate listing/retrieval
if cert.status == "SUCCESS":
    cert_response.download_url = f"/api/v1/certificates/{cert.id}/download"
else:
    cert_response.download_url = None
```

**Why**: URLs may change with API versioning; computed values are more flexible than stored values

---

## Summary

### What Needs to Be Created
1. Two API router files: `jobs.py` and `certificates.py`
2. Router registration in `main.py`
3. Computed fields for `JobResponse`
4. Three integration test files

### What Already Works
- Complete database schema and migrations
- Complete service layer with all business logic
- Complete Celery task with failure isolation and atomic counters
- Complete PDF generation with template
- Complete file management with path generation
- 52/52 passing unit tests

### Verification Strategy
1. Unit tests verify service layer (already passing)
2. Integration tests verify API endpoints (to be created)
3. Workflow tests verify end-to-end behavior (to be created)
4. Manual testing with Docker: POST job, check status, download certificates

### Estimated Effort
- API routes: ~150 lines of code
- Integration tests: ~300 lines of code
- Total: ~450 lines to complete Phase 2

### Key Risks
**None identified** — All complex logic (database, services, task processing) is already implemented and tested. The remaining work is straightforward HTTP endpoint wiring.
