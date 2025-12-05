"""Utility functions for common operations"""
import asyncio
import functools
import time
from datetime import datetime
from typing import Any, Callable, Literal, Optional

from app.utils.time_provider import time_provider


def get_current_time(
    format: Literal["readable", "iso", "timestamp", "logfile"] = "readable",
    timezone: Optional[str] = None,
    session_id: Optional[str] = None
) -> str:
    """Get current virtual time in specified format
    
    Args:
        format: Time format
            - 'readable': 'YYYY-MM-DD HH:MM:SS' (default, most common format)
            - 'iso': ISO 8601 format
            - 'timestamp': Unix timestamp as string
            - 'logfile': 'YYYYMMDDHHMMSS' (for log file names)
        timezone: Optional timezone name (e.g., 'Asia/Shanghai', 'UTC')
                  If None, uses system local timezone.
                  Requires pytz library if specified.
        session_id: Optional session ID for session-specific virtual time.
                    If None, uses default/global clock.
    
    Returns:
        Current virtual time as a string in the specified format
    
    Examples:
        >>> get_current_time()
        '2024-01-15 14:30:45'
        >>> get_current_time(format='iso')
        '2024-01-15T14:30:45.123456'
        >>> get_current_time(format='timestamp')
        '1705324245'
        >>> get_current_time(format='logfile')
        '20240115143045'
        >>> get_current_time(session_id='session-123')
        '2024-01-15 14:30:45'  # Virtual time for this session
    """
    try:
        return time_provider.now_str(format=format, session_id=session_id, timezone=timezone)
    except Exception as e:
        raise RuntimeError(f"Error getting current time: {e}")


def get_current_datetime(session_id: Optional[str] = None) -> datetime:
    """Get current virtual time as datetime object
    
    Args:
        session_id: Optional session ID for session-specific virtual time.
                    If None, uses default/global clock.
    
    Returns:
        Current virtual datetime
    """
    return time_provider.now(session_id=session_id)


def get_real_time(
    format: Literal["readable", "iso", "timestamp", "logfile"] = "readable",
    timezone: Optional[str] = None
) -> str:
    """Get real system time (always real, never virtual)
    
    Args:
        format: Time format
        timezone: Optional timezone name
    
    Returns:
        Real system time as a string
    """
    try:
        return time_provider.real_now_str(format=format, timezone=timezone)
    except Exception as e:
        raise RuntimeError(f"Error getting real time: {e}")


def get_real_datetime() -> datetime:
    """Get real system time as datetime object (always real, never virtual)
    
    Returns:
        Real system datetime
    """
    return time_provider.real_now()


def log_execution_time(
    log_level: str = "INFO",
    include_args: bool = False,
    include_result: bool = False,
):
    """
    Decorator to log function execution time.
    
    Supports both synchronous and asynchronous functions.
    
    Args:
        log_level: Log level to use ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        include_args: Whether to include function arguments in log (default: False)
        include_result: Whether to include function result in log (default: False)
    
    Returns:
        Decorator function
    
    Examples:
        >>> @log_execution_time()
        ... def my_function(x, y):
        ...     return x + y
        >>> my_function(1, 2)
        # Logs: "Function 'my_function' executed in 0.001s"
        
        >>> @log_execution_time(log_level='DEBUG', include_args=True)
        ... async def my_async_function(x):
        ...     await asyncio.sleep(0.1)
        ...     return x * 2
        >>> await my_async_function(5)
        # Logs: "Function 'my_async_function' executed in 0.101s (args: (5,))"
    """
    def decorator(func: Callable) -> Callable:
        # Import logger here to avoid circular import
        from app.logger import logger
        
        func_name = f"{func.__module__}.{func.__qualname__}" if hasattr(func, '__qualname__') else func.__name__
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    elapsed = time.perf_counter() - start_time
                    
                    log_msg = f"Function '{func_name}' executed in {elapsed:.4f}s"
                    if include_args:
                        log_msg += f" (args: {args}, kwargs: {kwargs})"
                    if include_result:
                        result_preview = str(result)[:100] if result is not None else "None"
                        log_msg += f" (result: {result_preview})"
                    
                    getattr(logger, log_level.lower())(log_msg)
                    return result
                except Exception as e:
                    elapsed = time.perf_counter() - start_time
                    logger.error(
                        f"Function '{func_name}' failed after {elapsed:.4f}s: {e}"
                    )
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    elapsed = time.perf_counter() - start_time
                    
                    log_msg = f"Function '{func_name}' executed in {elapsed:.4f}s"
                    if include_args:
                        log_msg += f" (args: {args}, kwargs: {kwargs})"
                    if include_result:
                        result_preview = str(result)[:100] if result is not None else "None"
                        log_msg += f" (result: {result_preview})"
                    
                    getattr(logger, log_level.lower())(log_msg)
                    return result
                except Exception as e:
                    elapsed = time.perf_counter() - start_time
                    logger.error(
                        f"Function '{func_name}' failed after {elapsed:.4f}s: {e}"
                    )
                    raise
            return sync_wrapper
    
    return decorator


def remove_empty_lines(text: Optional[str]) -> str:
    """Remove empty / whitespace-only lines from text.
    
    This helper is used to normalize LLM outputs so that
    we don't get visually noisy blank lines in streaming
    or non-streaming responses.
    
    Args:
        text: Original text (can be None)
    
    Returns:
        Text without empty lines. Returns "" for None/empty input.
    """
    return text or ""
    # if not text:
    #     return ""

    # # Normalize different newline forms
    # normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # # Split into lines, drop whitespace-only lines, and join back
    # lines = normalized.split("\n")
    # non_empty_lines = [line for line in lines if line.strip() != ""]

    # return "\n".join(non_empty_lines)


__all__ = [
    'get_current_time', 
    'get_current_datetime', 
    'get_real_time', 
    'get_real_datetime',
    'log_execution_time',
    'remove_empty_lines',
]

