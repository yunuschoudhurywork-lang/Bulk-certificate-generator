"""
Certificate service for managing individual certificate records.
Handles certificate retrieval, status updates, and progress tracking.

ARCHITECTURE NOTE - Async/Sync Boundary:
=====================================
This service layer uses async methods designed for FastAPI route handlers
that use asyncpg (async PostgreSQL driver). Celery tasks use direct 
synchronous ORM operations with psycopg2 (sync driver) for simplicity.

See app/services/job_service.py for detailed explanation of this
architectural decision.
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certificate import CertificateRecord


logger = logging.getLogger(__name__)


class CertificateService:
    """
    Service class for managing certificate records.
    
    Provides methods for retrieving certificates, updating their status,
    and tracking individual certificate generation outcomes.
    """
    
    @staticmethod
    async def get_certificates_by_job(
        job_id: UUID,
        db: AsyncSession,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[CertificateRecord], int]:
        """
        Retrieve certificate records for a specific job.
        
        Args:
            job_id: UUID of the generation job
            db: Async database session
            status_filter: Optional status to filter by (PENDING, SUCCESS, FAILED)
            limit: Maximum number of certificates to return
            offset: Number of certificates to skip
            
        Returns:
            Tuple of (list of certificate records, total count)
        """
        # Build base query
        query = select(CertificateRecord).where(
            CertificateRecord.job_id == job_id
        )
        
        count_query = select(func.count()).select_from(CertificateRecord).where(
            CertificateRecord.job_id == job_id
        )
        
        # Apply status filter if provided
        if status_filter:
            query = query.where(CertificateRecord.status == status_filter)
            count_query = count_query.where(CertificateRecord.status == status_filter)
        
        # Get total count
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()
        
        # Get paginated results ordered by created_at
        query = query.order_by(CertificateRecord.created_at).limit(limit).offset(offset)
        result = await db.execute(query)
        certificates = result.scalars().all()
        
        return list(certificates), total
    
    @staticmethod
    async def get_certificate_by_id(
        cert_id: UUID,
        db: AsyncSession
    ) -> Optional[CertificateRecord]:
        """
        Retrieve a certificate record by its ID.
        
        Args:
            cert_id: UUID of the certificate record
            db: Async database session
            
        Returns:
            CertificateRecord if found, None otherwise
        """
        result = await db.execute(
            select(CertificateRecord).where(CertificateRecord.id == cert_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def mark_certificate_success(
        cert_id: UUID,
        file_path: str,
        file_size: int,
        db: AsyncSession
    ) -> Optional[CertificateRecord]:
        """
        Mark a certificate as successfully generated.
        
        Updates the status, file path, file size, and generation timestamp.
        
        Args:
            cert_id: UUID of the certificate record
            file_path: Path to the generated PDF file
            file_size: Size of the generated file in bytes
            db: Async database session
            
        Returns:
            Updated CertificateRecord if found, None otherwise
        """
        cert = await CertificateService.get_certificate_by_id(cert_id, db)
        
        if cert is None:
            logger.warning(f"Certificate {cert_id} not found for success update")
            return None
        
        cert.status = "SUCCESS"
        cert.file_path = file_path
        cert.file_size_bytes = file_size
        cert.generated_at = datetime.utcnow()
        cert.error_message = None  # Clear any previous error
        
        await db.commit()
        await db.refresh(cert)
        
        logger.info(
            f"Marked certificate {cert_id} as SUCCESS "
            f"(file: {file_path}, size: {file_size} bytes)"
        )
        
        return cert
    
    @staticmethod
    async def mark_certificate_failed(
        cert_id: UUID,
        error_message: str,
        db: AsyncSession
    ) -> Optional[CertificateRecord]:
        """
        Mark a certificate as failed.
        
        Updates the status and stores the error message for debugging.
        
        Args:
            cert_id: UUID of the certificate record
            error_message: Description of the failure
            db: Async database session
            
        Returns:
            Updated CertificateRecord if found, None otherwise
        """
        cert = await CertificateService.get_certificate_by_id(cert_id, db)
        
        if cert is None:
            logger.warning(f"Certificate {cert_id} not found for failure update")
            return None
        
        cert.status = "FAILED"
        cert.error_message = error_message
        
        await db.commit()
        await db.refresh(cert)
        
        logger.warning(
            f"Marked certificate {cert_id} as FAILED: {error_message}"
        )
        
        return cert
