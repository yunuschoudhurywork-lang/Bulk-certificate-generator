#!/usr/bin/env python
"""
Manual test script to verify PDF generation works.
Run this inside Docker container:
  docker-compose exec api python test_manual_pdf.py
"""
from datetime import date
from pathlib import Path

from app.services.pdf_generator import generate_certificate_pdf
from app.services.file_manager import FileManager


def main():
    """Generate a test certificate and verify it works."""
    print("=" * 60)
    print("Manual PDF Generation Test")
    print("=" * 60)
    
    # Setup
    output_dir = Path("/tmp/test_certificates")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "test_certificate.pdf"
    
    # Test data
    recipient_name = "John Doe"
    course = "Python 101: Introduction to Programming"
    completion_date = date(2024, 3, 15)
    
    print(f"\nGenerating certificate for: {recipient_name}")
    print(f"Course: {course}")
    print(f"Date: {completion_date}")
    print(f"Output: {output_path}")
    
    try:
        # Generate certificate
        file_size = generate_certificate_pdf(
            recipient_name=recipient_name,
            course=course,
            completion_date=completion_date,
            output_path=output_path
        )
        
        print(f"\n✓ Certificate generated successfully!")
        print(f"  File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
        print(f"  Location: {output_path}")
        
        # Verify with FileManager
        fm = FileManager()
        verified_size = fm.get_certificate_size(output_path)
        print(f"\n✓ FileManager verification:")
        print(f"  Verified size: {verified_size:,} bytes")
        
        # Test with special characters
        print("\n" + "=" * 60)
        print("Testing special characters...")
        print("=" * 60)
        
        special_names = [
            "José García",
            "François Müller",
            "李明",
            "O'Brien"
        ]
        
        for name in special_names:
            special_output = output_dir / f"test_{hash(name)}.pdf"
            size = generate_certificate_pdf(
                recipient_name=name,
                course="International Course",
                completion_date=date(2024, 1, 1),
                output_path=special_output
            )
            print(f"  ✓ {name}: {size:,} bytes")
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        print(f"\nYou can now view the generated PDFs in: {output_dir}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
