"""
PDF certificate generation service using ReportLab.
Provides the main function to generate personalized certificates.
"""
import logging
from pathlib import Path
from datetime import date
from typing import Union

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4

from app.templates.certificate_template import (
    draw_certificate_border,
    draw_certificate_header,
    draw_recipient_info,
    draw_certificate_footer,
    PAGE_WIDTH,
    PAGE_HEIGHT
)


logger = logging.getLogger(__name__)


class CertificateGenerationError(Exception):
    """Raised when certificate generation fails."""
    pass


def generate_certificate_pdf(
    recipient_name: str,
    course: str,
    completion_date: Union[date, str],
    output_path: Path
) -> int:
    """
    Generate a personalized certificate PDF.
    
    Creates a professional certificate with the recipient's information
    using the predefined template design.
    
    Args:
        recipient_name: Full name of the certificate recipient
        course: Name of the completed course
        completion_date: Date of course completion (date object or string)
        output_path: Path where the PDF file should be saved
        
    Returns:
        File size in bytes of the generated PDF
        
    Raises:
        CertificateGenerationError: If PDF generation fails (disk full, 
            permission denied, invalid parameters, etc.)
    """
    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Format completion date
        if isinstance(completion_date, date):
            formatted_date = completion_date.strftime("%B %d, %Y")
        else:
            formatted_date = str(completion_date)
        
        # Validate input parameters
        if not recipient_name or not recipient_name.strip():
            raise ValueError("Recipient name cannot be empty")
        if not course or not course.strip():
            raise ValueError("Course name cannot be empty")
        
        # Create canvas with A4 landscape orientation
        c = canvas.Canvas(str(output_path), pagesize=landscape(A4))
        
        # Draw certificate components
        draw_certificate_border(c)
        draw_certificate_header(c)
        draw_recipient_info(c, recipient_name.strip(), course.strip(), formatted_date)
        draw_certificate_footer(c)
        
        # Save the PDF
        c.save()
        
        # Get file size
        if not output_path.exists():
            raise CertificateGenerationError(
                f"PDF file was not created at {output_path}"
            )
        
        file_size = output_path.stat().st_size
        
        logger.info(
            f"Successfully generated certificate for '{recipient_name}' "
            f"at {output_path} ({file_size} bytes)"
        )
        
        return file_size
        
    except ValueError as e:
        logger.error(f"Validation error generating certificate: {e}")
        raise CertificateGenerationError(f"Invalid input: {e}") from e
    
    except PermissionError as e:
        logger.error(f"Permission denied writing to {output_path}: {e}")
        raise CertificateGenerationError(
            f"Permission denied: Cannot write to {output_path}"
        ) from e
    
    except OSError as e:
        # Catches disk full, I/O errors, etc.
        logger.error(f"OS error generating certificate at {output_path}: {e}")
        raise CertificateGenerationError(
            f"File system error: {e}"
        ) from e
    
    except Exception as e:
        logger.error(f"Unexpected error generating certificate: {e}", exc_info=True)
        raise CertificateGenerationError(
            f"Failed to generate certificate: {e}"
        ) from e
