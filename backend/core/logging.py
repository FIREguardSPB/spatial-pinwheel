"""
P3-02: Centralized logging configuration.

Dev  → human-readable coloured output with timestamps
Prod → JSON-lines for Loki / ELK / CloudWatch

Usage:
    from core.logging import configure_logging, get_logger
    configure_logging()           # call once at startup
    logger = get_logger(__name__)
    logger.info("signal_created", ticker="TQBR:SBER", score=75)
"""
import logging
import logging.handlers
import sys
from pathlib import Path

try:
    import structlog
    _HAS_STRUCTLOG = True
except ImportError:
    _HAS_STRUCTLOG = False


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_dir: str | None = None,
) -> None:
    """
    Configure logging for the entire application.

    Args:
        level:       Log level string (DEBUG/INFO/WARNING/ERROR).
        json_format: True = JSON output (production). False = coloured human format (dev).
        log_dir:     Optional directory for rotating log files (production).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        rotating = logging.handlers.TimedRotatingFileHandler(
            log_path / "app.log",
            when="midnight",
            backupCount=7,
            encoding="utf-8",
        )
        handlers.append(rotating)

    if _HAS_STRUCTLOG:
        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
        ]

        if json_format:
            renderer = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer(colors=True)

        structlog.configure(
            processors=shared_processors + [
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
            foreign_pre_chain=shared_processors,
        )
        for h in handlers:
            h.setFormatter(formatter)
    else:
        # Fallback to standard logging if structlog not installed
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        for h in handlers:
            h.setFormatter(logging.Formatter(fmt))

    logging.basicConfig(level=numeric_level, handlers=handlers, force=True)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "grpc"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str):
    """
    Return a logger. Uses structlog BoundLogger if available,
    otherwise falls back to stdlib Logger.
    """
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)
