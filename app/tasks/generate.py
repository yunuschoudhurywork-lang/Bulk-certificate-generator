"""
Celery task for bulk certificate generation.
Processes certificate generation jobs asynchronously in the background.
"""
import logging
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker
from pydantic import ValidationError

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.certificate import CertificateRecord
from app.models.job import GenerationJob
from app.schemas.job import RecipientInput
from app.services.file_manager import FileManager
from app.services.pdf_generator import generate_certificate_pdf


logger = logging.getLogger(__name__)


# Create synchronous database engine for Celery worker
# Convert async URL to sync URL (asyncpg -> psycopg2)
sync_db_url = settings.database_url.replace(
    "postgresql+asyncpg://",
    "postgresql+psycopg2://"
)

sync_engine = create_engine(
    sync_db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_certificates_for_job(self, job_id: str) -> dict:
    """
    Generate certificates for all recipients in a job.
    
    This is the main Celery task that processes a certificate generation job.
    It iterates through all PENDING certificate records, generates PDFs,
    and updates the job status accordingly.
    
    Individual certificate failures do not stop the task - the task continues
    processing valid recipients and tracks failures separately.
    
    Args:
        self: Celery task instance (injected by bind=True)
        job_id: String representation of the job UUID
        
    Returns:
        Dictionary with job processing summary:
        {
            'job_id': str,
            'status': str,
            'completed': int,
            'failed': int,
            'total': int
        }
        
    Raises:
        Exception: Only for critical database errors that prevent task execution.
                  Individual certificate generation errors are caught and logged.
    """
    logger.info(f"Starting certificate generation for job {job_id}")
    
    job_uuid = UUID(job_id)
    db: Session = SyncSessionLocal()
    file_manager = FileManager()
    
    try:
        # Get the job
        job = db.query(GenerationJob).filter(GenerationJob.id == job_uuid).first()
        
        if not job:
            logger.error(f"Job {job_id} not found")
            raise ValueError(f"Job {job_id} not found")
        
        # Update job status to PROCESSING
        job.status = "PROCESSING"
        job.started_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Job {job_id} status updated to PROCESSING")
        
        # Get all PENDING certificate records for this job
        pending_certs = db.query(CertificateRecord).filter(
            CertificateRecord.job_id == job_uuid,
            CertificateRecord.status == "PENDING"
        ).all()
        
        logger.info(f"Found {len(pending_certs)} pending certificates to process")
        
        # Ensure job directory exists
        try:
            file_manager.ensure_job_directory(job_uuid)
        except Exception as e:
            logger.error(f"Failed to create job directory: {e}")
            job.status = "FAILED"
            job.completed_at = datetime.utcnow()
            db.commit()
            raise
        
        # Process each certificate
        for cert in pending_certs:
            try:
                # Validate recipient data at processing time
                # Catches edge cases that may have passed API validation
                try:
                    RecipientInput.model_validate({
                        "name": cert.recipient_name,
                        "email": cert.recipient_email,
                        "course": cert.course,
                        "completion_date": cert.completion_date
                    })
                except ValidationError as ve:
                    # Invalid data - mark as failed, continue with others
                    error_msg = f"Data validation failed: {str(ve)}"
                    logger.warning(
                        f"Certificate {cert.id} validation failed for "
                        f"{cert.recipient_name}: {ve}"
                    )
                    cert.status = "FAILED"
                    cert.error_message = error_msg[:500]
                    
                    # Atomic increment of failed count at database level
                    db.execute(
                        update(GenerationJob)
                        .where(GenerationJob.id == job_uuid)
                        .values(failed_count=GenerationJob.failed_count + 1)
                    )
                    db.commit()
                    continue
                
                # Generate file path
                file_path = file_manager.generate_certificate_path(
                    job_uuid,
                    cert.id
                )
                
                # Generate the certificate PDF
                file_size = generate_certificate_pdf(
                    recipient_name=cert.recipient_name,
                    course=cert.course,
                    completion_date=cert.completion_date,
                    output_path=file_path
                )
                
                # Mark certificate as SUCCESS
                cert.status = "SUCCESS"
                cert.file_path = str(file_path.relative_to(Path(settings.certificate_storage_path)))
                cert.file_size_bytes = file_size
                cert.generated_at = datetime.utcnow()
                cert.error_message = None
                
                # Atomic increment of completed count at database level
                # Prevents race condition with concurrent workers
                db.execute(
                    update(GenerationJob)
                    .where(GenerationJob.id == job_uuid)
                    .values(completed_count=GenerationJob.completed_count + 1)
                )
                
                db.commit()
                
                logger.info(
                    f"Successfully generated certificate {cert.id} "
                    f"for {cert.recipient_name}"
                )
                
            except Exception as e:
                # Log the error but continue processing other certificates
                error_msg = f"Failed to generate certificate: {str(e)}"
                logger.error(
                    f"Error generating certificate {cert.id} "
                    f"for {cert.recipient_name}: {e}",
                    exc_info=True
                )
                
                # Mark certificate as FAILED
                cert.status = "FAILED"
                cert.error_message = error_msg[:500]  # Truncate to fit in database
                
                # Atomic increment of failed count at database level
                db.execute(
                    update(GenerationJob)
                    .where(GenerationJob.id == job_uuid)
                    .values(failed_count=GenerationJob.failed_count + 1)
                )
                
                db.commit()
        
        # Finalize job status based on results
        if job.failed_count == 0:
            final_status = "COMPLETED"
        elif job.failed_count < job.total_recipients:
            final_status = "COMPLETED_WITH_ERRORS"
        else:
            final_status = "FAILED"
        
        job.status = final_status
        job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(
            f"Job {job_id} completed with status {final_status}: "
            f"{job.completed_count} successful, {job.failed_count} failed "
            f"out of {job.total_recipients} total"
        )
        
        return {
            'job_id': str(job.id),
            'status': final_status,
            'completed': job.completed_count,
            'failed': job.failed_count,
            'total': job.total_recipients
        }
        
    except Exception as e:
        logger.error(f"Critical error processing job {job_id}: {e}", exc_info=True)
        
        # Try to update job status to FAILED if possible
        try:
            job = db.query(GenerationJob).filter(GenerationJob.id == job_uuid).first()
            if job:
                job.status = "FAILED"
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as inner_e:
            logger.error(f"Failed to update job status after error: {inner_e}")
        
        # Retry on database errors, but not on validation errors
        if "database" in str(e).lower() or "connection" in str(e).lower():
            logger.info(f"Retrying job {job_id} due to database error")
            raise self.retry(exc=e)
        
        raise
        
    finally:
        db.close()
