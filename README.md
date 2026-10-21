# Bulk Certificate Generator Backend

A high-performance, asynchronous REST API and background worker pipeline built with **FastAPI**, **PostgreSQL**, **Celery**, **Redis**, and **ReportLab** for creating personalized PDF certificates in bulk.

---

## Features

- **Asynchronous Bulk Processing:** Submit jobs with up to 1,000 recipients per request. PDF generation runs asynchronously via Celery background workers.
- **Real-Time Job Tracking:** Check job status, progress percentage, completed count, and pending counts in real-time.
- **Failure Isolation:** Failures with individual recipients (e.g. invalid data or rendering exceptions) are tracked individually without failing the entire batch.
- **Atomic Counter Updates:** Direct database-level atomic increments prevent race conditions under concurrent worker execution.
- **Secure File Serving:** Dedicated download endpoints with path traversal validation preventing access to arbitrary filesystem locations.
- **Professional PDF Generation:** Dynamic PDF generation using ReportLab with custom styling, decorative borders, course details, and unique IDs.
- **Dockerized Architecture:** Ready-to-run setup using Docker Compose for PostgreSQL, Redis, FastAPI, and Celery workers.

---

## Architecture Overview

```
                      +-------------------+
                      |   Client / UI     |
                      +---------+---------+
                                |
                   HTTP REST    | (POST /jobs, GET /status)
                                v
                      +---------+---------+
                      |   FastAPI Server  |
                      +---+-----------+---+
                          |           |
            Writes Job &  |           | Enqueues Task
            Cert Records  |           | (.delay())
                          v           v
                  +-------+----+  +---+--------+
                  | PostgreSQL |  | Redis (MQ) |
                  +-------+----+  +---+--------+
                          ^           |
         Updates Progress |           | Consumes Job
         & Status         |           v
                      +---+-----------+---+
                      |   Celery Worker   |
                      +---------+---------+
                                |
                                | Generates PDFs
                                v
                      +---------+---------+
                      | Local / S3 Storage|
                      +-------------------+
```

---

## Prerequisites

- **Docker & Docker Compose** (Recommended for easiest setup), **OR**:
- **Python 3.12+**
- **PostgreSQL 15+**
- **Redis 7+**

---

## Quick Start with Docker (Recommended)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd certificate-generator
```

### 2. Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env
```

### 3. Build and Start All Services
```bash
docker compose up --build -d
```

This starts:
- `postgres` (Port 5432): Database
- `redis` (Port 6379): Celery message broker & result backend
- `api` (Port 8000): FastAPI application
- `worker`: Celery background task worker

### 4. Run Database Migrations
```bash
docker compose exec api alembic upgrade head
```

