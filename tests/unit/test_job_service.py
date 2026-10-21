"""
Unit tests for JobService.
Tests job creation, status updates, and progress tracking.
"""
import pytest
from datetime import datetime, date
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import GenerationJob
from app.models.certificate import CertificateRecord
from app.schemas.job import RecipientInput
from app.services.job_service import JobService


@pytest.mark.asyncio
async def test_create_job_with_recipients(db_session: AsyncSession):
    """Test creating a job with multiple recipients in a single transaction."""
    recipients = [
        RecipientInput(
            name="John Doe",
            email="john@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        ),
        RecipientInput(
            name="Jane Smith",
            email="jane@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        ),
        RecipientInput(
            name="Bob Johnson",
            email="bob@example.com",
            course="Python 101",
            completion_date=date(2024, 1, 15)
        )
    ]
    
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Verify job was created with correct attributes
    assert job.id is not None
    assert job.status == "PENDING"
    assert job.total_recipients == 3
    assert job.completed_count == 0
    assert job.failed_count == 0
    assert job.created_at is not None
    assert job.started_at is None
    assert job.completed_at is None
    
    # Verify certificate records were created
    assert len(job.certificate_records) == 3
    
    # Verify certificate record details
    cert_names = {cert.recipient_name for cert in job.certificate_records}
    assert cert_names == {"John Doe", "Jane Smith", "Bob Johnson"}
    
    for cert in job.certificate_records:
        assert cert.status == "PENDING"
        assert cert.job_id == job.id
        assert cert.course == "Python 101"
        assert cert.completion_date == date(2024, 1, 15)


@pytest.mark.asyncio
async def test_get_job_by_id(db_session: AsyncSession):
    """Test retrieving a job by its ID."""
    # Create a job
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 1)
        )
    ]
    created_job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Retrieve the job
    retrieved_job = await JobService.get_job_by_id(created_job.id, db_session)
    
    assert retrieved_job is not None
    assert retrieved_job.id == created_job.id
    assert retrieved_job.status == "PENDING"


@pytest.mark.asyncio
async def test_get_job_by_id_not_found(db_session: AsyncSession):
    """Test retrieving a non-existent job returns None."""
    fake_id = uuid4()
    job = await JobService.get_job_by_id(fake_id, db_session)
    
    assert job is None


@pytest.mark.asyncio
async def test_update_job_status(db_session: AsyncSession):
    """Test updating job status with timestamps."""
    # Create a job
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 1)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Update status to PROCESSING with started_at
    started_time = datetime.utcnow()
    updated_job = await JobService.update_job_status(
        job.id,
        "PROCESSING",
        db_session,
        started_at=started_time
    )
    
    assert updated_job is not None
    assert updated_job.status == "PROCESSING"
    assert updated_job.started_at is not None
    assert updated_job.completed_at is None
    
    # Update status to COMPLETED with completed_at
    completed_time = datetime.utcnow()
    updated_job = await JobService.update_job_status(
        job.id,
        "COMPLETED",
        db_session,
        completed_at=completed_time
    )
    
    assert updated_job.status == "COMPLETED"
    assert updated_job.completed_at is not None


@pytest.mark.asyncio
async def test_increment_completed(db_session: AsyncSession):
    """Test incrementing the completed count."""
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 1)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    assert job.completed_count == 0
    
    # Increment once
    updated_job = await JobService.increment_completed(job.id, db_session)
    assert updated_job.completed_count == 1
    
    # Increment again
    updated_job = await JobService.increment_completed(job.id, db_session)
    assert updated_job.completed_count == 2


