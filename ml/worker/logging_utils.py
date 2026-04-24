import json
import logging
from datetime import datetime, timezone


def build_logger() -> logging.Logger:
    logger = logging.getLogger("bookgen.worker")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


LOGGER = build_logger()


def log_event(level: str, message: str, **fields) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        **fields,
    }
    line = json.dumps(payload, ensure_ascii=False)
    if level == "error":
        LOGGER.error(line)
    else:
        LOGGER.info(line)
