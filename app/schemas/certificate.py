"""
Pydantic schemas for certificate-related API responses.
Handles validation for certificate retrieval endpoints.
"""
from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class CertificateResponse(BaseModel):
    """
    Response schema for individual certificate information.
    
    Provides details about a generated certificate including download URL.
    """
    certificate_id: UUID = Field(description="Unique certificate identifier")
    recipient_name: str = Field(description="Full name of the recipient")
    recipient_email: str = Field(description="Email address of the recipient")
    status: str = Field(description="Certificate generation status")
    generated_at: datetime | None = Field(description="When the certificate was generated")
    file_size_bytes: int | None = Field(description="Size of the PDF file in bytes")
    download_url: str | None = Field(description="URL to download the certificate")
    error_message: str | None = Field(description="Error message if generation failed")
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "certificate_id": "660e8400-e29b-41d4-a716-446655440000",
                "recipient_name": "John Doe",
                "recipient_email": "john@example.com",
                "status": "SUCCESS",
                "generated_at": "2024-01-15T10:35:00Z",
                "file_size_bytes": 45678,
                "download_url": "/api/v1/certificates/660e8400-e29b-41d4-a716-446655440000/download",
                "error_message": None
            }
        }
    }


class CertificateListResponse(BaseModel):
    """
    Response schema for paginated list of certificates.
    
    Used for listing certificates within a specific job.
    """
    job_id: UUID = Field(description="ID of the parent job")
    total: int = Field(description="Total number of certificates in this job")
    limit: int = Field(description="Maximum number of certificates per page")
    offset: int = Field(description="Number of certificates skipped")
    certificates: List[CertificateResponse] = Field(description="List of certificates in this page")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "total": 100,
                "limit": 20,
                "offset": 0,
                "certificates": []
            }
        }
    }
