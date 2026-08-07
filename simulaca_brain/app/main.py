"""
Application entry point.

Exposes create_app(), an application factory, rather than a bare
module-level `app = FastAPI()`. That keeps the app instantiable
multiple times (needed for isolated test clients) and keeps wiring
explicit instead of relying on import-time side effects.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.dependencies import get_simulation_service
from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings


@asynccontextmanager
async def application_lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Stop active simulation work cleanly when the application shuts down."""
    try:
        yield
    finally:
        await get_simulation_service().shutdown()


def create_app() -> FastAPI:
    """Build and configure a Simulaca Brain FastAPI application instance."""
    settings = get_settings()

    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=application_lifespan,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    dashboard_path = Path(__file__).resolve().parents[2] / "simulaca_dashboard" / "dist"
    if dashboard_path.exists():
        app.mount("/", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")

    return app


app = create_app()
