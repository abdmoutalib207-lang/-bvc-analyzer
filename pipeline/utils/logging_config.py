import logging
import sys
from pathlib import Path


def setup_logging(log_file: str = "collector.log", level: int = logging.INFO):
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent.parent / log_file, encoding="utf-8"),
    ]

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)

    # Silence noisy libs
    for lib in ("urllib3", "requests", "yfinance", "peewee"):
        logging.getLogger(lib).setLevel(logging.WARNING)
