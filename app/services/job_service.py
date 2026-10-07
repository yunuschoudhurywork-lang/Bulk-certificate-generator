"""
Job service for managing certificate generation jobs.
Handles job creation, status tracking, and progress updates.

ARCHITECTURE NOTE - Async/Sync Boundary:
=====================================
This service layer uses async methods designed for FastAPI route handlers
that use asyncpg (async PostgreSQL driver). Celery tasks use direct 
synchronous ORM operations with psycopg2 (sync driver) for simplicity.

This separation is intentional for MVP:
- FastAPI API layer: async services + AsyncSession + asyncpg
- Celery worker layer: direct ORM + Session + psycopg2
- Both share the same models but use different database engines

Benefits:
- No async/await complexity in Celery workers (Celery is synchronous)
- Clear separation between API and background processing layers
- No connection pool conflicts between async and sync engines

Trade-off:
- Some code duplication between services and task logic
- Services cannot be directly reused in Celery tasks

Future enhancement: Consider creating sync service variants for code reuse
between API and worker layers if duplication becomes significant.
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import GenerationJob
from app.models.certificate import CertificateRecord
from app.schemas.job import RecipientInput


logger = logging.getLogger(__name__)


class JobService:
    """
    Service class for managing generation jobs.
    
    Provides methods for creating jobs, tracking progress,
    and managing job status transitions.
    """
    
    @staticmethod
    async def create_job_with_recipients(
        recipients: List[RecipientInput],
        db: AsyncSession
    ) -> GenerationJob:
        """
        Create a new generation job with certificate records for all recipients.
        
        This operation is atomic - both the job and all certificate records
        are created in a single transaction.
        
        Args:
            recipients: List of recipient information
            db: Async database session
            
        Returns:
            Created GenerationJob with relationships loaded
            
        Raises:
            Exception: If database transaction fails
        """
        try:
            # Create the job
            job = GenerationJob(
                status="PENDING",
                total_recipients=len(recipients),
                completed_count=0,
                failed_count=0
            )
            db.add(job)
            
            # Flush to get the job ID
            await db.flush()
            
            # Create certificate records for all recipients
            certificate_records = []
            for recipient in recipients:
                cert_record = CertificateRecord(
                    job_id=job.id,
                    recipient_name=recipient.name,
                    recipient_email=recipient.email,
                    course=recipient.course,
                    completion_date=recipient.completion_date,
                    status="PENDING"
                )
                certificate_records.append(cert_record)
                db.add(cert_record)
            
            # Commit the transaction
            await db.commit()
            
            # Refresh to load relationships
            await db.refresh(job)
            
            logger.info(
                f"Created job {job.id} with {len(recipients)} recipients"
            )
            
            return job
            
        except Exception as e:
            logger.error(f"Error creating job with recipients: {e}")
            await db.rollback()
            raise
    
    @staticmethod
    async def get_job_by_id(
        job_id: UUID,
        db: AsyncSession
    ) -> Optional[GenerationJob]:
        """
        Retrieve a generation job by its ID.
        
        Args:
            job_id: UUID of the job
            db: Async database session
            
        Returns:
            GenerationJob if found, None otherwise
        """
        result = await db.execute(
            select(GenerationJob).where(GenerationJob.id == job_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_job_status(
        job_id: UUID,
        status: str,
        db: AsyncSession,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> Optional[GenerationJob]:
        """
        Update the status of a generation job.
        
        Args:
            job_id: UUID of the job
            status: New status value
            db: Async database session
            started_at: Optional timestamp when processing started
            completed_at: Optional timestamp when processing completed
            
        Returns:
            Updated GenerationJob if found, None otherwise
        """
        job = await JobService.get_job_by_id(job_id, db)
        
        if job is None:
            logger.warning(f"Job {job_id} not found for status update")
            return None
        
        job.status = status
        
        if started_at is not None:
            job.started_at = started_at
        
        if completed_at is not None:
            job.completed_at = completed_at
        
        await db.commit()
        await db.refresh(job)
        
        logger.info(f"Updated job {job_id} status to {status}")
        
        return job
    
    @staticmethod
    async def increment_completed(
        job_id: UUID,
        db: AsyncSession
    ) -> Optional[GenerationJob]:
        """
        Increment the completed count for a job.
        
        Args:
            job_id: UUID of the job
            db: Async database session
            
        Returns:
            Updated GenerationJob if found, None otherwise
        """
        job = await JobService.get_job_by_id(job_id, db)
        
        if job is None:
            logger.warning(f"Job {job_id} not found for increment_completed")
            return None
        
        job.completed_count += 1
        
        await db.commit()
        await db.refresh(job)
        
        return job
    
    @staticmethod
    async def increment_failed(
        job_id: UUID,
        db: AsyncSession
    ) -> Optional[GenerationJob]:
        """
        Increment the failed count for a job.
        
        Args:
            job_id: UUID of the job
            db: Async database session
            
        Returns:
            Updated GenerationJob if found, None otherwise
        """
        job = await JobService.get_job_by_id(job_id, db)
        
        if job is None:
            logger.warning(f"Job {job_id} not found for increment_failed")
            return None
        
        job.failed_count += 1
        
        await db.commit()
        await db.refresh(job)
        
        return job
    
    @staticmethod
    async def finalize_job_status(
        job_id: UUID,
        db: AsyncSession
    ) -> Optional[GenerationJob]:
        """
        Finalize the job status based on completed and failed counts.
        
        Logic:
        - If failed_count == 0: COMPLETED
        - If 0 < failed_count < total_recipients: COMPLETED_WITH_ERRORS
        - If failed_count == total_recipients: FAILED
        
        Also sets the completed_at timestamp.
        
        Args:
            job_id: UUID of the job
            db: Async database session
            
        Returns:
            Updated GenerationJob if found, None otherwise
        """
        job = await JobService.get_job_by_id(job_id, db)
        
        if job is None:
            logger.warning(f"Job {job_id} not found for finalization")
            return None
        
        # Determine final status based on counts
        if job.failed_count == 0:
            final_status = "COMPLETED"
        elif job.failed_count < job.total_recipients:
            final_status = "COMPLETED_WITH_ERRORS"
        else:
            final_status = "FAILED"
        
        job.status = final_status
        job.completed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(job)
        
        logger.info(
            f"Finalized job {job_id} with status {final_status} "
            f"(completed: {job.completed_count}, failed: {job.failed_count})"
        )
        
        return job
    
    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[GenerationJob], int]:
        """
        List generation jobs with pagination.
        
        Args:
            db: Async database session
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            
        Returns:
            Tuple of (list of jobs, total count)
        """
        # Get total count
        count_result = await db.execute(
            select(func.count()).select_from(GenerationJob)
        )
        total = count_result.scalar_one()
        
        # Get paginated jobs ordered by created_at descending
        result = await db.execute(
            select(GenerationJob)
            .order_by(GenerationJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        jobs = result.scalars().all()
        
        return list(jobs), total
