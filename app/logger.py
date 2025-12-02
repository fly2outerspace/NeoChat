import sys

from loguru import logger as _logger

from app.config import PROJECT_ROOT
from app.utils import get_real_time


_print_level = "INFO"


def define_log_level(
    print_level="INFO",
    logfile_level="DEBUG",
    name: str = None,
    enable_console: bool = True,
    enable_file: bool = True,
):
    """Adjust the log level to above level
    
    Args:
        print_level: Log level for console output
        logfile_level: Log level for file output
        name: Prefix name for log file
        enable_console: Whether to output logs to console
        enable_file: Whether to output logs to file
    """
    global _print_level
    _print_level = print_level

    formatted_date = get_real_time(format="logfile")  # Use real time for log file names
    log_name = (
        f"{name}_{formatted_date}" if name else formatted_date
    )  # name a log with prefix name

    _logger.remove()
    
    if enable_console:
        _logger.add(sys.stderr, level=print_level)
    
    if enable_file:
        _logger.add(PROJECT_ROOT / f"logs/{log_name}.log", level=logfile_level)
    
    return _logger


logger = define_log_level(enable_console=True, enable_file=False)

