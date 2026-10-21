#!/usr/bin/env python3
"""
Manual verification script for the fixes applied.
This script checks that the code changes are syntactically correct
and follow the expected patterns.
"""
import ast
import sys
from pathlib import Path


def verify_atomic_updates():
    """Verify atomic SQL UPDATE statements are used."""
    print("🔍 Verifying atomic progress counter updates...")
    
    task_file = Path("app/tasks/generate.py")
    content = task_file.read_text()
    
    # Check for atomic UPDATE imports
    checks = [
        ("✓ Imports 'update' from sqlalchemy", "from sqlalchemy import" in content and "update" in content),
        ("✓ Imports ValidationError", "from pydantic import ValidationError" in content),
        ("✓ Imports RecipientInput schema", "from app.schemas.job import RecipientInput" in content),
        ("✓ Uses atomic completed_count increment", "update(GenerationJob)" in content and "completed_count=GenerationJob.completed_count + 1" in content),
        ("✓ Uses atomic failed_count increment", "update(GenerationJob)" in content and "failed_count=GenerationJob.failed_count + 1" in content),
        ("✓ No Python-side += for job counters", "job.completed_count +=" not in content and "job.failed_count +=" not in content),
    ]
    
    for check, result in checks:
        if result:
            print(f"  {check}")
        else:
            print(f"  ✗ FAILED: {check}")
            return False
    
    return True


def verify_validation_in_task():
    """Verify runtime validation is added in task."""
    print("\n🔍 Verifying runtime validation in task...")
    
    task_file = Path("app/tasks/generate.py")
    content = task_file.read_text()
    
    checks = [
        ("✓ Validates recipient data during processing", "RecipientInput.model_validate" in content),
        ("✓ Catches ValidationError", "except ValidationError" in content),
        ("✓ Continues processing on validation failure", "continue" in content),
        ("✓ Marks invalid as FAILED with error message", 'cert.status = "FAILED"' in content and "Data validation failed" in content),
    ]
    
    for check, result in checks:
        if result:
            print(f"  {check}")
        else:
            print(f"  ✗ FAILED: {check}")
            return False
    
    return True


def verify_documentation():
    """Verify architecture documentation is added."""
    print("\n🔍 Verifying architecture documentation...")
    
    checks = []
    
    for service_file in ["app/services/job_service.py", "app/services/certificate_service.py"]:
        content = Path(service_file).read_text()
        has_arch_note = "ARCHITECTURE NOTE" in content or "Async/Sync" in content
        checks.append((f"✓ {service_file} has architecture note", has_arch_note))
    
    for check, result in checks:
        if result:
            print(f"  {check}")
        else:
            print(f"  ✗ FAILED: {check}")
            return False
    
    return True


def verify_syntax():
    """Verify Python syntax is valid."""
    print("\n🔍 Verifying Python syntax...")
    
    files = [
        "app/tasks/generate.py",
        "app/services/job_service.py",
        "app/services/certificate_service.py",
    ]
    
    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
            print(f"  ✓ {filepath} - syntax valid")
        except SyntaxError as e:
            print(f"  ✗ {filepath} - SYNTAX ERROR: {e}")
            return False
    
    return True


def main():
    print("=" * 60)
    print("VERIFICATION SCRIPT FOR FIXES")
    print("=" * 60)
    
    all_passed = True
    
    all_passed &= verify_syntax()
    all_passed &= verify_atomic_updates()
    all_passed &= verify_validation_in_task()
    all_passed &= verify_documentation()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL VERIFICATIONS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
