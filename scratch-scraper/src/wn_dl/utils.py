"""
Utility functions for the web novel scraper.

This module provides common utility functions used throughout the application.
"""

import asyncio
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from pytest import MarkDecorator

logger = logging.getLogger(__name__)


def clean_filename(
    filename: str, max_length: int = 255, use_underscores: bool = True
) -> str:
    """
    Clean a filename to be safe for filesystem use with Unix-safe naming.

    Args:
        filename: Original filename
        max_length: Maximum length for the filename
        use_underscores: If True, replace spaces and special chars with underscores

    Returns:
        Cleaned filename safe for filesystem use
    """
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Remove control characters
    filename = "".join(
        char for char in filename if unicodedata.category(char)[0] != "C"
    )

    # Normalize unicode
    filename = unicodedata.normalize("NFKD", filename)

    if use_underscores:
        # Replace spaces and remaining special characters with underscores for Unix-safe naming
        filename = re.sub(r"[^\w\.-]", "_", filename)
        # Replace multiple underscores with single underscore
        filename = re.sub(r"_+", "_", filename)
        # Remove leading/trailing underscores
        filename = filename.strip("_")
    else:
        # Remove extra whitespace and dots (original behavior)
        filename = re.sub(r"\s+", " ", filename).strip()
        filename = re.sub(r"\.+$", "", filename)  # Remove trailing dots

    # Truncate if too long
    if len(filename) > max_length:
        name, ext = Path(filename).stem, Path(filename).suffix
        max_name_length = max_length - len(ext)
        filename = name[:max_name_length] + ext

    # Ensure it's not empty
    if not filename or filename.isspace():
        filename = "untitled"

    return filename


def normalize_url(url: str, base_url: str) -> str:
    """
    Normalize a URL by making it absolute and cleaning it.

    Args:
        url: URL to normalize
        base_url: Base URL for relative URLs

    Returns:
        Normalized absolute URL
    """
    if not url:
        return ""

    # Make absolute
    if not url.startswith(("http://", "https://")):
        url = urljoin(base_url, url)

    # Parse and reconstruct to normalize
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


def extract_text_content(element: Tag, preserve_formatting: bool = True) -> str:
    """
    Extract clean text content from a BeautifulSoup element.

    Args:
        element: BeautifulSoup element
        preserve_formatting: Whether to preserve basic formatting

    Returns:
        Cleaned text content
    """
    if not element:
        return ""

    # Remove script and style elements
    for script in element(["script", "style"]):
        script.decompose()

    if preserve_formatting:
        # Replace block elements with newlines
        for tag in element.find_all(
            ["p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6"]
        ):
            if tag.name == "br":
                tag.replace_with("\n")
            else:
                tag.insert_before("\n")
                tag.insert_after("\n")

    # Get text and clean it
    text = element.get_text()

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)

    return text.strip()


def clean_html_content(soup: BeautifulSoup, config: Dict[str, Any]) -> str:
    """
    Clean HTML content based on configuration.

    Args:
        soup: BeautifulSoup object
        config: Cleaning configuration

    Returns:
        Cleaned text content
    """
    # Remove unwanted elements
    remove_selectors = config.get("remove_selectors", [])
    for selector in remove_selectors:
        try:
            for element in soup.select(selector):
                element.decompose()
        except Exception as e:
            logger.debug(f"Failed to remove elements with selector '{selector}': {e}")

    # Extract text with formatting preservation
    preserve_formatting = config.get("preserve_formatting", True)
    text = extract_text_content(soup, preserve_formatting)

    # Apply text processing
    text_processing = config.get("text_processing", {})

    if text_processing.get("remove_empty_lines", True):
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

    if text_processing.get("normalize_whitespace", True):
        text = re.sub(r" +", " ", text)
        text = re.sub(r"\n +", "\n", text)
        text = re.sub(r" +\n", "\n", text)

    if text_processing.get("convert_html_entities", True):
        import html

        text = html.unescape(text)

    return text


def extract_chapter_number(text: str) -> Optional[int]:
    """
    Extract chapter number from text using various patterns.

    Args:
        text: Text to search for chapter number

    Returns:
        Chapter number or None if not found
    """
    if not text:
        return None

    # Common patterns for chapter numbers
    patterns = [
        r"chapter\s*(\d+)",
        r"ch\s*(\d+)",
        r"c(\d+)",
        r"第(\d+)章",  # Chinese
        r"(\d+)章",  # Chinese
        r"#(\d+)",
        r"ep\s*(\d+)",  # Episode
        r"episode\s*(\d+)",
    ]

    text_lower = text.lower()

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue

    # Try to find standalone numbers
    numbers = re.findall(r"\b(\d+)\b", text)
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            pass

    return None


