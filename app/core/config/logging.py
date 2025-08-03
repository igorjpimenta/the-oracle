"""
Logging configuration.
"""

import logging
import sys
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Custom formatter with different colors for each log level"""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    BOLD = '\033[1m'
    RESET = '\033[0m'

    def format(self, record):
        # Get the color for this log level
        color = self.COLORS.get(record.levelname, '')

        # Format the message with color
        formatted = super().format(record)

        # Add color to the level name
        if color:
            formatted = formatted.replace(
                f'[{record.asctime}] {record.levelname}',
                f"{color}[{record.asctime}] "
                f"{self.BOLD}{record.levelname}{self.RESET}"
            )

        return formatted


def setup_logging(clear_existing: bool = False):
    """Setup application logging with UTF-8 support

    Args:
        clear_existing: If True, clear existing handlers first.
        Useful when reconfiguring after some logging mid-setup.
    """

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Clear existing handlers if requested
    if clear_existing:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    # Create formatters
    colored_formatter = ColoredFormatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(colored_formatter)

    # File handler with explicit UTF-8 encoding
    file_handler = logging.FileHandler("logs/app.log", encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    ))

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            file_handler,
            console_handler
        ],
        force=clear_existing
    )

    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("instructor").setLevel(logging.INFO)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
