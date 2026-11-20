"""JSON logging with a per-request ID, so one request can be traced through the logs."""

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            entry["request_id"] = request_id
        # Structured fields passed as logger.info("...", extra={"fields": {...}})
        entry.update(getattr(record, "fields", {}) or {})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    # Our request middleware logs every request, so uvicorn's access log would duplicate it.
    logging.getLogger("uvicorn.access").disabled = True
