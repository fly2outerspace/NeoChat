"""Streaming utilities for simulating progressive output effects

This module provides pseudo-streaming functionality that can be easily
replaced with real streaming when backend supports it.
"""
import asyncio
import random
from typing import AsyncIterator
from app.utils.enums import MessageCategory


class StreamingConfig:
    """Configuration for pseudo-streaming behavior
    
    This allows easy switching between pseudo and real streaming
    by changing the implementation without affecting callers.
    """
    # Character delay for typewriter effect (seconds per character)
    TYPEWRITER_CHAR_DELAY = 0.03
    
    # Base delay for line-by-line streaming (seconds per line)
    LINE_BASE_DELAY = 0.5
    # Additional delay per character in a line (seconds)
    LINE_CHAR_DELAY = 0.1
    # Minimum delay for a line (seconds)
    LINE_MIN_DELAY = 0.5
    # Maximum delay for a line (seconds)
    LINE_MAX_DELAY = 6.0
    # Random delay range for line-by-line streaming (seconds)
    # Adds random variation to make output feel more natural
    LINE_RANDOM_MIN = 0.1  # Minimum random delay to add
    LINE_RANDOM_MAX = 2  # Maximum random delay to add
    
    # Enable/disable pseudo-streaming (can be set to False for real streaming)
    ENABLE_PSEUDO_STREAMING = True


async def stream_typewriter_effect(
    text: str,
    char_delay: float = None
) -> AsyncIterator[str]:
    """Stream text with typewriter effect (character by character)
    
    Args:
        text: Text to stream
        char_delay: Delay between characters in seconds (uses config default if None)
    
    Yields:
        str: Single character chunks
    """
    if not StreamingConfig.ENABLE_PSEUDO_STREAMING:
        # If pseudo-streaming is disabled, yield entire text at once
        # This allows easy switching to real streaming
        if text:
            yield text
        return
    
    delay = char_delay or StreamingConfig.TYPEWRITER_CHAR_DELAY
    
    for char in text:
        yield char
        if delay > 0:
            await asyncio.sleep(delay)


async def stream_line_by_line(
    text: str,
    base_delay: float = None,
    char_delay: float = None,
    min_delay: float = None,
    max_delay: float = None,
    random_min: float = None,
    random_max: float = None
) -> AsyncIterator[str]:
    """Stream text line by line with dynamic timing based on line length
    
    Args:
        text: Text to stream (will be split by newlines)
        base_delay: Base delay per line in seconds (uses config default if None)
        char_delay: Additional delay per character in seconds (uses config default if None)
        min_delay: Minimum delay per line in seconds (uses config default if None)
        max_delay: Maximum delay per line in seconds (uses config default if None)
        random_min: Minimum random delay to add in seconds (uses config default if None)
        random_max: Maximum random delay to add in seconds (uses config default if None)
    
    Yields:
        str: Line chunks (including newline character)
    """
    if not StreamingConfig.ENABLE_PSEUDO_STREAMING:
        # If pseudo-streaming is disabled, yield entire text at once
        if text:
            yield text
        return
    
    base = base_delay or StreamingConfig.LINE_BASE_DELAY
    char = char_delay or StreamingConfig.LINE_CHAR_DELAY
    min_d = min_delay or StreamingConfig.LINE_MIN_DELAY
    max_d = max_delay or StreamingConfig.LINE_MAX_DELAY
    rand_min = random_min if random_min is not None else StreamingConfig.LINE_RANDOM_MIN
    rand_max = random_max if random_max is not None else StreamingConfig.LINE_RANDOM_MAX
    
    # Normalize newline variations and handle escaped newlines
    normalized_text = text or ""
    normalized_text = normalized_text.replace('\r\n', '\n').replace('\r', '\n')
    normalized_text = normalized_text.replace('\\n', '\n')
    ends_with_newline = normalized_text.endswith('\n')
    lines = normalized_text.split('\n')
    
    for i, line in enumerate(lines):
        # Calculate delay based on line length
        line_length = len(line)
        delay = base + (line_length * char)
        # Add random variation for more natural feel
        random_delay = random.uniform(rand_min, rand_max)
        delay = delay + random_delay
        delay = max(min_d, min(delay, max_d))  # Clamp between min and max
        
        # Yield the line with newline (except for last line if text doesn't end with newline)
        if i < len(lines) - 1:
            yield line + '\n'
            # Wait before next line
            if delay > 0:
                await asyncio.sleep(delay)
        else:
            # Last line: only add newline if original text ended with one
            if ends_with_newline:
                yield line + '\n'
            else:
                yield line
            # No delay after the last line


async def stream_by_category(
    text: str,
    category: MessageCategory
) -> AsyncIterator[str]:
    """Stream text based on message category
    
    This is the main entry point for streaming. It automatically selects
    the appropriate streaming mode based on category:
    - SPEAK_IN_PERSON: Typewriter effect (character by character)
    - TELEGRAM: Line by line with dynamic timing
    - Others: No streaming (yield entire text)
    
    Args:
        text: Text to stream
        category: Message category to determine streaming mode
    
    Yields:
        str: Text chunks based on category-specific streaming mode
    """
    if category == MessageCategory.SPEAK_IN_PERSON:
        async for chunk in stream_typewriter_effect(text):
            yield chunk
    elif category == MessageCategory.TELEGRAM:
        async for chunk in stream_line_by_line(text):
            yield chunk
    else:
        # For other categories, yield entire text at once
        if text:
            yield text

