"""
API routes for certificate download.
Handles serving generated certificate PDF files.
"""
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.certificate_service import CertificateService


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/certificates/{certificate_id}/download")
async def download_certificate(
    certificate_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Download a generated certificate PDF.
    
    The certificate must have status SUCCESS for download to be available.
    
    Args:
        certificate_id: UUID of the certificate
        db: Database session
        
    Returns:
        FileResponse with the PDF file
        
    Raises:
        HTTPException 404: If certificate not found, not yet generated, or file missing
    """
    # Get certificate record
    cert = await CertificateService.get_certificate_by_id(certificate_id, db)
    
    if cert is None:
        raise HTTPException(
            status_code=404,
            detail=f"Certificate {certificate_id} not found"
        )
    
    # Check if certificate has been successfully generated
    if cert.status != "SUCCESS":
        raise HTTPException(
            status_code=404,
            detail=f"Certificate {certificate_id} is not available for download (status: {cert.status})"
        )
    
    # Construct full file path
    storage_path = Path(settings.certificate_storage_path)
    file_path = storage_path / cert.file_path
    
    # Validate path to prevent directory traversal attacks
    # Resolve both paths and ensure the file stays within storage directory
    try:
        storage_path_resolved = storage_path.resolve()
        file_path_resolved = file_path.resolve()
        
        if not file_path_resolved.is_relative_to(storage_path_resolved):
            logger.error(f"Path traversal attempt detected: {cert.file_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Certificate file not found on server"
            )
    except (ValueError, OSError) as e:
        logger.error(f"Path resolution error for certificate {certificate_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Certificate file not found on server"
        )
    
    # Verify file exists on disk
    if not file_path_resolved.exists():
        logger.error(f"Certificate file missing: {file_path_resolved}")
        raise HTTPException(
            status_code=404,
            detail=f"Certificate file not found on server"
        )
    
    # Prepare filename for download
    # Format: RecipientName_CertificateID.pdf
    safe_name = cert.recipient_name.replace(" ", "_")
    filename = f"{safe_name}_{certificate_id}.pdf"
    
    logger.info(f"Serving certificate {certificate_id} to download")
    
    return FileResponse(
        path=str(file_path_resolved),
        media_type="application/pdf",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