### 5. Verify the Installation
- **API Health Check:** [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Local Development Setup (Without Docker)

### 1. Environment Setup
Create and activate a virtual environment:
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -e .
```

### 3. Configure Database & Redis
Ensure PostgreSQL and Redis are running locally. Update `.env` with your credentials:
```env
DATABASE_URL=postgresql+asyncpg://certgen:password@localhost:5432/certgen
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CERTIFICATE_STORAGE_PATH=./data/certificates
MAX_RECIPIENTS_PER_JOB=1000
```

### 4. Apply Database Migrations
```bash
alembic upgrade head
```

### 5. Run the Application
In terminal 1, start the FastAPI API server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In terminal 2, start the Celery background worker:
```bash
# Windows (requires solo pool)
celery -A app.core.celery_app worker -l info -P solo

# Linux / macOS
celery -A app.core.celery_app worker -l info
```

---

## API Reference & Examples

### 1. Create a Bulk Certificate Job
Submits a batch of recipients for asynchronous processing.

**Endpoint:** `POST /api/v1/jobs`

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
     -H "Content-Type: application/json" \
     -d '{
       "recipients": [
         {
           "name": "Jane Doe",
           "email": "jane@example.com",
           "course": "Full Stack Web Development",
           "completion_date": "2024-05-15"
         },
         {
           "name": "John Smith",
           "email": "john@example.com",
           "course": "Full Stack Web Development",
           "completion_date": "2024-05-15"
         }
       ]
     }'
```

**Response (`201 Created`):**
```json
{
  "job_id": "87d0f08c-0328-40d6-b9ec-ef6281f7a2f4",
  "status": "PENDING",
  "total_recipients": 2,
  "completed_count": 0,
  "failed_count": 0,
  "pending_count": 2,
  "progress_percentage": 0.0,
  "created_at": "2026-10-21T22:08:05.076Z",
  "started_at": null,
  "completed_at": null
}
```

---

### 2. Check Job Status & Progress
Retrieves the real-time processing status and progress percentage.

**Endpoint:** `GET /api/v1/jobs/{job_id}`

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/87d0f08c-0328-40d6-b9ec-ef6281f7a2f4"
```

**Response (`200 OK`):**
```json
{
  "job_id": "87d0f08c-0328-40d6-b9ec-ef6281f7a2f4",
  "status": "COMPLETED",
  "total_recipients": 2,
  "completed_count": 2,
  "failed_count": 0,
  "pending_count": 0,
  "progress_percentage": 100.0,
  "created_at": "2026-10-21T22:08:05.076Z",
  "started_at": "2026-10-21T22:08:05.500Z",
  "completed_at": "2026-10-21T22:08:06.100Z"
}
```

---

### 3. List Certificates for a Job
Lists individual certificate records with pagination, status filtering, and download URLs.

**Endpoint:** `GET /api/v1/jobs/{job_id}/certificates?limit=10&offset=0&status=SUCCESS`

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/87d0f08c-0328-40d6-b9ec-ef6281f7a2f4/certificates"
```

**Response (`200 OK`):**
```json
{
  "job_id": "87d0f08c-0328-40d6-b9ec-ef6281f7a2f4",
  "total": 2,
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

---

### 4. Download Certificate PDF
Downloads the generated certificate PDF file.

**Endpoint:** `GET /api/v1/certificates/{certificate_id}/download`

**Request:**
```bash
curl -O -J "http://localhost:8000/api/v1/certificates/9da6a293-376b-432e-915d-213a5309737a/download"
```

**Response:**
- Header: `Content-Type: application/pdf`
- Header: `Content-Disposition: attachment; filename="Jane_Doe_9da6a293-376b-432e-915d-213a5309737a.pdf"`
- Body: Binary PDF stream

---

## Testing & Quality Assurance

### Run the Pytest Test Suite
```bash
pytest -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/ -v
```

### Run Live End-to-End Workflow Verification
Exercises job creation, Redis queueing, asynchronous Celery processing, polling, and PDF binary downloading:
```bash
python test_e2e_live.py
```

### Clean Test Database
To truncate test tables if needed:
```bash
python clean_test_db.py
```

---

## Project Structure

```
certificate-generator/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── certificates.py    # Download routes & path safety
│   │       └── jobs.py            # Job creation, polling, cert list
│   ├── core/
│   │   ├── celery_app.py          # Celery configuration & imports
│   │   ├── config.py              # Pydantic BaseSettings
│   │   └── database.py            # Async engine & sessionmaker
│   ├── models/
│   │   ├── certificate.py         # CertificateRecord SQLAlchemy model
│   │   └── job.py                 # GenerationJob SQLAlchemy model
│   ├── schemas/
│   │   ├── certificate.py         # Certificate response Pydantic schemas
│   │   └── job.py                 # Job request/response & computed fields
│   ├── services/
│   │   ├── certificate_service.py # Certificate database query service
│   │   ├── file_manager.py        # Storage path management & sanitization
│   │   ├── job_service.py         # Job creation & counter updates
│   │   └── pdf_generator.py       # ReportLab PDF creation
│   ├── tasks/
│   │   └── generate.py            # Celery task for batch processing
│   ├── templates/
│   │   └── certificate_template.py# Certificate canvas drawing & layout
│   └── main.py                    # FastAPI entrypoint & route registration
├── alembic/                       # Database migrations
├── tests/
│   ├── conftest.py                # Pytest fixtures & session isolation
│   ├── integration/               # API & workflow integration tests
│   └── unit/                      # Unit tests for services & generators
├── docker-compose.yml             # Docker services orchestration
├── Dockerfile                     # API and Worker container image
├── pyproject.toml                 # Package dependencies & configuration
└── test_e2e_live.py               # Live end-to-end verification script
```

---

## License

This project is licensed under the MIT License.
