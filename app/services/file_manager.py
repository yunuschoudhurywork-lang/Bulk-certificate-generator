"""
File management service for certificate storage.
Handles path generation, directory creation, and storage validation.
"""
import logging
import os
import re
from pathlib import Path
from uuid import UUID
from typing import Optional

from app.core.config import settings


logger = logging.getLogger(__name__)


class FileManagerError(Exception):
    """Raised when file management operations fail."""
    pass


class FileManager:
    """
    Manages file paths and storage for generated certificates.
    
    Provides utilities for generating consistent file paths, creating
    directories, and validating storage availability.
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize the FileManager.
        
        Args:
            base_path: Base directory for certificate storage. 
                      Defaults to settings.certificate_storage_path
        """
        if base_path is None:
            self.base_path = Path(settings.certificate_storage_path)
        else:
            self.base_path = Path(base_path)
        
        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def generate_certificate_path(self, job_id: UUID, cert_id: UUID) -> Path:
        """
        Generate the full path for a certificate file.
        
        Creates a hierarchical path structure:
        base_path/certificates/<job_id>/<cert_id>.pdf
        
        Args:
            job_id: UUID of the generation job
            cert_id: UUID of the certificate record
            
        Returns:
            Path object for the certificate file
        """
        job_dir = self.base_path / str(job_id)
        return job_dir / f"{cert_id}.pdf"
    
    def ensure_job_directory(self, job_id: UUID) -> Path:
        """
        Ensure the directory for a job exists.
        
        Creates the job directory if it doesn't exist.
        Operation is idempotent - no error if directory already exists.
        
        Args:
            job_id: UUID of the generation job
            
        Returns:
            Path object for the job directory
            
        Raises:
            FileManagerError: If directory creation fails
        """
        job_dir = self.base_path / str(job_id)
        
        try:
            job_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured job directory exists: {job_dir}")
            return job_dir
        except PermissionError as e:
            logger.error(f"Permission denied creating directory {job_dir}: {e}")
            raise FileManagerError(
                f"Permission denied: Cannot create directory {job_dir}"
            ) from e
        except OSError as e:
            logger.error(f"OS error creating directory {job_dir}: {e}")
            raise FileManagerError(
                f"Failed to create directory {job_dir}: {e}"
            ) from e
    
    def get_certificate_filename(self, recipient_name: str, cert_id: UUID) -> str:
        """
        Generate a safe filename for a certificate.
        
        Creates a filename from the recipient name and certificate ID,
        sanitizing special characters to prevent path traversal attacks
        and ensure cross-platform compatibility.
        
        Args:
            recipient_name: Name of the certificate recipient
            cert_id: UUID of the certificate record
            
        Returns:
            Safe filename string (e.g., "john_doe_<uuid>.pdf")
        """
        # Sanitize the recipient name
        # Remove or replace characters that are problematic in filenames
        safe_name = re.sub(r'[^\w\s-]', '', recipient_name.lower())
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        
        # Truncate to reasonable length
        safe_name = safe_name[:50]
        
        # Remove leading/trailing underscores
        safe_name = safe_name.strip('_')
        
        # If name is empty after sanitization, use generic name
        if not safe_name:
            safe_name = "certificate"
        
        return f"{safe_name}_{cert_id}.pdf"
    
    def validate_storage_path(self) -> bool:
        """
        Validate that the storage path is accessible and writable.
        
        Checks:
        - Directory exists or can be created
        - Write permissions are available
        - Basic disk space is available
        
        Returns:
            True if storage path is valid and writable
            
        Raises:
            FileManagerError: If storage path is not usable
        """
        try:
            # Ensure directory exists
            self.base_path.mkdir(parents=True, exist_ok=True)
            
            # Check write permissions by creating a test file
            test_file = self.base_path / ".storage_test"
            try:
                test_file.touch()
                test_file.unlink()
            except PermissionError:
                raise FileManagerError(
                    f"No write permission for storage path: {self.base_path}"
                )
            
            # Check disk space (warn if less than 100MB available)
            if os.name != 'nt':  # Unix-like systems
                stat = os.statvfs(self.base_path)
                free_space = stat.f_bavail * stat.f_frsize
                if free_space < 100 * 1024 * 1024:  # 100MB
                    logger.warning(
                        f"Low disk space in certificate storage: {free_space / (1024*1024):.2f} MB remaining"
                    )
            
            logger.info(f"Storage path validated: {self.base_path}")
            return True
            
        except Exception as e:
            logger.error(f"Storage path validation failed: {e}")
            raise FileManagerError(f"Invalid storage path: {e}") from e
    
    def get_certificate_size(self, file_path: Path) -> int:
        """
        Get the size of a certificate file in bytes.
        
        Args:
            file_path: Path to the certificate file
            
        Returns:
            File size in bytes
            
        Raises:
            FileManagerError: If file doesn't exist or can't be read
        """
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"Certificate file not found: {file_path}")
            
            return file_path.stat().st_size
            
        except Exception as e:
            logger.error(f"Error getting file size for {file_path}: {e}")
            raise FileManagerError(f"Cannot read file: {e}") from e
