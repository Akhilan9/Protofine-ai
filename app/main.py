"""FastAPI application entrypoint for EvidenceGuard AI."""
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.routes import router as api_router
from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
)
logger = logging.getLogger("evidenceguard")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("EVIDENCEGUARD AI SERVICE INITIALIZING")
    logger.info(f"Effective Provider: {settings.effective_provider}")
    logger.info(f"Model Name:         {settings.MODEL_NAME}")
    logger.info(f"Environment:        {settings.ENVIRONMENT}")
    logger.info("=" * 60)
    yield

app = FastAPI(
    title="EvidenceGuard AI",
    description=(
        "Self-Checking Factual Answer Engine for the Protofine.ai Applied AI Engineering Intern Build Task. "
        "Applies an adversarial two-pass self-check loop to catch and correct unsupported factual claims."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Serve the developer UI at the root route
_STATIC_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serve developer demo UI at root endpoint."""
    if _STATIC_INDEX.exists():
        return FileResponse(_STATIC_INDEX)
    return {"message": "EvidenceGuard AI API is running. Visit /docs for OpenAPI documentation."}
