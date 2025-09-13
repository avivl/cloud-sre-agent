# gemini_sre_agent/logger.py

from datetime import datetime
import json
import logging
import os


class JsonFormatter(logging.Formatter):
    """
    A custom logging formatter that outputs log records as JSON strings.
    Includes standard log record attributes and any extra attributes passed.
    """

    def format(self, record: str) -> None:
        """
        Format.

        Args:
            record: Description of record.

        """
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
            "process": record.process,
            "thread": record.thread,
            "processName": record.processName,
            "threadName": record.threadName,
        }

        # Add extra attributes from the log record
        for key, value in record.__dict__.items():
            if key not in log_record and not key.startswith("_"):
                log_record[key] = value

        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            log_record["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_record)


def setup_logging(
    log_level: str = "INFO", json_format: bool = False, log_file: str | None = None
):
    """
    Sets up the logging configuration for the application.

    Args:
        log_level (str): The minimum logging level to capture (e.g., "INFO", "DEBUG").
        json_format (bool): If True, logs will be formatted as JSON. Otherwise, human-readable.
        log_file (Optional[str]): Path to a file where logs should be written. If None, logs
                                   are only sent to the console.

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger("gemini_sre_agent")
    logger.setLevel(log_level.upper())

    # Clear existing handlers to prevent duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(pathname)s:%(lineno)d)"
        )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
