import logging
import os
import sys
import yaml


def load_config() -> dict:
    """Load config.yaml from the project root."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def setup_logger(name: str = "baba") -> logging.Logger:
    """Set up and return a configured logger."""
    config = load_config()
    log_cfg = config.get("baba", {}).get("logging", {})

    level_str = log_cfg.get("level", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    log_file = os.path.expanduser(log_cfg.get("file", "~/Library/Logs/baba.log"))
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    # Prevent child loggers from duplicating messages via the parent
    logger.propagate = False

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
