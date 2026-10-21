"""
Main FastAPI application entry point.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.services.file_manager import FileManager, FileManagerError


logger = logging.getLogger(__name__)

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
    # Validate certificate storage directory
    try:
        file_manager = FileManager()
        file_manager.validate_storage_path()
        logger.info(f"Certificate storage validated at: {settings.certificate_storage_path}")
    except FileManagerError as e:
        logger.error(f"Certificate storage validation failed: {e}")
        raise RuntimeError(f"Failed to initialize certificate storage: {e}") from e


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


# Import and include routers
from app.api.routes import jobs, certificates

app.include_router(jobs.router, prefix="/api/v1", tags=["Jobs"])
app.include_router(certificates.router, prefix="/api/v1", tags=["Certificates"])
