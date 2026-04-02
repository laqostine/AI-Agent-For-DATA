"""FurniVision AI -- FastAPI middleware: CORS, request logging, error handling."""

import logging
import time
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from config import CORS_ORIGINS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CORS setup
# ---------------------------------------------------------------------------

def add_cors_middleware(app: FastAPI) -> None:
    """Attach CORS middleware to the FastAPI application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every incoming request with timing, method, path, and status."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start = time.perf_counter()
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""

        logger.info(
            "[%s] --> %s %s%s",
            request_id,
            method,
            path,
            f"?{query}" if query else "",
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                "[%s] <-- %s %s 500 (%.1fms) UNHANDLED EXCEPTION",
                request_id,
                method,
                path,
                elapsed,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "[%s] <-- %s %s %d (%.1fms)",
            request_id,
            method,
            path,
            response.status_code,
            elapsed,
        )

        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Global error handling middleware
# ---------------------------------------------------------------------------

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and returns a structured JSON error."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except ValueError as exc:
            logger.warning("ValueError: %s", exc)
            return JSONResponse(
                status_code=400,
                content={"detail": str(exc)},
            )
        except Exception as exc:
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
            )


# ---------------------------------------------------------------------------
# Convenience: attach all middleware at once
# ---------------------------------------------------------------------------

def setup_middleware(app: FastAPI) -> None:
    """Register all middleware layers on the FastAPI application.

    Order matters -- middleware added last wraps outermost.
    """
    # Error handling (outermost)
    app.add_middleware(ErrorHandlingMiddleware)

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # CORS (innermost of the custom stack)
    add_cors_middleware(app)
