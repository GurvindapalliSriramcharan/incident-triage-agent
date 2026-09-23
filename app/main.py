import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.approvals import router as approvals_router
from app.api.incidents import router as incidents_router
from app.config import settings
from app.db.connection import is_database_connected, run_schema_migration
from app.schemas.incident import HealthCheckResponse
from scripts.seed_rag import seed_runbooks

# Configure logging format: [incident_id] [node] message or standard service logs
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("incident_triage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("Initializing Autonomous Incident Triage Agent service...")

    # Attempt automatic schema migration if DATABASE_URL is provided
    if settings.DATABASE_URL:
        if is_database_connected():
            logger.info("PostgreSQL is connected. Running schema migrations...")
            run_schema_migration()
        else:
            logger.warning("DATABASE_URL provided but database is not reachable at startup.")

    # Seed runbooks into knowledge base
    try:
        logger.info("Seeding internal incident runbooks...")
        seed_runbooks(force=False)
    except Exception as e:
        logger.warning(f"Runbook seeding encountered error: {e}")

    logger.info("Incident Triage Agent service ready to receive alerts.")
    yield
    logger.info("Shutting down Incident Triage Agent service.")


app = FastAPI(
    title="Autonomous Incident Triage Agent API",
    description=(
        "Production-ready Autonomous Incident Triage System with LangGraph orchestration, "
        "pgvector semantic search, Google Gemini structured reasoning, and Human-in-the-Loop approval gating."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global unhandled exception handler to avoid exposing raw stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact the system administrator."}
    )


# Health check endpoint
@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["system"],
    summary="Service and dependencies health probe"
)
def health_check():
    """Health endpoint for Docker, Kubernetes, and Render health checks."""
    db_ok = is_database_connected()
    gemini_ok = bool(settings.GEMINI_API_KEY)

    return HealthCheckResponse(
        status="ok",
        environment=settings.APP_ENV,
        database_connected=db_ok,
        gemini_configured=gemini_ok,
        version="1.0.0"
    )


# Register API routers
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
