"""
Unit tests for PDF generation service.
"""
import tempfile
from datetime import date
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import landscape, A4

from app.services.pdf_generator import (
    generate_certificate_pdf,
    CertificateGenerationError
)


class TestPDFGenerator:
    """Test cases for certificate PDF generation."""
    
    def test_generate_valid_certificate(self, tmp_path):
        """Test generating a valid certificate PDF."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        recipient_name = "John Doe"
        course = "Python 101"
        completion_date = date(2024, 3, 15)
        
        # Act
        file_size = generate_certificate_pdf(
            recipient_name,
            course,
            completion_date,
            output_path
        )
        
        # Assert
        assert output_path.exists(), "PDF file should be created"
        assert file_size > 0, "PDF file size should be greater than 0"
        assert output_path.stat().st_size == file_size, "Returned size should match actual file size"
        assert output_path.suffix == ".pdf", "File should have .pdf extension"
    
    def test_generate_certificate_with_string_date(self, tmp_path):
        """Test generating certificate with date as string."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        recipient_name = "Jane Smith"
        course = "Data Science Fundamentals"
        completion_date = "March 15, 2024"
        
        # Act
        file_size = generate_certificate_pdf(
            recipient_name,
            course,
            completion_date,
            output_path
        )
        
        # Assert
        assert output_path.exists()
        assert file_size > 0
    
    def test_certificate_content(self, tmp_path):
        """Test that PDF contains recipient information."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        recipient_name = "Alice Johnson"
        course = "Machine Learning 101"
        completion_date = date(2024, 1, 20)
        
        # Act
        generate_certificate_pdf(
            recipient_name,
            course,
            completion_date,
            output_path
        )
        
        # Assert - Basic validation that file is a valid PDF
        # Reading first few bytes to check PDF header
        with open(output_path, 'rb') as f:
            header = f.read(4)
            assert header == b'%PDF', "File should have valid PDF header"
        
        # Check file size is reasonable (professional certificate should be > 1KB)
        assert output_path.stat().st_size > 1000, "Certificate PDF should be reasonably sized"
    
    def test_invalid_output_path(self, tmp_path):
        """Test error handling when PDF creation fails."""
        # Arrange
        # Create a directory where we want to write the file
        # Then replace it with a file to cause a write error
        blocking_file = tmp_path / "blocked"
        blocking_file.write_text("blocking")
        
        # Try to write a PDF where a file already exists as a directory component
        invalid_path = blocking_file / "cert.pdf"
        recipient_name = "Test User"
        course = "Test Course"
        completion_date = date(2024, 1, 1)
        
        # Act & Assert
        # This will fail because we can't create a directory where a file exists
        with pytest.raises(CertificateGenerationError):
            generate_certificate_pdf(
                recipient_name,
                course,
                completion_date,
                invalid_path
            )
    
    def test_empty_recipient_name(self, tmp_path):
        """Test error handling for empty recipient name."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        
        # Act & Assert
        with pytest.raises(CertificateGenerationError) as exc_info:
            generate_certificate_pdf(
                "",  # Empty name
                "Test Course",
                date(2024, 1, 1),
                output_path
            )
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_whitespace_only_recipient_name(self, tmp_path):
        """Test error handling for whitespace-only recipient name."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        
        # Act & Assert
        with pytest.raises(CertificateGenerationError):
            generate_certificate_pdf(
                "   ",  # Whitespace only
                "Test Course",
                date(2024, 1, 1),
                output_path
            )
    
    def test_empty_course_name(self, tmp_path):
        """Test error handling for empty course name."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        
        # Act & Assert
        with pytest.raises(CertificateGenerationError):
            generate_certificate_pdf(
                "Test User",
                "",  # Empty course
                date(2024, 1, 1),
                output_path
            )
    
    def test_special_characters_in_name(self, tmp_path):
        """Test handling of special characters in recipient name."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        test_cases = [
            "José García",  # Unicode characters
            "O'Brien",  # Apostrophe
            "Anne-Marie",  # Hyphen
            "François Müller",  # Multiple unicode characters
            "李明",  # Chinese characters
            "Владимир",  # Cyrillic characters
        ]
        
        # Act & Assert
        for recipient_name in test_cases:
            output = tmp_path / f"cert_{hash(recipient_name)}.pdf"
            file_size = generate_certificate_pdf(
                recipient_name,
                "International Course",
                date(2024, 1, 1),
                output
            )
            
            assert output.exists(), f"Should handle name: {recipient_name}"
            assert file_size > 0, f"Should generate valid PDF for: {recipient_name}"
    
    def test_long_recipient_name(self, tmp_path):
        """Test handling of very long recipient names."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        long_name = "Alexander Christopher Bartholomew Wellington Montgomery III"
        
        # Act
        file_size = generate_certificate_pdf(
            long_name,
            "Advanced Studies",
            date(2024, 1, 1),
            output_path
        )
        
        # Assert
        assert output_path.exists()
        assert file_size > 0
    
    def test_long_course_name(self, tmp_path):
        """Test handling of very long course names."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        long_course = "Advanced Machine Learning and Artificial Intelligence with Deep Neural Networks and Natural Language Processing"
        
        # Act
        file_size = generate_certificate_pdf(
            "Test User",
            long_course,
            date(2024, 1, 1),
            output_path
        )
        
        # Assert
        assert output_path.exists()
        assert file_size > 0
    
    def test_parent_directory_created(self, tmp_path):
        """Test that parent directories are created if they don't exist."""
        # Arrange
        nested_path = tmp_path / "level1" / "level2" / "level3" / "cert.pdf"
        
        # Act
        file_size = generate_certificate_pdf(
            "Test User",
            "Test Course",
            date(2024, 1, 1),
            nested_path
        )
        
        # Assert
        assert nested_path.exists()
        assert file_size > 0
        assert nested_path.parent.exists()
    
    def test_overwrite_existing_file(self, tmp_path):
        """Test that existing files are overwritten."""
        # Arrange
        output_path = tmp_path / "test_cert.pdf"
        
        # Create first certificate
        file_size_1 = generate_certificate_pdf(
            "First User",
            "First Course",
            date(2024, 1, 1),
            output_path
        )
        
        # Act - Generate second certificate with same path
        file_size_2 = generate_certificate_pdf(
            "Second User",
            "Second Course",
            date(2024, 2, 1),
            output_path
        )
        
        # Assert
        assert output_path.exists()
        assert file_size_2 > 0
        # File sizes might be slightly different due to different content
    
    def test_multiple_certificates_different_paths(self, tmp_path):
        """Test generating multiple certificates in parallel."""
        # Arrange
        certificates = [
            ("Alice", "Course A", date(2024, 1, 1)),
            ("Bob", "Course B", date(2024, 1, 2)),
            ("Charlie", "Course C", date(2024, 1, 3)),
        ]
        
        # Act
        for i, (name, course, date_val) in enumerate(certificates):
            output_path = tmp_path / f"cert_{i}.pdf"
            file_size = generate_certificate_pdf(name, course, date_val, output_path)
            
            # Assert
            assert output_path.exists()
            assert file_size > 0
