"""Shared log formatting and task-local request/device correlation."""

import json
import logging
import logging.handlers
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from datetime import UTC, datetime
from pathlib import Path

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
device_context: ContextVar[dict[str, str] | None] = ContextVar(
    "device_context", default=None
)


@contextmanager
def log_context(**fields: str):
    token = device_context.set({**(device_context.get() or {}), **fields})
    try:
        yield
    finally:
        device_context.reset(token)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Explicit fields (e.g. per-host scan summaries) take precedence.
        for key, value in {
            "request_id": request_id.get(),
            "device_id": None,
            "host": None,
            "operation": None,
            **(device_context.get() or {}),
        }.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **{
                key: getattr(record, key, None)
                for key in ("request_id", "device_id", "host", "operation")
            },
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(log_level="INFO", log_format="text", *, logs_dir=Path("logs")):
    """Configure app and uvicorn logs once per startup; safe to call again."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    formatter = (
        JsonFormatter()
        if log_format == "json"
        else logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "request_id=%(request_id)s device_id=%(device_id)s host=%(host)s "
            "operation=%(operation)s %(message)s"
        )
    )
    root = logging.getLogger()
    root.setLevel(log_level)
    # Only replace our own handlers; preserve test capture and embedding hosts.
    for handler in root.handlers[:]:
        if getattr(handler, "_kasabuena", False):
            root.removeHandler(handler)
            handler.close()
    handlers = [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            logs_dir / "kasabuena.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
    ]
    for handler in handlers:
        handler._kasabuena = True
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        handler.addFilter(ContextFilter())
        root.addHandler(handler)
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(log_level)
    return root


def get_logger(name):
    return logging.getLogger(name)


def background_context():
    """Long-lived jobs must not inherit the request that happened to start them."""
    context = copy_context()
    context.run(request_id.set, None)
    context.run(device_context.set, None)
    return context
