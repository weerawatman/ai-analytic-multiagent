import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.app.core.config import get_settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger("ai_analytics")
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False

    log_dir = Path(__file__).resolve().parents[3] / settings.data_local_dir / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "backend.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Read-only or locked filesystem — console logging still works.
        logger.warning("Cannot create log file at %s; file logging disabled", log_dir)

    return logger


logger = setup_logging()
