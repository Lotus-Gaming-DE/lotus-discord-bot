import logging
from logging.handlers import RotatingFileHandler
import asyncio


def setup_logging(log_level: str = "INFO"):
    """Configure logging for console and file output.

    Parameters
    ----------
    log_level: str
        The desired log level (e.g. "INFO" or "DEBUG").
    """
    log_level = log_level.upper()
    level = getattr(logging, log_level, logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s:%(name)s: %(message)s")

    handlers = [logging.StreamHandler()]
    file_handler = RotatingFileHandler(
        "bot.log", maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)

    logging.basicConfig(level=level,
                        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
                        handlers=handlers,
                        force=True)

    logging.getLogger("discord").setLevel(logging.WARNING)


def get_logger(name: str, **context) -> logging.LoggerAdapter:
    """Return a LoggerAdapter with optional contextual information."""
    base = logging.getLogger(name)
    return logging.LoggerAdapter(base, context)


def create_logged_task(coro, logger: logging.Logger):
    """Create an asyncio task and log uncaught exceptions."""
    task = asyncio.create_task(coro)

    def _log_exception(t: asyncio.Task):
        exc = t.exception()
        if exc is not None:
            logger.error("Task raised an exception", exc_info=exc)

    task.add_done_callback(_log_exception)
    return task
