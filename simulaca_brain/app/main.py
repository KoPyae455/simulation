"""
Application entry point.

Exposes create_app(), an application factory, rather than a bare
module-level `app = FastAPI()`. That keeps the app instantiable
multiple times (needed for isolated test clients) and keeps wiring
explicit instead of relying on import-time side effects.
"""

import logging

from fastapi import FastAPI

from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build and configure a Simulaca Brain FastAPI application instance."""
    settings = get_settings()

    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()