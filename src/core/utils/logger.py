import datetime
import logging
import sys

from core.utils.paths import DATA_DIR


class CustomFormatter(logging.Formatter):
    """A log formatter that adjusts output formatting based on the log level.

    INFO-level logs use a concise format, while DEBUG and higher levels use a detailed format including timestamp, logger name, and line number.
    """

    # Define a detailed format for DEBUG and higher-level warnings/errors
    detailed_format = (
        "| %(levelname)-8s | %(asctime)s | %(name)s:%(lineno)d | %(message)s"
    )

    # Define a concise format for INFO messages
    concise_format = "| %(levelname)-8s | %(asctime)s | %(message)s"

    def __init__(self):
        super().__init__(fmt="%(levelno)d: %(msg)s", datefmt="%H:%M:%S")
        self.formatters = {
            logging.INFO: logging.Formatter(self.concise_format, datefmt=self.datefmt),
            logging.DEBUG: logging.Formatter(
                self.detailed_format, datefmt=self.datefmt
            ),
            logging.WARNING: logging.Formatter(
                self.detailed_format, datefmt=self.datefmt
            ),
            logging.ERROR: logging.Formatter(
                self.detailed_format, datefmt=self.datefmt
            ),
            logging.CRITICAL: logging.Formatter(
                self.detailed_format, datefmt=self.datefmt
            ),
        }

    def format(self, record: logging.LogRecord) -> str:
        """Selects the appropriate log format dynamically based on log level.

        Args:
            record (LogRecord): The log record being processed.

        Returns:
            str: The formatted log string.
        """
        formatter = self.formatters.get(record.levelno)
        return formatter.format(record)


def setup_logging(
    level: int = logging.INFO,
    stream: bool = True,
    save: bool = False,
    label: str = None,
) -> None:
    """Configures the root logger with a custom formatter and optional file output.

    Console output is optional via the `stream` flag.

    Args:
        level (int): Minimum log level to process (default: INFO).
        stream (bool): If True, logs are written to stdout.
        save: (str): If provided, save logs to file.
        label: (str): If provided, logs are saved to file using the label as prefix.

    """
    root_logger = logging.getLogger()

    # Clear any existing handlers to prevent duplicate logs
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Custom formatter to be set for the handler
    formatter = CustomFormatter()

    # Stream handler to console (stdout)
    if stream:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    # File handler only if save=True
    if save:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        name = f"{label}_{timestamp}.log" if label else f"logs_{timestamp}.log"
        savepath = DATA_DIR / "logs" / name
        savepath.parent.mkdir(parents=True, exist_ok=True)

        fh = logging.FileHandler(savepath, mode="a", encoding="utf-8")
        fh.setFormatter(formatter)
        root_logger.addHandler(fh)

    root_logger.setLevel(level)

    # Minimum level of logs to process
    root_logger.setLevel(level)

    # Quieten noisy libraries
    for lib in ("urllib3", "httpx", "httpcore"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    # Use a special logger name to avoid the verbose format for this one message
    logging.getLogger("setup_logger").info(
        f"Logging configured with level: {logging.getLevelName(level)}"
    )


def log_tools(
    tool_name: str, level: int = logging.DEBUG, save: bool = True, label: str = None
) -> logging.Logger:
    """Tool-specific logger that writes detailed debug logs to a file.

    Args:
        tool_name (str): Unique name for the tool logger (e.g., 'extract_tool').
        level (int): Minimum log level for this logger (default: DEBUG).
        save: (str): If provided, save logs to file.
        label: (str): If provided, logs are saved to file using the label as prefix.

    Returns:
        Configured Logger instance for the tool.
    """
    logger = logging.getLogger(f"tools.{tool_name}")
    logger.setLevel(level)
    logger.propagate = False  # no console output

    # Only attach file handler if requested
    if save and not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        prefix = f"{label}_" if label else ""
        filename = f"{prefix}{tool_name}_{timestamp}.log"
        savepath = DATA_DIR / "logs" / "tools" / filename
        savepath.parent.mkdir(parents=True, exist_ok=True)

        fh = logging.FileHandler(savepath, mode="a", encoding="utf-8")
        fh.setFormatter(CustomFormatter())
        logger.addHandler(fh)

    return logger
