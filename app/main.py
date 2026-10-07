"""
Main FastAPI application entry point.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title="Bulk Certificate Generator API",
    version="1.0.0",
    description="Backend API for generating personalized certificates in bulk",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize resources on application startup."""
    # Ensure certificate storage directory exists
    cert_dir = Path(settings.certificate_storage_path)
    cert_dir.mkdir(parents=True, exist_ok=True)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint for health check."""
    return {
        "message": "Bulk Certificate Generator API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include routers (will be added in future features)
# from app.api.routes import jobs, certificates
# app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
# app.include_router(certificates.router, prefix="/api/v1/certificates", tags=["Certificates"])