def validate_chapter_content(content: str, min_length: int = 50) -> bool:
    """
    Validate if chapter content is meaningful.

    Args:
        content: Chapter content to validate
        min_length: Minimum content length

    Returns:
        True if content appears valid
    """
    if not content or len(content.strip()) < min_length:
        return False

    # Check for common error indicators
    error_indicators = [
        "404",
        "not found",
        "error",
        "access denied",
        "chapter not available",
        "content not found",
    ]

    content_lower = content.lower()
    for indicator in error_indicators:
        if indicator in content_lower:
            return False

    # Check if content is mostly non-alphabetic (might be corrupted)
    alphabetic_chars = sum(1 for c in content if c.isalpha())
    if len(content) > 0 and alphabetic_chars / len(content) < 0.3:
        return False

    return True


def create_safe_directory(path: Path) -> bool:
    """
    Create directory safely with error handling.

    Args:
        path: Directory path to create

    Returns:
        True if directory was created or already exists
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False


def sanitize_markdown_content(content: str, preserve_title_chars: bool = False) -> str:
    """
    Sanitize content for safe markdown usage by escaping special characters.

    Args:
        content: Raw content that may contain markdown-breaking characters
        preserve_title_chars: If True, preserve common title characters like ()[]!? (useful for titles)

    Returns:
        Sanitized content safe for markdown
    """
    if not content:
        return ""

    # Characters that need escaping in markdown
    markdown_special_chars = {
        "\\": "\\\\",  # Backslash (must be first)
        "`": "\\`",  # Backtick
        "*": "\\*",  # Asterisk
        "_": "\\_",  # Underscore
        "{": "\\{",  # Curly braces
        "}": "\\}",
        "#": "\\#",  # Hash
        "+": "\\+",  # Plus
        "-": "\\-",  # Minus (only at start of line)
        ".": "\\.",  # Dot (only when followed by space at start of line)
        "|": "\\|",  # Pipe
        "<": "&lt;",  # Less than
        ">": "&gt;",  # Greater than
        "&": "&amp;",  # Ampersand
    }

    # Conditionally add title characters to escaping
    if not preserve_title_chars:
        markdown_special_chars["("] = "\\("  # Parentheses
        markdown_special_chars[")"] = "\\)"
        markdown_special_chars["["] = "\\["  # Square brackets
        markdown_special_chars["]"] = "\\]"
        markdown_special_chars["!"] = "\\!"  # Exclamation mark
        markdown_special_chars["?"] = "\\?"  # Question mark
        markdown_special_chars["-"] = "\\-"  # Hyphen
        markdown_special_chars["."] = "\\."  # Dot

    # Apply escaping
    for char, escaped in markdown_special_chars.items():
        content = content.replace(char, escaped)

    return content


def validate_markdown_content(content: str) -> bool:
    """
    Validate if content is safe for markdown processing.

    Args:
        content: Content to validate

    Returns:
        True if content appears safe for markdown
    """
    if not content:
        return True

    # Check for potentially problematic patterns
    problematic_patterns = [
        r"```[^`]*$",  # Unclosed code blocks
        r"^\s*#{7,}",  # Too many heading levels
        r"\[.*\]\(.*\).*\[.*\]\(.*\)",  # Nested links (simplified check)
    ]

    for pattern in problematic_patterns:
        if re.search(pattern, content, re.MULTILINE):
            logger.warning(f"Potentially problematic markdown pattern found: {pattern}")
            return False

    return True


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def estimate_reading_time(text: str, words_per_minute: int = 200) -> int:
    """
    Estimate reading time for text.

    Args:
        text: Text to analyze
        words_per_minute: Average reading speed

    Returns:
        Estimated reading time in minutes
    """
    if not text:
        return 0

    word_count = len(text.split())
    return max(1, round(word_count / words_per_minute))


async def retry_async(
    func,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry on

    Returns:
        Result of the function call

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                wait_time = delay * (backoff_factor**attempt)
                logger.debug(
                    f"Retry attempt {attempt + 1} failed, waiting {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries + 1} attempts failed")

    raise last_exception


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to specified length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating

    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse duration string to seconds.

    Args:
        duration_str: Duration string (e.g., "1h30m", "45s", "2.5h")

    Returns:
        Duration in seconds or None if parsing fails
    """
    if not duration_str:
        return None

    # Remove whitespace
    duration_str = duration_str.strip().lower()

    # Try simple float (assume seconds)
    try:
        return int(float(duration_str))
    except ValueError:
        pass

    # Parse complex duration
    total_seconds = 0

    # Hours
    hours_match = re.search(r"(\d+(?:\.\d+)?)h", duration_str)
    if hours_match:
        total_seconds += float(hours_match.group(1)) * 3600

    # Minutes
    minutes_match = re.search(r"(\d+(?:\.\d+)?)m", duration_str)
    if minutes_match:
        total_seconds += float(minutes_match.group(1)) * 60

    # Seconds
    seconds_match = re.search(r"(\d+(?:\.\d+)?)s", duration_str)
    if seconds_match:
        total_seconds += float(seconds_match.group(1))

    return int(total_seconds) if total_seconds > 0 else None
