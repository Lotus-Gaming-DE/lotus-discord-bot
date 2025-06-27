import logging
import asyncio
from pathlib import Path
import datetime

import structlog


class HourlyFileHandler(logging.Handler):
    """Write logs to ``logs/runtime-<YYYY-MM-DD-HH>.json`` with hourly rotation."""

    def __init__(self, logs_dir: Path) -> None:
        super().__init__()
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(exist_ok=True)
        self.current_hour = self._hour()
        self.file = open(self._path(), "a", encoding="utf-8")

    def _hour(self) -> str:
        return datetime.datetime.utcnow().strftime("%Y-%m-%d-%H")

    def _path(self) -> Path:
        return self.logs_dir / f"runtime-{self.current_hour}.json"

    def emit(
        self, record: logging.LogRecord
    ) -> None:  # pragma: no cover - thin wrapper
        hour = self._hour()
        if hour != self.current_hour:
            self.file.close()
            self.current_hour = hour
            self.file = open(self._path(), "a", encoding="utf-8")
        msg = self.format(record)
        self.file.write(msg + "\n")
        self.file.flush()

    def close(self) -> None:  # pragma: no cover - cleanup
        if not self.file.closed:
            self.file.close()
        super().close()


_configured = False


def setup_logging(log_level: str = "INFO"):
    """Configure logging for console and file output.

    Parameters
    ----------
    log_level: str
        The desired log level (e.g. "INFO" or "DEBUG").
    """
    global _configured
    if _configured:
        return

    log_level = log_level.upper()
    level = getattr(logging, log_level, logging.INFO)

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    handlers = [
        logging.StreamHandler(),
        HourlyFileHandler(logs_dir),
    ]

    logging.basicConfig(
        level=level, handlers=handlers, format="%(message)s", force=True
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    logging.getLogger("discord").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str, **context) -> structlog.BoundLogger:
    """Return a structlog ``BoundLogger`` with optional context."""
    if not _configured:
        setup_logging()
    return structlog.get_logger(name).bind(**context)


def create_logged_task(coro, logger) -> asyncio.Task:
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
