"""
GenerationJob SQLAlchemy model.
Tracks bulk certificate generation jobs and their progress.
"""
from datetime import datetime
from typing import List, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, String, TIMESTAMP, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.certificate import CertificateRecord


class GenerationJob(Base):
    """
    Represents a bulk certificate generation job.
    
    Tracks the overall status and progress of generating certificates
    for multiple recipients in a single batch.
    """
    __tablename__ = "generation_jobs"
    
    # Primary key with PostgreSQL UUID generation
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique job identifier"
    )
    
    # Status tracking with constraint
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        comment="Current job status"
    )
    
    # Progress counters
    total_recipients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total number of recipients in this job"
    )
    
    completed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of successfully generated certificates"
    )
    
    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Number of failed certificate generations"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When the job was created"
    )
    
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When the job processing started"
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When the job finished (success or failure)"
    )
    
    # Relationship to certificate records
    certificate_records: Mapped[List["CertificateRecord"]] = relationship(
        "CertificateRecord",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED')",
            name="valid_job_status"
        ),
        Index("ix_generation_jobs_status", "status"),
        Index("ix_generation_jobs_created_at_desc", "created_at", postgresql_ops={"created_at": "DESC"}),
    )
    
    def __repr__(self) -> str:
        return f"<GenerationJob(id={self.id}, status={self.status}, total={self.total_recipients})>"
