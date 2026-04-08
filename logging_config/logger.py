import logging
import sys
import os

class ColorLineFormatter(logging.Formatter):
    """Custom formatter: bold yellow for line number, normal color for the message."""
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def format(self, record):
        # Format line number in bold yellow
        record.lineno_color = f"{self.BOLD}{self.YELLOW}[LINE {record.lineno}]{self.RESET}"
        # Standard log formatting
        formatted = (
            f"{record.asctime} | {record.levelname} | {getattr(record, 'app_name', 'APP')} | "
            f"{record.name} | {record.filename} | {record.funcName} | {record.lineno_color} | {record.getMessage()}"
        )
        return formatted

def setup_logger(app_name: str = None):
    if app_name is None:
        app_name = os.getenv("APP_NAME", "MY_APP")

    logger = logging.getLogger()  # root logger
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # already configured

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # File handler
    file_handler = logging.FileHandler(f"{app_name}.log")
    file_handler.setLevel(logging.DEBUG)

    # Formatter
    formatter = ColorLineFormatter()
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add app_name to record dynamically
    def add_app_name(record):
        record.app_name = app_name
        return True
    console_handler.addFilter(add_app_name)
    file_handler.addFilter(add_app_name)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger