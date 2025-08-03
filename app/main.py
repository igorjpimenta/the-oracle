"""
Main entry point for running the application with uvicorn.
"""

import uvicorn

from .core.config.settings import get_settings


def main():
    """Main entry point for the application."""
    settings = get_settings()

    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=settings.PORT,
        log_level="debug" if settings.DEBUG else "warning",
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
