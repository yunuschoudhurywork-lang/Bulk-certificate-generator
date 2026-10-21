"""
Unit tests for CertificateService.
Tests certificate retrieval, status updates, and filtering.
"""
import pytest
from datetime import date
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job import RecipientInput
from app.services.job_service import JobService
from app.services.certificate_service import CertificateService


@pytest.mark.asyncio
async def test_get_certificates_by_job(db_session: AsyncSession):
    """Test retrieving all certificates for a job."""
    # Create a job with 3 recipients
    recipients = [
        RecipientInput(
            name=f"User {i}",
            email=f"user{i}@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
        for i in range(3)
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Get all certificates for this job
    certs, total = await CertificateService.get_certificates_by_job(
        job.id,
        db_session,
        limit=10,
        offset=0
    )
    
    assert len(certs) == 3
    assert total == 3
    
    # Verify all certificates belong to this job
    for cert in certs:
        assert cert.job_id == job.id
        assert cert.status == "PENDING"


@pytest.mark.asyncio
async def test_get_certificates_by_job_with_status_filter(db_session: AsyncSession):
    """Test retrieving certificates filtered by status."""
    # Create a job with 3 recipients
    recipients = [
        RecipientInput(
            name=f"User {i}",
            email=f"user{i}@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
        for i in range(3)
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Mark one certificate as SUCCESS and one as FAILED
    certs = job.certificate_records
    await CertificateService.mark_certificate_success(
        certs[0].id,
        "/path/to/cert1.pdf",
        12345,
        db_session
    )
    await CertificateService.mark_certificate_failed(
        certs[1].id,
        "Test error",
        db_session
    )
    
    # Filter by SUCCESS status
    success_certs, success_total = await CertificateService.get_certificates_by_job(
        job.id,
        db_session,
        status_filter="SUCCESS",
        limit=10,
        offset=0
    )
    assert len(success_certs) == 1
    assert success_total == 1
    assert success_certs[0].status == "SUCCESS"
    
    # Filter by FAILED status
    failed_certs, failed_total = await CertificateService.get_certificates_by_job(
        job.id,
        db_session,
        status_filter="FAILED",
        limit=10,
        offset=0
    )
    assert len(failed_certs) == 1
    assert failed_total == 1
    assert failed_certs[0].status == "FAILED"
    
    # Filter by PENDING status
    pending_certs, pending_total = await CertificateService.get_certificates_by_job(
        job.id,
        db_session,
        status_filter="PENDING",
        limit=10,
        offset=0
    )
    assert len(pending_certs) == 1
    assert pending_total == 1
    assert pending_certs[0].status == "PENDING"


@pytest.mark.asyncio
async def test_get_certificates_pagination(db_session: AsyncSession):
    """Test pagination when retrieving certificates."""
    # Create a job with 5 recipients
    recipients = [
        RecipientInput(
            name=f"User {i}",
            email=f"user{i}@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
        for i in range(5)
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Get first page
    certs_page1, total = await CertificateService.get_certificates_by_job(
        job.id,
        db_session,
        limit=2,
        offset=0
    )
    assert len(certs_page1) == 2
    assert total == 5
    
    # Get second page
    certs_page2, total = await CertificateService.get_certificates_by_job(
        job.id,
        db_session,
        limit=2,
        offset=2
    )
    assert len(certs_page2) == 2
    assert total == 5
    
    # Get third page
    certs_page3, total = await CertificateService.get_certificates_by_job(
        job.id,
        db_session,
        limit=2,
        offset=4
    )
    assert len(certs_page3) == 1
    assert total == 5


@pytest.mark.asyncio
async def test_get_certificate_by_id(db_session: AsyncSession):
    """Test retrieving a certificate by its ID."""
    # Create a job with one recipient
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    cert_id = job.certificate_records[0].id
    
    # Retrieve the certificate
    cert = await CertificateService.get_certificate_by_id(cert_id, db_session)
    
    assert cert is not None
    assert cert.id == cert_id
    assert cert.recipient_name == "Test User"
    assert cert.status == "PENDING"


@pytest.mark.asyncio
async def test_get_certificate_by_id_not_found(db_session: AsyncSession):
    """Test retrieving a non-existent certificate returns None."""
    fake_id = uuid4()
    cert = await CertificateService.get_certificate_by_id(fake_id, db_session)
    
    assert cert is None


@pytest.mark.asyncio
async def test_mark_certificate_success(db_session: AsyncSession):
    """Test marking a certificate as successfully generated."""
    # Create a job with one recipient
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    cert = job.certificate_records[0]
    
    assert cert.status == "PENDING"
    assert cert.file_path is None
    assert cert.file_size_bytes is None
    assert cert.generated_at is None
    
    # Mark as success
    file_path = "/data/certificates/job-id/cert-id.pdf"
    file_size = 54321
    updated_cert = await CertificateService.mark_certificate_success(
        cert.id,
        file_path,
        file_size,
        db_session
    )
    
    assert updated_cert is not None
    assert updated_cert.status == "SUCCESS"
    assert updated_cert.file_path == file_path
    assert updated_cert.file_size_bytes == file_size
    assert updated_cert.generated_at is not None
    assert updated_cert.error_message is None


@pytest.mark.asyncio
async def test_mark_certificate_failed(db_session: AsyncSession):
    """Test marking a certificate as failed."""
    # Create a job with one recipient
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    cert = job.certificate_records[0]
    
    assert cert.status == "PENDING"
    assert cert.error_message is None
    
    # Mark as failed
    error_msg = "Disk full: Cannot write PDF file"
    updated_cert = await CertificateService.mark_certificate_failed(
        cert.id,
        error_msg,
        db_session
    )
    
    assert updated_cert is not None
    assert updated_cert.status == "FAILED"
    assert updated_cert.error_message == error_msg


@pytest.mark.asyncio
async def test_mark_certificate_success_clears_previous_error(db_session: AsyncSession):
    """Test that marking certificate as success clears any previous error."""
    # Create a job with one recipient
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    cert = job.certificate_records[0]
    
    # First mark as failed
    await CertificateService.mark_certificate_failed(
        cert.id,
        "Initial error",
        db_session
    )
    
    # Verify it's failed with error message
    cert = await CertificateService.get_certificate_by_id(cert.id, db_session)
    assert cert.status == "FAILED"
    assert cert.error_message == "Initial error"
    
    # Then mark as success (e.g., on retry)
    updated_cert = await CertificateService.mark_certificate_success(
        cert.id,
        "/path/to/cert.pdf",
        12345,
        db_session
    )
    
    # Verify error message is cleared
    assert updated_cert.status == "SUCCESS"
    assert updated_cert.error_message is None
    assert updated_cert.file_path == "/path/to/cert.pdf"


@pytest.mark.asyncio
async def test_get_certificates_empty_job(db_session: AsyncSession):
    """Test retrieving certificates for a non-existent job."""
    fake_job_id = uuid4()
    
    certs, total = await CertificateService.get_certificates_by_job(
        fake_job_id,
        db_session,
        limit=10,
        offset=0
    )
    
    assert certs == []
    assert total == 0
