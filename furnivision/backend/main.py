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
from api.routes.v5 import router as v5_router
from api.routes.edit import router as edit_router

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
    application.include_router(v5_router)
    application.include_router(edit_router)

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

    # Local storage file serving (dev mode only)
    @application.get("/api/v1/local-storage/{file_path:path}", tags=["dev"])
    async def serve_local_file(file_path: str):
        from fastapi.responses import FileResponse
        from config import TEMP_DIR
        # Try under storage/ first, then directly under TEMP_DIR
        local_path = TEMP_DIR / "storage" / file_path
        if not local_path.exists():
            local_path = TEMP_DIR / file_path
        if not local_path.exists():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="File not found in local storage")
        return FileResponse(str(local_path))

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
