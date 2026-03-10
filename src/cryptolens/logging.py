"""Structured JSON logging configuration using structlog."""

import logging

import orjson
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog to emit JSON lines to stdout.

    Args:
        log_level: Standard Python log level name, e.g. "INFO" or "DEBUG".
    """
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(serializer=orjson.dumps),
        ],
        logger_factory=structlog.BytesLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=log_level.upper())
