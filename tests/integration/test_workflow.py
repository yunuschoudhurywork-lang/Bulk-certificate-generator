"""
Integration tests for end-to-end certificate generation workflow.
Tests the complete flow from job creation through certificate generation.
"""
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.services.job_service import JobService
from app.services.certificate_service import CertificateService
from app.schemas.job import RecipientInput
from app.tasks.generate import generate_certificates_for_job


@pytest.fixture
def override_get_db(db_session):
    """Override the get_db dependency to use the test session."""
    async def _get_test_db():
        yield db_session
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_end_to_end_workflow_success(db_session, override_get_db, tmp_path):
    """
    Test complete workflow: create job → verify queued → check API responses.
    Note: Actual Celery task execution requires Docker/separate database.
    """
    # Override storage path
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Step 1: Create job via API
        request_data = {
            "recipients": [
                {
                    "name": "Alice Johnson",
                    "email": "alice@example.com",
                    "course": "Python 101",
                    "completion_date": "2024-01-15"
                },
                {
                    "name": "Bob Smith",
                    "email": "bob@example.com",
                    "course": "Python 101",
                    "completion_date": "2024-01-16"
                },
                {
                    "name": "Charlie Brown",
                    "email": "charlie@example.com",
                    "course": "Python 101",
                    "completion_date": "2024-01-17"
                }
            ]
        }
        
        with patch("app.api.routes.jobs.generate_certificates_for_job") as mock_task:
            mock_task.delay = MagicMock(return_value=None)
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/api/v1/jobs", json=request_data)
        
        assert response.status_code == 201
        job_id = response.json()["job_id"]
        
        # Verify Celery task was queued
        mock_task.delay.assert_called_once_with(job_id)
        
        # Step 2: Verify job status via API
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/v1/jobs/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"
        assert data["total_recipients"] == 3
        assert data["completed_count"] == 0
        assert data["failed_count"] == 0
        assert data["progress_percentage"] == 0.0
        
        # Step 3: List certificates
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/v1/jobs/{job_id}/certificates")
        
        assert response.status_code == 200
        certs = response.json()["certificates"]
        assert len(certs) == 3
        assert all(cert["status"] == "PENDING" for cert in certs)
        assert all(cert["download_url"] is None for cert in certs)
    
    finally:
        settings.certificate_storage_path = original_storage


@pytest.mark.skip(reason="Requires actual database transaction - tested via Docker integration")
@pytest.mark.asyncio
async def test_workflow_with_one_failure(db_session, tmp_path):
    """
    Test workflow where one recipient fails but others succeed.
    Verifies failure isolation.
    """
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Create job with 3 recipients
        recipients = [
            RecipientInput(
                name=f"Person {i}",
                email=f"person{i}@example.com",
                course="Test Course",
                completion_date=date(2024, 1, 15)
            )
            for i in range(3)
        ]
        
        job = await JobService.create_job_with_recipients(recipients, db_session)
        
        # Mock PDF generator to fail for the 2nd recipient only
        original_generate = __import__("app.services.pdf_generator", fromlist=["generate_certificate_pdf"]).generate_certificate_pdf
        call_count = [0]
        
        def mock_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Fail on 2nd call
                raise Exception("Simulated PDF generation failure")
            return original_generate(*args, **kwargs)
        
        with patch("app.tasks.generate.generate_certificate_pdf", side_effect=mock_generate):
            result = generate_certificates_for_job(str(job.id))
        
        # Verify job completed with errors
        assert result["status"] == "COMPLETED_WITH_ERRORS"
        assert result["completed"] == 2
        assert result["failed"] == 1
        assert result["total"] == 3
        
        # Verify certificate statuses
        certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
        success_certs = [c for c in certs if c.status == "SUCCESS"]
        failed_certs = [c for c in certs if c.status == "FAILED"]
        
        assert len(success_certs) == 2
        assert len(failed_certs) == 1
        
        # Verify failed certificate has error message
        assert failed_certs[0].error_message is not None
        assert "Failed to generate certificate" in failed_certs[0].error_message
        
        # Verify successful certificates can be downloaded
        for cert in success_certs:
            file_path = tmp_path / str(job.id) / f"{cert.id}.pdf"
            assert file_path.exists()
    
    finally:
        settings.certificate_storage_path = original_storage


