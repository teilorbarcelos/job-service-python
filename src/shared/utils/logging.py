"""Structured JSON logger for the job runner.

Configures the root logger with a JSON formatter that emits
timestamped, level-tagged records to stdout. No external dependencies
(uses stdlib `logging` + `json`).

The boilerplate never calls `logging.basicConfig()` or installs
handlers directly elsewhere — `setup_logging()` is called once from
`app.py` at startup. Modules just call `get_logger(__name__)`.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_RESERVED_LOGRECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime",
}


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOGRECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with a single JSON StreamHandler to stdout.

    Idempotent: calling twice replaces the previous configuration.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Inherits the root configuration from setup_logging()."""
    return logging.getLogger(name)
