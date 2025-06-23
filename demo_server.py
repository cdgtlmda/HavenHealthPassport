"""Standalone FastAPI server for Live Demo AWS Services.

This server provides only the AWS service endpoints needed for the Live Demo
without requiring database or other complex dependencies.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.live_demo_endpoints import router as live_demo_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Haven Health Passport - Live Demo API",
    version="1.0.0",
    description="AWS GenAI Services Live Demo for Haven Health Passport",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:8082",
        "http://localhost:8083",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Live Demo endpoints
app.include_router(live_demo_router, tags=["live-demo", "aws-services"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Haven Health Passport - Live Demo API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "transcribe-medical": "/api/transcribe-medical",
            "translate": "/api/translate",
            "comprehend-medical": "/api/comprehend-medical",
            "textract": "/api/textract",
            "bedrock-cultural": "/api/bedrock-cultural",
            "aws-status": "/api/aws-status",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "live-demo-api"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
