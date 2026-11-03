"""Journalisation JSON sur stdout (exigence : logs JSON)."""

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formateur JSON minimal : ts, level, logger, message (+ extras par clés)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "catalogue",
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Attributs fournis via `extra=`
        for key in ("event", "path", "status_code", "duration_ms", "method", "instance", "detail"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Trop bavards en INFO normal
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
