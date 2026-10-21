"""
API routes for certificate generation jobs.
Handles job creation, status retrieval, and certificate listing.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.job import CreateJobRequest, JobResponse
from app.schemas.certificate import CertificateResponse, CertificateListResponse
from app.services.job_service import JobService
from app.services.certificate_service import CertificateService
from app.tasks.generate import generate_certificates_for_job


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    request: CreateJobRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new bulk certificate generation job.
    
    Validates the request, creates a job with recipient records,
    and queues the background processing task.
    
    Args:
        request: Bulk generation request with list of recipients
        db: Database session
        
    Returns:
        JobResponse with job details and initial status
        
    Raises:
        HTTPException 400: If recipient count exceeds maximum allowed
    """
    # Validate recipient count against configuration
    if len(request.recipients) > settings.max_recipients_per_job:
        raise HTTPException(
            status_code=400,
            detail=f"Recipient count ({len(request.recipients)}) exceeds maximum allowed ({settings.max_recipients_per_job})"
        )
    
    logger.info(f"Creating job with {len(request.recipients)} recipients")
    
    # Create job and certificate records in a single transaction
    job = await JobService.create_job_with_recipients(request.recipients, db)
    
    # Queue Celery task for background processing
    generate_certificates_for_job.delay(str(job.id))
    
    logger.info(f"Job {job.id} created and queued for processing")
    
    # Build response
    return JobResponse(
        job_id=job.id,
        status=job.status,
        total_recipients=job.total_recipients,
        completed_count=job.completed_count,
        failed_count=job.failed_count,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the status and progress of a generation job.
    
    Args:
        job_id: UUID of the job
        db: Database session
        
    Returns:
        JobResponse with current job status and progress
        
    Raises:
        HTTPException 404: If job not found
    """
    job = await JobService.get_job_by_id(job_id, db)
    
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    return JobResponse(
        job_id=job.id,
        status=job.status,
        total_recipients=job.total_recipients,
        completed_count=job.completed_count,
        failed_count=job.failed_count,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


@router.get("/jobs/{job_id}/certificates", response_model=CertificateListResponse)
async def list_certificates(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by status (PENDING, SUCCESS, FAILED)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """
    List certificates for a specific job with optional filtering.
    
    Args:
        job_id: UUID of the job
        db: Database session
        status: Optional status filter
        limit: Maximum results per page
        offset: Pagination offset
        
    Returns:
        CertificateListResponse with paginated certificate list
        
    Raises:
        HTTPException 404: If job not found
    """
    # Verify job exists
    job = await JobService.get_job_by_id(job_id, db)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    # Get certificates
    certificates, total = await CertificateService.get_certificates_by_job(
        job_id=job_id,
        db=db,
        status_filter=status,
        limit=limit,
        offset=offset
    )
    
    # Build response with download URLs
    cert_responses = []
    for cert in certificates:
        # Only provide download URL for successfully generated certificates
        download_url = None
        if cert.status == "SUCCESS":
            download_url = f"/api/v1/certificates/{cert.id}/download"
        
        cert_responses.append(CertificateResponse(
            certificate_id=cert.id,
            recipient_name=cert.recipient_name,
            recipient_email=cert.recipient_email,
            status=cert.status,
            generated_at=cert.generated_at,
            file_size_bytes=cert.file_size_bytes,
            download_url=download_url,
            error_message=cert.error_message
        ))
    
    return CertificateListResponse(
        job_id=job_id,
        total=total,
        limit=limit,
        offset=offset,
        certificates=cert_responses
    )
