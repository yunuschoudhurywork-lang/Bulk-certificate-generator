"""
End-to-End Workflow Verification Script.
Exercises the full live flow:
1. Submit bulk job request via API
2. Celery worker picks up task from Redis asynchronously
3. Worker processes recipients, generates PDFs, updates progress counters and status
4. API returns updated job status, 100% progress, COMPLETED status
5. API returns certificate records with download URLs
6. API serves generated PDF via download endpoint
7. Validate downloaded PDF content and integrity
"""
import asyncio
import time
from datetime import date
from httpx import AsyncClient

from app.main import app
from app.core.config import settings


async def run_e2e_verification():
    print("=" * 60)
    print("LIVE END-TO-END WORKFLOW VERIFICATION")
    print("=" * 60)
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Step 1: Submit bulk certificate generation request
        print("\n1. Submitting bulk job request via POST /api/v1/jobs...")
        payload = {
            "recipients": [
                {
                    "name": "Grace Hopper",
                    "email": "grace.hopper@example.com",
                    "course": "Compilers & Computing",
                    "completion_date": "2024-05-01"
                },
                {
                    "name": "Alan Turing",
                    "email": "alan.turing@example.com",
                    "course": "Theoretical Computer Science",
                    "completion_date": "2024-05-02"
                },
                {
                    "name": "Ada Lovelace",
                    "email": "ada.lovelace@example.com",
                    "course": "Analytical Engines",
                    "completion_date": "2024-05-03"
                }
            ]
        }
        
        response = await client.post("/api/v1/jobs", json=payload)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        job_id = data["job_id"]
        print(f"   [SUCCESS] Job created: {job_id}")
        print(f"   Status: {data['status']}, Total recipients: {data['total_recipients']}")
        
        # Step 2: Poll GET /api/v1/jobs/{job_id} until Celery worker finishes processing
        print(f"\n2. Polling GET /api/v1/jobs/{job_id} for asynchronous processing...")
        max_wait = 20  # seconds
        start_time = time.time()
        final_job_data = None
        
        while time.time() - start_time < max_wait:
            res = await client.get(f"/api/v1/jobs/{job_id}")
            assert res.status_code == 200, f"Expected 200, got {res.status_code}"
            job_info = res.json()
            status = job_info["status"]
            print(f"   Status: {status} | Completed: {job_info['completed_count']} | Failed: {job_info['failed_count']} | Progress: {job_info['progress_percentage']}%")
            
            if status in ("COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"):
                final_job_data = job_info
                break
            await asyncio.sleep(1)
            
        assert final_job_data is not None, "Timed out waiting for Celery worker to complete job"
        assert final_job_data["status"] == "COMPLETED", f"Expected COMPLETED, got {final_job_data['status']}"
        assert final_job_data["completed_count"] == 3
        assert final_job_data["failed_count"] == 0
        assert final_job_data["progress_percentage"] == 100.0
        assert final_job_data["pending_count"] == 0
        print(f"   [SUCCESS] Asynchronous processing finished in {time.time() - start_time:.2f}s")
        
        # Step 3: Retrieve certificates for the job
        print(f"\n3. Retrieving certificates via GET /api/v1/jobs/{job_id}/certificates...")
        res = await client.get(f"/api/v1/jobs/{job_id}/certificates")
        assert res.status_code == 200
        certs_data = res.json()
        assert certs_data["total"] == 3
        certificates = certs_data["certificates"]
        print(f"   [SUCCESS] Found {len(certificates)} certificates")
        for cert in certificates:
            print(f"   - Recipient: {cert['recipient_name']} | Status: {cert['status']} | Download URL: {cert['download_url']}")
            assert cert["status"] == "SUCCESS"
            assert cert["download_url"] is not None
            
        # Step 4: Download and verify PDFs
        print("\n4. Downloading and verifying certificates via GET /api/v1/certificates/{id}/download...")
        for cert in certificates:
            cert_id = cert["certificate_id"]
            download_url = cert["download_url"]
            print(f"   Downloading certificate {cert_id} ({cert['recipient_name']})...")
            dl_res = await client.get(download_url)
            assert dl_res.status_code == 200, f"Download failed: {dl_res.status_code}"
            assert dl_res.headers["content-type"] == "application/pdf"
            assert "attachment" in dl_res.headers.get("content-disposition", "")
            content = dl_res.content
            assert len(content) > 1000, "PDF size unexpectedly small"
            assert content.startswith(b"%PDF"), "Response is not a valid PDF file"
            print(f"   [SUCCESS] Downloaded {len(content)} bytes PDF: {dl_res.headers.get('content-disposition')}")
            
    print("\n" + "=" * 60)
    print("LIVE END-TO-END WORKFLOW VERIFICATION COMPLETE: ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
