"""Centralized logging configuration for motus.leap."""

import logging
import sys
from pathlib import Path
from typing import Optional

def get_log_file_path() -> Path:
    """Resolve the active log file path consistently across dev and production environments."""
    import os
    env_dir = os.getenv("TUBE_MANAGER_DATA_DIR")
    if env_dir:
        return Path(env_dir) / "tube_manager.log"
    if Path("data").exists():
        return Path("data") / "tube_manager.log"
    if Path("/app/data").exists():
        return Path("/app/data") / "tube_manager.log"
    d = Path("data")
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d / "tube_manager.log"

def setup_logging(log_level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """Set up logging configuration for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to a log file
    """
    if log_file is None:
        log_file = get_log_file_path()

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except Exception as e:
            sys.stderr.write(f"[WARN] Failed to setup FileHandler for {log_file}: {e}\n")

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=True
    )

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Configure uvicorn loggers to use our format
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logging.getLogger(logger_name).setLevel(getattr(logging, log_level.upper(), logging.INFO))

    return logging.getLogger("tube_manager")