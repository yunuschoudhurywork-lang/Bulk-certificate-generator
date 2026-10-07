# FEAT-003 Verification Checklist

## Pre-requisites
- [ ] Docker and Docker Compose installed
- [ ] Project built: `docker-compose build`
- [ ] Services running: `docker-compose up -d`

---

## Verification Steps

### 1. Unit Tests - PDF Generator
```bash
docker-compose exec api pytest tests/unit/test_pdf_generator.py -v
```

**Expected Result:**
- ✅ All 16 tests pass
- ✅ No errors or failures
- ✅ Tests cover: valid generation, content, errors, special chars, unicode

**What to Look For:**
- `test_generate_valid_certificate PASSED`
- `test_certificate_content PASSED`
- `test_special_characters_in_name PASSED`
- All tests green

---

### 2. Unit Tests - File Manager
```bash
docker-compose exec api pytest tests/unit/test_file_manager.py -v
```

**Expected Result:**
- ✅ All 24 tests pass
- ✅ No errors or failures
- ✅ Tests cover: paths, directories, sanitization, security

**What to Look For:**
- `test_generate_certificate_path PASSED`
- `test_get_certificate_filename_path_traversal_prevention PASSED`
- `test_validate_storage_path_success PASSED`
- All tests green

---

### 3. Test Coverage Check
```bash
docker-compose exec api pytest tests/unit/ --cov=app.services --cov-report=term
```

**Expected Result:**
- ✅ Coverage > 80% for `app.services.pdf_generator`
- ✅ Coverage > 80% for `app.services.file_manager`

**What to Look For:**
```
app/services/pdf_generator.py    XX      X     XX%
app/services/file_manager.py     XX      X     XX%
```

---

### 4. Manual PDF Generation Test
```bash
docker-compose exec api python test_manual_pdf.py
```

**Expected Result:**
- ✅ Generates test_certificate.pdf
- ✅ File size reported (should be 5-15 KB)
- ✅ Special character tests pass
- ✅ "All tests passed! ✓" message

**What to Look For:**
```
Manual PDF Generation Test
========================================
✓ Certificate generated successfully!
  File size: X,XXX bytes (XX.XX KB)
  
Testing special characters...
  ✓ José García: X,XXX bytes
  ✓ François Müller: X,XXX bytes
  ✓ 李明: X,XXX bytes
  ✓ O'Brien: X,XXX bytes

All tests passed! ✓
```

---

### 5. View Generated PDF
```bash
# Copy PDF from container to host
docker-compose exec api cat /tmp/test_certificates/test_certificate.pdf > test_certificate.pdf

# Or on Windows PowerShell:
docker-compose exec api cat /tmp/test_certificates/test_certificate.pdf | Set-Content -Path test_certificate.pdf -Encoding Byte
```

**Expected Result:**
- ✅ PDF opens in viewer (Adobe, Chrome, etc.)
- ✅ Title: "Certificate of Completion"
- ✅ Contains: "John Doe"
- ✅ Contains: "Python 101: Introduction to Programming"
- ✅ Contains: "March 15, 2024"
- ✅ Gold border visible
- ✅ Professional appearance

---

### 6. Quick Import Test
```bash
docker-compose exec api python -c "from app.services import generate_certificate_pdf, FileManager; print('✓ Imports successful!')"
```

**Expected Result:**
- ✅ `✓ Imports successful!`
- ✅ No import errors
- ✅ No module not found errors

---

### 7. Storage Path Validation on Startup
```bash
docker-compose logs api | grep -i "storage\|certificate"
```

**Expected Result:**
- ✅ Log entry: "Certificate storage validated at: ..."
- ✅ No storage validation errors
- ✅ Application starts successfully

---

### 8. Generate Sample Certificate Programmatically
```bash
docker-compose exec api python -c "
from app.services.pdf_generator import generate_certificate_pdf
from pathlib import Path
from datetime import date

p = Path('/tmp/sample_verification.pdf')
size = generate_certificate_pdf(
    'Verification Test User',
    'Advanced Python Programming',
    date(2024, 3, 15),
    p
)
print(f'✓ Generated: {size} bytes at {p}')
print(f'✓ File exists: {p.exists()}')
"
```

**Expected Result:**
```
✓ Generated: X,XXX bytes at /tmp/sample_verification.pdf
✓ File exists: True
```

---

### 9. Test FileManager Path Generation
```bash
docker-compose exec api python -c "
from app.services.file_manager import FileManager
from uuid import UUID

fm = FileManager()
job_id = UUID('12345678-1234-5678-1234-567812345678')
cert_id = UUID('87654321-4321-8765-4321-876543218765')

path = fm.generate_certificate_path(job_id, cert_id)
print(f'✓ Path format correct: {str(path)}')

job_dir = fm.ensure_job_directory(job_id)
print(f'✓ Job directory created: {job_dir.exists()}')

safe_name = fm.get_certificate_filename('Test../../../etc/passwd', cert_id)
print(f'✓ Path traversal prevented: {safe_name}')
print(f'✓ No dots in filename: {\"..\" not in safe_name}')
"
```

**Expected Result:**
```
✓ Path format correct: .../certificates/12345678-1234-5678-1234-567812345678/87654321-4321-8765-4321-876543218765.pdf
✓ Job directory created: True
✓ Path traversal prevented: test_etcpasswd_87654321-4321-8765-4321-876543218765.pdf
✓ No dots in filename: True
```

---

### 10. Verify Error Handling
```bash
docker-compose exec api python -c "
from app.services.pdf_generator import generate_certificate_pdf, CertificateGenerationError
from pathlib import Path
from datetime import date

try:
    generate_certificate_pdf('', 'Course', date(2024, 1, 1), Path('/tmp/test.pdf'))
    print('✗ Should have raised error for empty name')
except CertificateGenerationError as e:
    print(f'✓ Correctly raised error: {str(e)[:50]}...')
"
```

**Expected Result:**
```
✓ Correctly raised error: Invalid input: Recipient name cannot be empty
```

---

## Success Criteria

All of the following must be true:

- [ ] All 16 PDF generator tests pass
- [ ] All 24 file manager tests pass  
- [ ] Test coverage > 80% for both services
- [ ] Manual test script completes successfully
- [ ] Generated PDF is viewable and contains correct information
- [ ] Imports work without errors
- [ ] Storage validation succeeds on startup
- [ ] Sample certificate generation works programmatically
- [ ] FileManager correctly generates paths and prevents traversal
- [ ] Error handling works as expected (empty name raises error)

---

## Common Issues and Solutions

### Issue: "No module named 'reportlab'"
**Solution:** Rebuild Docker image: `docker-compose build`

### Issue: "Permission denied" when creating directories
**Solution:** Check Docker volume permissions, ensure `/app/data` is writable

### Issue: Tests fail with import errors
**Solution:** Ensure `PYTHONPATH` is set correctly in Docker, rebuild if needed

### Issue: PDF doesn't render correctly
**Solution:** Check that reportlab version is 4.1.0, verify fonts are available

### Issue: Unicode characters appear as boxes
**Solution:** This is a ReportLab limitation with Helvetica; working as expected for standard fonts

---

## Notes

- **Docker Required:** All verification must run inside Docker container
- **Local Testing:** Not possible without reportlab installed locally
- **PDF Viewing:** Some viewers may render fonts differently
- **Performance:** PDF generation should take < 100ms per certificate

---

**Verification Date:** _____________  
**Verified By:** _____________  
**Result:** ☐ Pass  ☐ Fail  
**Notes:** _____________________________________________
