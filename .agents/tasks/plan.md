# Implementation Plan: Bulk Certificate Generator Backend

This plan implements a production-ready FastAPI backend for bulk certificate generation with asynchronous processing, job tracking, graceful failure handling, and certificate retrieval.

## Overview

The work is decomposed into 5 sequential features (FEAT-001 through FEAT-005). Each feature builds on the previous ones. See the FEAT JSON files in this directory for detailed implementation steps and verification.

## Feature Sequence

### FEAT-001: Project Infrastructure Setup (Foundation)
**Type**: chore  
**Description**: Complete project setup with Docker Compose, PostgreSQL, Redis, FastAPI skeleton, Celery worker, Alembic migrations, and all configuration files.

**Key Deliverables**:
- Directory structure with app/, tests/, alembic/, data/
- pyproject.toml with pinned dependencies (FastAPI 0.109.2, SQLAlchemy 2.0.27, Celery 5.3.6, etc.)
- docker-compose.yml with 4 services: postgres, redis, api, worker
- Dockerfile with Python 3.12 multi-stage build
- Core configuration: app/core/{config.py, database.py, celery_app.py}
- Alembic initialization
- .env.example, .gitignore

**Verification**: `docker-compose up -d` starts all services, Swagger UI at http://localhost:8000/docs

---

### FEAT-002: Database Schema and Models (Data Layer)
**Type**: feat  
**Description**: SQLAlchemy models for generation_jobs and certificate_records with proper relationships, Pydantic validation schemas, and Alembic migration.

**Key Deliverables**:
- app/models/job.py: GenerationJob with UUID PK, 5 statuses, counters, timestamps
- app/models/certificate.py: CertificateRecord with job FK, recipient fields, 3 statuses
- app/schemas/job.py: RecipientInput, CreateJobRequest, JobResponse with validation
- app/schemas/certificate.py: CertificateResponse, CertificateListResponse
- Alembic migration creating both tables with indexes and constraints

**Verification**: `alembic upgrade head` creates tables, psql shows correct schema with FK cascades

---

### FEAT-003: PDF Generation Service (Certificate Creation)
**Type**: feat  
**Description**: ReportLab PDF generator with professional certificate template, file management service for storage paths and directory operations.

**Key Deliverables**:
- app/templates/certificate_template.py: A4 landscape layout with title, recipient info, styling
- app/services/pdf_generator.py: generate_certificate_pdf() creates valid PDFs with ReportLab
- app/services/file_manager.py: Path generation, directory creation, filename sanitization
- Unit tests for PDF content validation and file management

**Verification**: Unit tests pass, manual PDF generation creates viewable certificate with correct content

---

### FEAT-004: Business Logic and Celery Task (Processing Engine)
**Type**: feat  
**Description**: Service layer for job and certificate operations, main Celery task implementing bulk generation with graceful failure handling.

**Key Deliverables**:
- app/services/job_service.py: Create job+records, update status, finalize logic
- app/services/certificate_service.py: Query, filter, mark success/failure
- app/tasks/generate.py: generate_certificates_for_job Celery task with loop processing
- Integration tests with Celery eager mode

**Verification**: Celery task test generates all certificates, handles failures gracefully, updates job status correctly

---

### FEAT-005: REST API and E2E Testing (User Interface)
**Type**: feat  
**Description**: All 5 REST endpoints, comprehensive integration and end-to-end tests, complete README documentation.

**Key Deliverables**:
- app/api/routes/jobs.py: POST /api/v1/jobs, GET /api/v1/jobs/{id}, GET /api/v1/jobs/{id}/certificates, GET /api/v1/jobs
- app/api/routes/certificates.py: GET /api/v1/certificates/{id}/download
- Integration tests for all endpoints
- E2E test: POST job → poll status → download certificates
- README.md with architecture, setup, API docs, design decisions

**Verification**: Full workflow test passes, manual curl commands create job and download PDFs, coverage >80%

---

## Key Technical Decisions

1. **Asynchronous Processing**: Celery + Redis for background generation prevents HTTP timeouts and enables scalability
2. **Failure Tolerance**: Individual certificate failures don't stop the job - status becomes COMPLETED_WITH_ERRORS
3. **Filesystem Storage**: PDFs stored at data/certificates/<job_id>/<cert_id>.pdf, metadata in DB
4. **Database Design**: Two tables with cascade delete, UUIDs for public IDs, denormalized for performance
5. **Validation**: Pydantic V2 with email validation, date validation, recipient count limits (max 1000)

## Dependencies

- Python 3.12+
- Docker & Docker Compose
- PostgreSQL 15 (in container)
- Redis 7 (in container)

## Critical Implementation Notes

1. **Database Sessions**: Use AsyncSession for FastAPI routes, sync Session for Celery tasks (Celery doesn't support async)
2. **Migration Order**: Run Alembic before starting the API service (add depends_on with healthchecks)
3. **Volume Sharing**: API and Worker containers must share data/certificates volume for file access
4. **Task Idempotency**: Only process PENDING records so task reruns don't duplicate work
5. **Error Messages**: Store detailed error_message in certificate_records for debugging failed generations
6. **Progress Calculation**: pending_count = total_recipients - completed_count - failed_count (not stored)
7. **Celery Configuration**: Use task_acks_late=True and worker_prefetch_multiplier=1 for reliability
8. **File Response**: Use FastAPI FileResponse with proper content-disposition header for downloads

## Testing Strategy

- **Unit Tests**: PDF generation, validation logic, service methods (mocked DB)
- **Integration Tests**: API endpoints with real test database, Celery eager mode
- **E2E Tests**: Full workflow with real services, verify actual file generation
- **Target Coverage**: >80% overall, >90% for business logic

## Success Criteria

✅ docker-compose up starts all services  
✅ POST /api/v1/jobs creates job and returns immediately  
✅ Worker processes certificates in background  
✅ GET /api/v1/jobs/{id} shows real-time progress  
✅ Individual failures don't stop the batch  
✅ GET /api/v1/certificates/{id}/download serves valid PDFs  
✅ All tests pass with good coverage  
✅ README enables new developer to run project  

---

For detailed step-by-step implementation instructions, see:
- .agents/tasks/task-bulk-certificate-generator/context.json (project context)
- .agents/tasks/task-bulk-certificate-generator/features/FEAT-*.json (detailed steps per feature)
