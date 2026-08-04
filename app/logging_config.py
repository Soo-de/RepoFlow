import logging
import json
import sys
from datetime import datetime, timezone


class ReadableFormatter(logging.Formatter):
    """Formats log records into clean, human-readable terminal lines.

    Preserves newlines in multiline blocks (e.g. repo analysis summaries)
    and formats timestamps cleanly instead of escaping newlines as JSON string literals.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        msg = record.getMessage()
        prefix = f"[{timestamp}] [{record.levelname}] [{record.name}]"

        if "\n" in msg:
            output = f"{prefix}:\n{msg}"
        else:
            output = f"{prefix}: {msg}"

        if record.exc_info and record.exc_info[0]:
            output += "\n" + self.formatException(record.exc_info)
        return output


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ReadableFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
