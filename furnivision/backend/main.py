"""FurniVision AI -- FastAPI application entry point."""

import logging
import sys

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.middleware import setup_middleware
from api.routes.projects import router as projects_router
from api.routes.upload import router as upload_router
from api.routes.pipeline import router as pipeline_router
from api.routes.confirm import router as confirm_router
from api.routes.outputs import router as outputs_router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title="FurniVision AI API",
        description="AI-powered interior design pipeline -- floor plan analysis, "
        "furniture placement, image generation, and video assembly.",
        version="0.1.0",
    )

    # Middleware
    setup_middleware(application)

    # Routers
    application.include_router(projects_router)
    application.include_router(upload_router)
    application.include_router(pipeline_router)
    application.include_router(confirm_router)
    application.include_router(outputs_router)

    # Startup / shutdown events
    @application.on_event("startup")
    async def on_startup():
        logger.info("FurniVision AI API starting up")

    @application.on_event("shutdown")
    async def on_shutdown():
        logger.info("FurniVision AI API shutting down")

    # Health check
    @application.get("/health", tags=["health"])
    async def health_check():
        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "service": "furnivision-api"},
        )

    return application


app = create_app()


# ---------------------------------------------------------------------------
# Uvicorn entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
