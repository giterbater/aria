"""
ARIA logging configuration.

Provides a consistent logging setup across all modules.
Usage:
    from aria_logging import logger
    logger.info("Something happened")
    logger.debug("Diagnostic info")
    logger.error("An error occurred")
"""

import logging
import sys


def setup_logging(level: str = "INFO", log_file: str = None):
    """
    Configure logging for ARIA.
    
    Args:
        level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to. If None, logs to stderr.
    """
    # Create logger
    logger = logging.getLogger("aria")
    logger.setLevel(getattr(logging, level.upper()))

    # Create formatter
    formatter = logging.Formatter(
        "[%(levelname)s] [%(name)s] %(message)s"
    )

    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add stderr handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Global logger instance
logger = setup_logging()


def get_logger(name: str = None):
    """Get a logger for a specific module."""
    if name:
        return logging.getLogger(f"aria.{name}")
    return logger
