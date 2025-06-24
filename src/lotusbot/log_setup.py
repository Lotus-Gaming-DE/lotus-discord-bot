import logging
from logging.handlers import RotatingFileHandler
import asyncio
from pathlib import Path
import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for console and rotating file output.

    Parameters
    ----------
    log_level: str
        The desired log level (e.g. "INFO" or "DEBUG").
    """
    log_level = log_level.upper()
    level = getattr(logging, log_level, logging.INFO)

    Path("logs").mkdir(exist_ok=True)
    handlers = [logging.StreamHandler()]
    file_handler = RotatingFileHandler(
        "logs/bot.log", maxBytes=1_000_000, backupCount=3
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    handlers.append(file_handler)

    logging.basicConfig(level=level, handlers=handlers, force=True)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    logging.getLogger("discord").setLevel(logging.WARNING)


def get_logger(name: str, **context) -> structlog.BoundLogger:
    """Return a structured logger with optional context."""
    return structlog.get_logger(name, **context)


def create_logged_task(coro, logger: structlog.BoundLogger) -> asyncio.Task:
    """Create an ``asyncio.Task`` and log uncaught exceptions.

    The returned task ignores :class:`asyncio.CancelledError` when finished and
    logs all other exceptions via ``logger.error``.
    """
    task = asyncio.create_task(coro)

    def _log_exception(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.error("Task raised an exception", exc_info=exc)

    task.add_done_callback(_log_exception)
    return task