@pytest.mark.asyncio
async def test_increment_failed(db_session: AsyncSession):
    """Test incrementing the failed count."""
    recipients = [
        RecipientInput(
            name="Test User",
            email="test@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 1)
        )
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    assert job.failed_count == 0
    
    # Increment once
    updated_job = await JobService.increment_failed(job.id, db_session)
    assert updated_job.failed_count == 1
    
    # Increment again
    updated_job = await JobService.increment_failed(job.id, db_session)
    assert updated_job.failed_count == 2


@pytest.mark.asyncio
async def test_finalize_job_status_all_success(db_session: AsyncSession):
    """Test finalizing job status when all certificates succeed."""
    recipients = [
        RecipientInput(
            name=f"User {i}",
            email=f"user{i}@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 1)
        )
        for i in range(5)
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Simulate all successes
    for _ in range(5):
        await JobService.increment_completed(job.id, db_session)
    
    # Finalize
    finalized_job = await JobService.finalize_job_status(job.id, db_session)
    
    assert finalized_job.status == "COMPLETED"
    assert finalized_job.completed_at is not None
    assert finalized_job.completed_count == 5
    assert finalized_job.failed_count == 0


@pytest.mark.asyncio
async def test_finalize_job_status_partial_failure(db_session: AsyncSession):
    """Test finalizing job status when some certificates fail."""
    recipients = [
        RecipientInput(
            name=f"User {i}",
            email=f"user{i}@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 1)
        )
        for i in range(5)
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Simulate 3 successes and 2 failures
    for _ in range(3):
        await JobService.increment_completed(job.id, db_session)
    for _ in range(2):
        await JobService.increment_failed(job.id, db_session)
    
    # Finalize
    finalized_job = await JobService.finalize_job_status(job.id, db_session)
    
    assert finalized_job.status == "COMPLETED_WITH_ERRORS"
    assert finalized_job.completed_at is not None
    assert finalized_job.completed_count == 3
    assert finalized_job.failed_count == 2


@pytest.mark.asyncio
async def test_finalize_job_status_all_failed(db_session: AsyncSession):
    """Test finalizing job status when all certificates fail."""
    recipients = [
        RecipientInput(
            name=f"User {i}",
            email=f"user{i}@example.com",
            course="Test Course",
            completion_date=date(2024, 1, 1)
        )
        for i in range(5)
    ]
    job = await JobService.create_job_with_recipients(recipients, db_session)
    
    # Simulate all failures
    for _ in range(5):
        await JobService.increment_failed(job.id, db_session)
    
    # Finalize
    finalized_job = await JobService.finalize_job_status(job.id, db_session)
    
    assert finalized_job.status == "FAILED"
    assert finalized_job.completed_at is not None
    assert finalized_job.completed_count == 0
    assert finalized_job.failed_count == 5


@pytest.mark.asyncio
async def test_list_jobs_empty(db_session: AsyncSession):
    """Test listing jobs when database is empty."""
    jobs, total = await JobService.list_jobs(db_session, limit=10, offset=0)
    
    assert jobs == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_jobs_pagination(db_session: AsyncSession):
    """Test listing jobs with pagination."""
    # Create 5 jobs
    for i in range(5):
        recipients = [
            RecipientInput(
                name=f"User {i}",
                email=f"user{i}@example.com",
                course="Test Course",
                completion_date=date(2024, 1, 1)
            )
        ]
        await JobService.create_job_with_recipients(recipients, db_session)
    
    # Get first page (limit 2)
    jobs_page1, total = await JobService.list_jobs(db_session, limit=2, offset=0)
    assert len(jobs_page1) == 2
    assert total == 5
    
    # Get second page
    jobs_page2, total = await JobService.list_jobs(db_session, limit=2, offset=2)
    assert len(jobs_page2) == 2
    assert total == 5
    
    # Get third page
    jobs_page3, total = await JobService.list_jobs(db_session, limit=2, offset=4)
    assert len(jobs_page3) == 1
    assert total == 5
    
    # Ensure jobs are ordered by created_at descending (newest first)
    # The last created job should appear first
    all_jobs, _ = await JobService.list_jobs(db_session, limit=10, offset=0)
    for i in range(len(all_jobs) - 1):
        assert all_jobs[i].created_at >= all_jobs[i + 1].created_at
