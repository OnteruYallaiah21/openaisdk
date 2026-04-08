

class Logger:
    """A simple logger that prints the line number in bold yellow, but the message in default color."""
    @staticmethod                   
    def log_info(message: str):
        """Prints the line number in bold yellow, but the message in default color."""
        frame = inspect.currentframe().f_back
        line_no = frame.f_lineno
        # ANSI escape codes
        yellow = "\033[93m"
        bold = "\033[1m"
        reset = "\033[0m"
        # Only the [LINE XX] part is yellow/bold now
        print(f"{bold}{yellow}[LINE {line_no}]{reset} INFO: {message}")