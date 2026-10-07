"""SQLAlchemy database models."""

from app.models.certificate import CertificateRecord
from app.models.job import GenerationJob

__all__ = ["GenerationJob", "CertificateRecord"]
