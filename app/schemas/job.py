"""
Pydantic schemas for job-related API requests and responses.
Handles validation for certificate generation job endpoints.
"""
from datetime import date, datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RecipientInput(BaseModel):
    """
    Input schema for a single certificate recipient.
    
    Validates recipient information before certificate generation.
    """
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Full name of the recipient",
        examples=["John Doe"]
    )
    
    email: EmailStr = Field(
        description="Email address of the recipient",
        examples=["john.doe@example.com"]
    )
    
    course: str = Field(
        min_length=1,
        max_length=200,
        description="Course or program name",
        examples=["Advanced Python Programming"]
    )
    
    completion_date: date = Field(
        description="Date when the course was completed",
        examples=["2024-01-15"]
    )
    
    @field_validator("completion_date")
    @classmethod
    def validate_completion_date(cls, v: date) -> date:
        """Ensure completion date is not in the future."""
        if v > date.today():
            raise ValueError("completion_date cannot be in the future")
        return v
    
    @field_validator("name", "course")
    @classmethod
    def validate_not_empty(cls, v: str, info) -> str:
        """Ensure string fields are not just whitespace."""
        if not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty or whitespace only")
        return v.strip()


class CreateJobRequest(BaseModel):
    """
    Request schema for creating a bulk certificate generation job.
    
    Contains a list of recipients for whom certificates should be generated.
    """
    recipients: List[RecipientInput] = Field(
        min_length=1,
        max_length=1000,
        description="List of recipients for certificate generation",
        examples=[[
            {
                "name": "John Doe",
                "email": "john@example.com",
                "course": "Python 101",
                "completion_date": "2024-01-15"
            }
        ]]
    )


class JobResponse(BaseModel):
    """
    Response schema for job status and progress information.
    
    Provides detailed information about a certificate generation job.
    """
    job_id: UUID = Field(description="Unique job identifier")
    status: str = Field(description="Current job status")
    total_recipients: int = Field(description="Total number of recipients")
    completed_count: int = Field(description="Number of successfully generated certificates")
    failed_count: int = Field(description="Number of failed certificate generations")
    pending_count: int = Field(description="Number of certificates still pending")
    created_at: datetime = Field(description="When the job was created")
    started_at: datetime | None = Field(description="When processing started")
    completed_at: datetime | None = Field(description="When the job finished")
    progress_percentage: float = Field(description="Completion percentage (0-100)")
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "PROCESSING",
                "total_recipients": 100,
                "completed_count": 45,
                "failed_count": 2,
                "pending_count": 53,
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:05Z",
                "completed_at": None,
                "progress_percentage": 47.0
            }
        }
    }


class JobListResponse(BaseModel):
    """
    Response schema for paginated list of jobs.
    
    Used for listing multiple generation jobs with pagination.
    """
    total: int = Field(description="Total number of jobs matching the query")
    limit: int = Field(description="Maximum number of jobs per page")
    offset: int = Field(description="Number of jobs skipped")
    jobs: List[JobResponse] = Field(description="List of jobs in this page")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "total": 150,
                "limit": 20,
                "offset": 0,
                "jobs": []
            }
        }
    }
