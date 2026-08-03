import logging
from pathlib import Path


def get_logger(root: Path, name: str = "jarvis") -> logging.Logger:
    log_dir = root / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log_dir = Path("/tmp") / name
        log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        try:
            handler = logging.FileHandler(log_dir / "jarvis.log", encoding="utf-8")
        except PermissionError:
            handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger
