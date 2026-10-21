"""
Unit tests for file management service.
"""
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.services.file_manager import FileManager, FileManagerError


class TestFileManager:
    """Test cases for FileManager class."""
    
    def test_initialization_with_default_path(self):
        """Test FileManager initialization with default settings path."""
        # Act
        fm = FileManager()
        
        # Assert
        assert fm.base_path is not None
        assert fm.base_path.exists(), "Base path should be created on initialization"
    
    def test_initialization_with_custom_path(self, tmp_path):
        """Test FileManager initialization with custom base path."""
        # Arrange
        custom_path = tmp_path / "custom_certs"
        
        # Act
        fm = FileManager(base_path=custom_path)
        
        # Assert
        assert fm.base_path == custom_path
        assert fm.base_path.exists(), "Custom base path should be created"
    
    def test_generate_certificate_path(self, tmp_path):
        """Test generating certificate file path."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        job_id = uuid4()
        cert_id = uuid4()
        
        # Act
        cert_path = fm.generate_certificate_path(job_id, cert_id)
        
        # Assert
        assert cert_path.parent == tmp_path / str(job_id)
        assert cert_path.name == f"{cert_id}.pdf"
        assert str(job_id) in str(cert_path)
        assert str(cert_id) in str(cert_path)
    
    def test_generate_certificate_path_format(self, tmp_path):
        """Test that certificate path follows correct format."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        job_id = uuid4()
        cert_id = uuid4()
        
        # Act
        cert_path = fm.generate_certificate_path(job_id, cert_id)
        
        # Assert
        expected_path = tmp_path / str(job_id) / f"{cert_id}.pdf"
        assert cert_path == expected_path
    
    def test_ensure_job_directory(self, tmp_path):
        """Test creating job directory."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        job_id = uuid4()
        
        # Act
        job_dir = fm.ensure_job_directory(job_id)
        
        # Assert
        assert job_dir.exists(), "Job directory should be created"
        assert job_dir.is_dir(), "Job directory should be a directory"
        assert job_dir == tmp_path / str(job_id)
    
    def test_ensure_job_directory_idempotent(self, tmp_path):
        """Test that ensure_job_directory is idempotent."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        job_id = uuid4()
        
        # Act - Call twice
        job_dir_1 = fm.ensure_job_directory(job_id)
        job_dir_2 = fm.ensure_job_directory(job_id)
        
        # Assert
        assert job_dir_1 == job_dir_2
        assert job_dir_1.exists()
        # Should not raise any errors
    
    def test_ensure_job_directory_multiple_jobs(self, tmp_path):
        """Test creating directories for multiple jobs."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        job_ids = [uuid4() for _ in range(5)]
        
        # Act
        job_dirs = [fm.ensure_job_directory(job_id) for job_id in job_ids]
        
        # Assert
        for job_dir in job_dirs:
            assert job_dir.exists()
            assert job_dir.is_dir()
        
        # All directories should be different
        assert len(set(job_dirs)) == 5
    
    def test_get_certificate_filename_basic(self, tmp_path):
        """Test generating safe filename from recipient name."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        cert_id = uuid4()
        
        # Act
        filename = fm.get_certificate_filename("John Doe", cert_id)
        
        # Assert
        assert filename.endswith(f"_{cert_id}.pdf")
        assert "john_doe" in filename.lower()
        assert filename.startswith("john_doe")
    
    def test_get_certificate_filename_special_characters(self, tmp_path):
        """Test filename sanitization with special characters."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        cert_id = uuid4()
        test_cases = [
            ("O'Brien", "obrien"),  # Apostrophe removed
            ("José García", "josé_garcía"),  # Unicode preserved, space to underscore
            ("Anne-Marie", "anne_marie"),  # Hyphen to underscore
            ("User@Company", "usercompany"),  # @ removed
            ("Test/Path", "testpath"),  # / removed
            ("Test\\Path", "testpath"),  # \ removed
            ("User<Name>", "username"),  # < > removed
        ]
        
        # Act & Assert
        for input_name, expected_part in test_cases:
            filename = fm.get_certificate_filename(input_name, cert_id)
            
            # Should not contain dangerous characters
            assert "/" not in filename
            assert "\\" not in filename
            assert "<" not in filename
            assert ">" not in filename
            assert ".." not in filename
            
            # Should contain sanitized version
            assert expected_part in filename.lower()
    
    def test_get_certificate_filename_path_traversal_prevention(self, tmp_path):
        """Test that path traversal attempts are sanitized."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        cert_id = uuid4()
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "....//....//etc",
        ]
        
        # Act & Assert
        for malicious_name in malicious_names:
            filename = fm.get_certificate_filename(malicious_name, cert_id)
            
            # Should not contain path traversal patterns
            assert ".." not in filename
            assert "/" not in filename
            assert "\\" not in filename
            
            # Should be a safe filename
            assert filename.endswith(".pdf")
    
    def test_get_certificate_filename_unicode(self, tmp_path):
        """Test handling unicode characters in filenames."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        cert_id = uuid4()
        unicode_names = [
            "李明",
            "Владимир",
            "François",
            "Müller",
        ]
        
        # Act & Assert
        for name in unicode_names:
            filename = fm.get_certificate_filename(name, cert_id)
            
            # Should generate valid filename
            assert filename.endswith(".pdf")
            assert str(cert_id) in filename
            
            # Should not contain problematic characters
            assert "/" not in filename
            assert "\\" not in filename
    
    def test_get_certificate_filename_empty_name(self, tmp_path):
        """Test handling empty name after sanitization."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        cert_id = uuid4()
        
        # Act
        filename = fm.get_certificate_filename("@#$%^&*()", cert_id)
        
        # Assert
        assert filename.startswith("certificate_")
        assert filename.endswith(".pdf")
        assert str(cert_id) in filename
    
    def test_get_certificate_filename_long_name(self, tmp_path):
        """Test that very long names are truncated."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        cert_id = uuid4()
        long_name = "A" * 200  # Very long name
        
        # Act
        filename = fm.get_certificate_filename(long_name, cert_id)
        
        # Assert
        # Name should be truncated to reasonable length
        assert len(filename) < 100  # Should be much shorter than 200
        assert filename.endswith(".pdf")
    
    def test_get_certificate_filename_whitespace(self, tmp_path):
        """Test handling of whitespace in names."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        cert_id = uuid4()
        
        # Act
        filename = fm.get_certificate_filename("John   Doe", cert_id)
        
        # Assert
        assert filename.startswith("john_doe")
        # Multiple spaces should be collapsed to single underscore
        assert "___" not in filename
    
    def test_validate_storage_path_success(self, tmp_path):
        """Test successful storage path validation."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        
        # Act
        result = fm.validate_storage_path()
        
        # Assert
        assert result is True
        assert fm.base_path.exists()
    
    def test_validate_storage_path_creates_directory(self, tmp_path):
        """Test that validate_storage_path creates directory if needed."""
        # Arrange
        storage_path = tmp_path / "new_storage"
        fm = FileManager(base_path=storage_path)
        
        # Remove the directory that was created in __init__
        storage_path.rmdir()
        assert not storage_path.exists()
        
        # Act
        result = fm.validate_storage_path()
        
        # Assert
        assert result is True
        assert storage_path.exists()
    
    def test_get_certificate_size_existing_file(self, tmp_path):
        """Test getting size of existing certificate file."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        test_file = tmp_path / "test.pdf"
        test_content = b"PDF content here"
        test_file.write_bytes(test_content)
        
        # Act
        file_size = fm.get_certificate_size(test_file)
        
        # Assert
        assert file_size == len(test_content)
        assert file_size > 0
    
    def test_get_certificate_size_nonexistent_file(self, tmp_path):
        """Test error handling for nonexistent file."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        nonexistent_file = tmp_path / "does_not_exist.pdf"
        
        # Act & Assert
        with pytest.raises(FileManagerError):
            fm.get_certificate_size(nonexistent_file)
    
    def test_full_workflow(self, tmp_path):
        """Test complete workflow: create directory, generate path, validate."""
        # Arrange
        fm = FileManager(base_path=tmp_path)
        job_id = uuid4()
        cert_id = uuid4()
        
        # Act
        # 1. Validate storage
        assert fm.validate_storage_path()
        
        # 2. Ensure job directory exists
        job_dir = fm.ensure_job_directory(job_id)
        assert job_dir.exists()
        
        # 3. Generate certificate path
        cert_path = fm.generate_certificate_path(job_id, cert_id)
        assert cert_path.parent == job_dir
        
        # 4. Create a dummy certificate file
        cert_path.write_bytes(b"dummy PDF content")
        
        # 5. Get file size
        file_size = fm.get_certificate_size(cert_path)
        assert file_size > 0
        
        # Assert - Everything should work together
        assert cert_path.exists()
        assert cert_path.is_file()
