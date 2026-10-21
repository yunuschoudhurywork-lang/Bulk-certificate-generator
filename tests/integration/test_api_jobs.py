"""
Integration tests for job API endpoints.
Tests the complete API surface for job creation and retrieval.
"""
import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from uuid import UUID

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.job import GenerationJob
from app.models.certificate import CertificateRecord


@pytest.fixture
def override_get_db(db_session):
    """Override the get_db dependency to use the test session."""
    async def _get_test_db():
        yield db_session
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_job_success(db_session, override_get_db):
    """Test successful job creation with valid recipients."""
    request_data = {
        "recipients": [
            {
                "name": "John Doe",
                "email": "john@example.com",
                "course": "Python 101",
                "completion_date": "2024-01-15"
            },
            {
                "name": "Jane Smith",
                "email": "jane@example.com",
                "course": "Advanced Python",
                "completion_date": "2024-01-20"
            }
        ]
    }
    
    # Mock Celery task to prevent actual queueing
    with patch("app.api.routes.jobs.generate_certificates_for_job") as mock_task:
        mock_task.delay = MagicMock(return_value=None)
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/jobs", json=request_data)
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response structure
    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert data["total_recipients"] == 2
    assert data["completed_count"] == 0
    assert data["failed_count"] == 0
    assert data["pending_count"] == 2
    assert data["progress_percentage"] == 0.0
    assert data["created_at"] is not None
    assert data["started_at"] is None
    assert data["completed_at"] is None
    
    # Verify Celery task was queued
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_create_job_empty_recipients(db_session, override_get_db):
    """Test that empty recipient list is rejected."""
    request_data = {"recipients": []}
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/jobs", json=request_data)
    
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_create_job_exceeds_max_recipients(db_session, override_get_db):
    """Test that requests exceeding max recipients are rejected."""
    # Create a request with more than allowed recipients
    max_allowed = settings.max_recipients_per_job
    request_data = {
        "recipients": [
            {
                "name": f"Person {i}",
                "email": f"person{i}@example.com",
                "course": "Test Course",
                "completion_date": "2024-01-15"
            }
            for i in range(max_allowed + 1)
        ]
    }
    
    with patch("app.api.routes.jobs.generate_certificates_for_job") as mock_task:
        mock_task.delay = MagicMock(return_value=None)
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/jobs", json=request_data)
    
    # Pydantic validation happens before endpoint validation, so we get 422
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_job_invalid_email(db_session, override_get_db):
    """Test that invalid email addresses are rejected."""
    request_data = {
        "recipients": [
            {
                "name": "John Doe",
                "email": "not-an-email",
                "course": "Python 101",
                "completion_date": "2024-01-15"
            }
        ]
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/jobs", json=request_data)
    
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_create_job_future_completion_date(db_session, override_get_db):
    """Test that future completion dates are rejected."""
    from datetime import timedelta
    future_date = (date.today() + timedelta(days=1)).isoformat()
    
    request_data = {
        "recipients": [
            {
                "name": "John Doe",
                "email": "john@example.com",
                "course": "Python 101",
                "completion_date": future_date
            }
        ]
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/jobs", json=request_data)
    
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_get_job_success(db_session, override_get_db):
    """Test successful job retrieval."""
    # Create a job first
    from app.services.job_service import JobService
    from app.schemas.job import RecipientInput
    
    recipients = [
        RecipientInput(
            name="John Doe",
            email="john@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Retrieve the job via API
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/jobs/{job.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["job_id"] == str(job.id)
    assert data["status"] == "PENDING"
    assert data["total_recipients"] == 1
    assert data["pending_count"] == 1
    assert data["progress_percentage"] == 0.0


@pytest.mark.asyncio
async def test_get_job_not_found(db_session, override_get_db):
    """Test retrieval of non-existent job."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/jobs/{fake_id}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_job_progress_calculation(db_session, override_get_db):
    """Test that progress percentage is correctly calculated."""
    from app.services.job_service import JobService
    from app.schemas.job import RecipientInput
    
    recipients = [
        RecipientInput(
            name=f"Person {i}",
            email=f"person{i}@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 15)
        )
        for i in range(10)
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Manually update counts to simulate progress
    job.completed_count = 7
    job.failed_count = 2
    await db_session.commit()
    
    # Retrieve via API
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/jobs/{job.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["completed_count"] == 7
    assert data["failed_count"] == 2
    assert data["pending_count"] == 1
    assert data["progress_percentage"] == 90.0  # (7 + 2) / 10 * 100


@pytest.mark.asyncio
async def test_list_certificates_for_job(db_session, override_get_db):
    """Test listing certificates for a job."""
    from app.services.job_service import JobService
    from app.schemas.job import RecipientInput
    
    recipients = [
        RecipientInput(
            name=f"Person {i}",
            email=f"person{i}@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 15)
        )
        for i in range(5)
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # List certificates
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/jobs/{job.id}/certificates")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["job_id"] == str(job.id)
    assert data["total"] == 5
    assert data["limit"] == 100
    assert data["offset"] == 0
    assert len(data["certificates"]) == 5
    
    # Verify certificate structure
    cert = data["certificates"][0]
    assert "certificate_id" in cert
    assert "recipient_name" in cert
    assert "status" in cert
    assert cert["status"] == "PENDING"
    assert cert["download_url"] is None  # Not yet generated


@pytest.mark.asyncio
async def test_list_certificates_pagination(db_session, override_get_db):
    """Test certificate listing pagination."""
    from app.services.job_service import JobService
    from app.schemas.job import RecipientInput
    
    recipients = [
        RecipientInput(
            name=f"Person {i}",
            email=f"person{i}@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 15)
        )
        for i in range(25)
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Get first page
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/jobs/{job.id}/certificates?limit=10&offset=0"
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 25
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert len(data["certificates"]) == 10
    
    # Get second page
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/jobs/{job.id}/certificates?limit=10&offset=10"
        )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["certificates"]) == 10


@pytest.mark.asyncio
async def test_list_certificates_with_status_filter(db_session, override_get_db):
    """Test filtering certificates by status."""
    from app.services.job_service import JobService
    from app.services.certificate_service import CertificateService
    from app.schemas.job import RecipientInput
    
    recipients = [
        RecipientInput(
            name=f"Person {i}",
            email=f"person{i}@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 15)
        )
        for i in range(5)
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Mark some certificates as SUCCESS
    certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
    await CertificateService.mark_certificate_success(
        certs[0].id, "test/path.pdf", 1000, db_session
    )
    await CertificateService.mark_certificate_success(
        certs[1].id, "test/path2.pdf", 2000, db_session
    )
    
    # Filter by SUCCESS status
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/jobs/{job.id}/certificates?status=SUCCESS"
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["certificates"]) == 2
    assert all(cert["status"] == "SUCCESS" for cert in data["certificates"])
    assert all(cert["download_url"] is not None for cert in data["certificates"])


@pytest.mark.asyncio
async def test_list_certificates_for_nonexistent_job(db_session, override_get_db):
    """Test listing certificates for non-existent job returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/jobs/{fake_id}/certificates")
    
    assert response.status_code == 404
