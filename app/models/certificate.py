"""
CertificateRecord SQLAlchemy model.
Tracks individual certificate generation records within a job.
"""
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.job import GenerationJob


class CertificateRecord(Base):
    """
    Represents an individual certificate generation record.
    
    Each record corresponds to one recipient within a generation job.
    Tracks the status, recipient information, and generated file details.
    """
    __tablename__ = "certificate_records"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique certificate record identifier"
    )
    
    # Foreign key to parent job with cascade delete
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to the parent generation job"
    )
    
    # Recipient information
    recipient_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Full name of the certificate recipient"
    )
    
    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email address of the recipient"
    )
    
    course: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Course name for the certificate"
    )
    
    completion_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Course completion date"
    )
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        comment="Certificate generation status"
    )
    
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if generation failed"
    )
    
    # Generated file information
    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Relative path to the generated PDF file"
    )
    
    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Size of the generated PDF in bytes"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the record was created"
    )
    
    generated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When the certificate was successfully generated"
    )
    
    # Relationship back to job
    job: Mapped["GenerationJob"] = relationship(
        "GenerationJob",
        back_populates="certificate_records"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'SUCCESS', 'FAILED')",
            name="valid_certificate_status"
        ),
        Index("ix_certificate_records_job_id", "job_id"),
        Index("ix_certificate_records_status", "status"),
        Index("ix_certificate_records_recipient_email", "recipient_email"),
    )
    
    def __repr__(self) -> str:
        return f"<CertificateRecord(id={self.id}, recipient={self.recipient_name}, status={self.status})>"
