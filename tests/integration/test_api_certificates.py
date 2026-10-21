"""
Integration tests for certificate download API endpoint.
Tests certificate retrieval and file serving.
"""
import pytest
from datetime import date
from pathlib import Path
from httpx import AsyncClient

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.services.job_service import JobService
from app.services.certificate_service import CertificateService
from app.schemas.job import RecipientInput


@pytest.fixture
def override_get_db(db_session):
    """Override the get_db dependency to use the test session."""
    async def _get_test_db():
        yield db_session
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_download_certificate_success(db_session, override_get_db, tmp_path):
    """Test successful certificate download."""
    # Create a job with one recipient
    recipients = [
        RecipientInput(
            name="John Doe",
            email="john@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
    cert = certs[0]
    
    # Create a temporary PDF file
    job_dir = tmp_path / str(job.id)
    job_dir.mkdir(parents=True)
    pdf_path = job_dir / f"{cert.id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ntest pdf content")
    
    # Mark certificate as SUCCESS with file path
    relative_path = f"{job.id}/{cert.id}.pdf"
    await CertificateService.mark_certificate_success(
        cert.id, relative_path, len(pdf_path.read_bytes()), db_session
    )
    
    # Temporarily override storage path to use tmp_path
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Download the certificate
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/v1/certificates/{cert.id}/download")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "John_Doe" in response.headers.get("content-disposition", "")
        assert len(response.content) > 0
    finally:
        # Restore original storage path
        settings.certificate_storage_path = original_storage


@pytest.mark.asyncio
async def test_download_certificate_not_found(db_session, override_get_db):
    """Test download of non-existent certificate returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/certificates/{fake_id}/download")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_download_certificate_pending_status(db_session, override_get_db):
    """Test download of pending certificate returns 404."""
    # Create a job with one recipient (status is PENDING by default)
    recipients = [
        RecipientInput(
            name="Jane Smith",
            email="jane@example.com",
            course="Advanced Python",
            completion_date=date(2024, 1, 15)
        )
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
    cert = certs[0]
    
    # Try to download the pending certificate
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/certificates/{cert.id}/download")
    
    assert response.status_code == 404
    assert "not available for download" in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_certificate_failed_status(db_session, override_get_db):
    """Test download of failed certificate returns 404."""
    # Create a job with one recipient
    recipients = [
        RecipientInput(
            name="Bob Wilson",
            email="bob@example.com",
            course="Data Science",
            completion_date=date(2024, 1, 15)
        )
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
    cert = certs[0]
    
    # Mark certificate as FAILED
    await CertificateService.mark_certificate_failed(
        cert.id, "Test error", db_session
    )
    
    # Try to download the failed certificate
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/certificates/{cert.id}/download")
    
    assert response.status_code == 404
    assert "not available for download" in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_certificate_file_missing(db_session, override_get_db, tmp_path):
    """Test download when certificate record exists but file is missing."""
    # Create a job with one recipient
    recipients = [
        RecipientInput(
            name="Alice Cooper",
            email="alice@example.com",
            course="Machine Learning",
            completion_date=date(2024, 1, 15)
        )
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
    cert = certs[0]
    
    # Mark certificate as SUCCESS but don't create the actual file
    relative_path = f"{job.id}/{cert.id}.pdf"
    await CertificateService.mark_certificate_success(
        cert.id, relative_path, 1000, db_session
    )
    
    # Temporarily override storage path to use tmp_path (file doesn't exist there)
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Try to download (file missing on disk)
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/v1/certificates/{cert.id}/download")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        # Restore original storage path
        settings.certificate_storage_path = original_storage


@pytest.mark.asyncio
async def test_download_certificate_filename_format(db_session, override_get_db, tmp_path):
    """Test that download filename is properly formatted."""
    # Create a job with recipient with spaces in name
    recipients = [
        RecipientInput(
            name="Mary Jane Watson",
            email="mary.jane@example.com",
            course="Web Development",
            completion_date=date(2024, 1, 15)
        )
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
    cert = certs[0]
    
    # Create temporary file
    job_dir = tmp_path / str(job.id)
    job_dir.mkdir(parents=True)
    pdf_path = job_dir / f"{cert.id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ntest")
    
    # Mark as SUCCESS
    relative_path = f"{job.id}/{cert.id}.pdf"
    await CertificateService.mark_certificate_success(
        cert.id, relative_path, len(pdf_path.read_bytes()), db_session
    )
    
    # Override storage path
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Download and check filename
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/v1/certificates/{cert.id}/download")
        
        assert response.status_code == 200
        content_disp = response.headers.get("content-disposition", "")
        
        # Verify filename contains recipient name with underscores instead of spaces
        assert "Mary_Jane_Watson" in content_disp
        assert str(cert.id) in content_disp
        assert ".pdf" in content_disp
    finally:
        settings.certificate_storage_path = original_storage


@pytest.mark.asyncio
async def test_download_certificate_path_traversal_prevention(db_session, override_get_db, tmp_path):
    """Test that path traversal attempts in certificate download are prevented."""
    recipients = [
        RecipientInput(
            name="Security Tester",
            email="security@example.com",
            course="Security 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
    cert = certs[0]

    # Create a dummy storage directory and an external secret file
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("classified data")

    # Set file_path to traverse out of storage
    traversal_path = "../secret.txt"
    await CertificateService.mark_certificate_success(
        cert.id, traversal_path, 100, db_session
    )

    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(storage_dir)

    try:
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/v1/certificates/{cert.id}/download")

        # Must return 404 and not serve the secret file
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        settings.certificate_storage_path = original_storage