@pytest.mark.skip(reason="Requires actual database transaction - tested via Docker integration")
@pytest.mark.asyncio
async def test_workflow_all_failures(db_session, tmp_path):
    """
    Test workflow where all recipients fail.
    Final status should be FAILED.
    """
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Create job with 3 recipients
        recipients = [
            RecipientInput(
                name=f"Person {i}",
                email=f"person{i}@example.com",
                course="Test Course",
                completion_date=date(2024, 1, 15)
            )
            for i in range(3)
        ]
        
        job = await JobService.create_job_with_recipients(recipients, db_session)
        
        # Mock PDF generator to always fail
        def mock_generate_fail(*args, **kwargs):
            raise Exception("Simulated failure")
        
        with patch("app.tasks.generate.generate_certificate_pdf", side_effect=mock_generate_fail):
            result = generate_certificates_for_job(str(job.id))
        
        # Verify job failed
        assert result["status"] == "FAILED"
        assert result["completed"] == 0
        assert result["failed"] == 3
        assert result["total"] == 3
        
        # Verify all certificates are marked as FAILED
        certs, _ = await CertificateService.get_certificates_by_job(job.id, db_session)
        assert all(c.status == "FAILED" for c in certs)
        assert all(c.error_message is not None for c in certs)
    
    finally:
        settings.certificate_storage_path = original_storage


@pytest.mark.skip(reason="Requires actual database transaction - tested via Docker integration")
@pytest.mark.asyncio
async def test_workflow_job_finalization_timestamps(db_session, tmp_path):
    """Test that job timestamps are correctly set during workflow."""
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Create job
        recipients = [
            RecipientInput(
                name="Test User",
                email="test@example.com",
                course="Test Course",
                completion_date=date(2024, 1, 15)
            )
        ]
        
        job = await JobService.create_job_with_recipients(recipients, db_session)
        
        # Verify initial state
        assert job.started_at is None
        assert job.completed_at is None
        
        # Process job
        generate_certificates_for_job(str(job.id))
        
        # Refresh job from database
        from sqlalchemy import select
        from app.models.job import GenerationJob
        result = await db_session.execute(
            select(GenerationJob).where(GenerationJob.id == job.id)
        )
        updated_job = result.scalar_one()
        
        # Verify timestamps are set
        assert updated_job.started_at is not None
        assert updated_job.completed_at is not None
        assert updated_job.completed_at >= updated_job.started_at
    
    finally:
        settings.certificate_storage_path = original_storage


@pytest.mark.skip(reason="Requires actual database transaction - tested via Docker integration")
@pytest.mark.asyncio
async def test_workflow_validation_error_handling(db_session, tmp_path):
    """Test that validation errors at processing time are handled gracefully."""
    original_storage = settings.certificate_storage_path
    settings.certificate_storage_path = str(tmp_path)
    
    try:
        # Create job (bypassing normal validation for this test)
        from app.models.job import GenerationJob
        from app.models.certificate import CertificateRecord
        from datetime import datetime
        
        job = GenerationJob(
            status="PENDING",
            total_recipients=1,
            completed_count=0,
            failed_count=0
        )
        db_session.add(job)
        await db_session.flush()
        
        # Create certificate with invalid data (empty name)
        cert = CertificateRecord(
            job_id=job.id,
            recipient_name="",  # Invalid
            recipient_email="test@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 15),
            status="PENDING"
        )
        db_session.add(cert)
        await db_session.commit()
        
        # Process job
        result = generate_certificates_for_job(str(job.id))
        
        # Verify validation error was caught and certificate marked as FAILED
        assert result["status"] == "FAILED"
        assert result["failed"] == 1
        
        # Refresh certificate
        from sqlalchemy import select
        result = await db_session.execute(
            select(CertificateRecord).where(CertificateRecord.id == cert.id)
        )
        updated_cert = result.scalar_one()
        
        assert updated_cert.status == "FAILED"
        assert "validation failed" in updated_cert.error_message.lower()
    
    finally:
        settings.certificate_storage_path = original_storage


@pytest.mark.asyncio
async def test_workflow_empty_batch_rejected_at_api(db_session, override_get_db):
    """Test that empty batches are rejected at API validation level."""
    request_data = {"recipients": []}
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/jobs", json=request_data)
    
    # Should be rejected by Pydantic validation before reaching task
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_workflow_oversized_batch_rejected_at_api(db_session, override_get_db):
    """Test that oversized batches are rejected at API level."""
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
