"""Structured (JSON) logging configuration.

Spec's observability section is specific about what a log line should be
able to answer: request_id, processing_stage/operation, status, duration,
error details — and specific about what it must never contain: passwords,
tokens, API keys, unnecessary sensitive user data. Plain string logs
("celery_task_started task=... request_id=...", used through Phase 3-6)
are readable by a human but not reliably machine-parseable — grepping for
one request's full story across dozens of log lines works until you need
to do it programmatically (a log aggregator, an alert rule). JSON logs are
exactly as readable with `jq`/a log viewer, and are actually queryable.
"""
import json
import logging
import sys
from datetime import datetime, timezone

# Attributes every standard LogRecord already has — anything else passed via
# logger.info(..., extra={...}) is application-specific and gets included.
_RESERVED_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet the very chatty libraries down to warnings-only; they'd otherwise
    # dominate the log stream with connection-pool-level noise.
    for noisy_logger in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
