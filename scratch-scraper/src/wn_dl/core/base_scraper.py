"""
Abstract base scraper class defining the interface for web novel scrapers.

This module provides the base class that all provider-specific scrapers must inherit from.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
import cloudscraper
from bs4 import BeautifulSoup

from .cache_config import CacheConfig
from .cache_manager import CacheManager
from .models import ChapterData, NovelMetadata
from .retry_handler import RetryHandler

logger = logging.getLogger(__name__)


class HTTPError(Exception):
    """Custom HTTP error with status code."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def parse_retry_after_header(retry_after_value: str) -> Optional[float]:
    """
    Parse Retry-After header value and return delay in seconds.

    Supports both numeric (seconds) and HTTP-date formats as per RFC 7231.

    Args:
        retry_after_value: Value from Retry-After header

    Returns:
        Delay in seconds, or None if parsing fails
    """
    if not retry_after_value:
        return None

    retry_after_value = retry_after_value.strip()

    # Try parsing as numeric value (seconds)
    try:
        delay = float(retry_after_value)
        # Ensure reasonable bounds (max 5 minutes)
        return min(max(delay, 1.0), 300.0)
    except ValueError:
        pass

    # Try parsing as HTTP-date format
    try:
        retry_time = parsedate_to_datetime(retry_after_value)
        current_time = datetime.now(retry_time.tzinfo)
        delay = (retry_time - current_time).total_seconds()
        # Ensure reasonable bounds (max 5 minutes, min 1 second)
        return min(max(delay, 1.0), 300.0)
    except (ValueError, TypeError, OverflowError):
        pass

    logger.warning(f"Failed to parse Retry-After header value: {retry_after_value}")
    return None


class BaseNovelScraper(ABC):
    """
    Abstract base class for web novel scrapers.

    This class defines the interface that all provider-specific scrapers must implement.
    It provides common functionality for HTTP requests, rate limiting, and error handling.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        session: Optional[aiohttp.ClientSession] = None,
        cache_config: Optional[CacheConfig] = None,
    ):
        """
        Initialize the scraper with configuration.

        Args:
            config: Provider-specific configuration dictionary
            session: Optional aiohttp session (will create one if not provided)
            cache_config: Optional cache configuration
        """
        self.config = config
        self.session = session
        self.cloudscraper_session = None
        self.base_url = config.get("provider", {}).get("base_url", "")
        self.rate_limit = config.get("request", {}).get("rate_limit", 0.5)
        self.max_retries = config.get("request", {}).get("max_retries", 3)
        self.timeout = config.get("request", {}).get("timeout", 30)
        self.user_agent = config.get("request", {}).get(
            "user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        # Rate limiting
        self._last_request_time = 0.0

        # Initialize cache manager
        self.cache_manager = None
        if cache_config and cache_config.enabled:
            self.cache_manager = CacheManager(cache_config)
            logger.info(f"Cache enabled for {self.__class__.__name__}")

        # Initialize advanced retry handler with configuration
        self.retry_handler = self._create_retry_handler()

        logger.info(
            f"Initialized {self.__class__.__name__} with base_url: {self.base_url}"
        )

    def _get_provider_name(self) -> str:
        """Get provider name for cache operations."""
        return self.config.get("provider", {}).get(
            "name", self.__class__.__name__.lower()
        )

    def _create_retry_handler(self) -> RetryHandler:
        """
        Create retry handler with configuration from provider config.

        Returns:
            Configured RetryHandler instance
        """
        from .retry_handler import CircuitBreakerConfig, RateLimitConfig, RetryConfig

        # Get retry configuration from provider config
        error_handling = self.config.get("error_handling", {})
        request_config = self.config.get("request", {})

        # Configure retry behavior with provider-specific delays
        retry_delays = error_handling.get("retry_delays", [1, 2, 4, 8])
        retry_config = RetryConfig(
            max_retries=request_config.get("max_retries", 3),
            base_delay=retry_delays[0] if retry_delays else 1.0,
            max_delay=retry_delays[-1] if retry_delays else 30.0,
            backoff_factor=2.0,
            jitter=True,
            retry_on_status_codes=error_handling.get(
                "retry_on_status", [429, 500, 502, 503, 504]
            ),
        )

        # Configure circuit breaker with provider-specific settings
        circuit_breaker_config = error_handling.get("circuit_breaker", {})
        circuit_config = CircuitBreakerConfig(
            failure_threshold=circuit_breaker_config.get("failure_threshold", 5),
            recovery_timeout=circuit_breaker_config.get("recovery_timeout", 60.0),
        )

        # Configure adaptive rate limiting with provider-specific settings
        rate_limiting_config = error_handling.get("rate_limiting", {})
        rate_limit_config = RateLimitConfig(
            requests_per_second=rate_limiting_config.get(
                "requests_per_second", 1.0 / request_config.get("rate_limit", 0.5)
            ),
            burst_size=rate_limiting_config.get("burst_size", 3),
            adaptive=rate_limiting_config.get("adaptive", True),
        )

        return RetryHandler(retry_config, circuit_config, rate_limit_config)

    async def __aenter__(self):
        """Async context manager entry."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = {"User-Agent": self.user_agent}
            headers.update(self.config.get("request", {}).get("headers", {}))

            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)

        # Initialize cloudscraper session
        if self.cloudscraper_session is None:
            self.cloudscraper_session = cloudscraper.create_scraper()
            self.cloudscraper_session.headers.update({"User-Agent": self.user_agent})
            self.cloudscraper_session.headers.update(
                self.config.get("request", {}).get("headers", {})
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
        if self.cloudscraper_session:
            self.cloudscraper_session.close()
        await self.cleanup()

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        import time

        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()

    async def _make_request_raw(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        Make a single HTTP request without retry logic.

        Args:
            url: URL to request
            **kwargs: Additional arguments for aiohttp request

        Returns:
            Response object

        Raises:
            HTTPError: If request fails with non-success status
            Exception: For other request errors
        """
        logger.debug(f"Making request to {url}")

        async with self.session.get(url, **kwargs) as response:
            if response.status == 200:
                return response
            elif response.status in [429, 500, 502, 503, 504]:
                # Check for Retry-After header on 429 responses
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        wait_time = parse_retry_after_header(retry_after)
                        if wait_time:
                            # Create custom exception with retry delay info
                            error = HTTPError(
                                response.status,
                                f"Rate limited, retry after {wait_time}s",
                            )
                            error.retry_after = wait_time
                            raise error

                raise HTTPError(response.status, f"HTTP {response.status}")
            else:
                raise HTTPError(response.status, f"HTTP {response.status}")

    async def _make_request(
        self, url: str, **kwargs
    ) -> Optional[aiohttp.ClientResponse]:
        """
        Make an HTTP request with advanced retry logic.

        Args:
            url: URL to request
            **kwargs: Additional arguments for aiohttp request

        Returns:
            Response object or None if all retries failed
        """
        await self._rate_limit()

        try:
            return await self.retry_handler.execute(
                self._make_request_raw, url, **kwargs
            )
        except Exception as e:
            logger.error(f"All retry attempts failed for {url}: {e}")
            return None

    async def _get_soup_raw(self, url: str) -> BeautifulSoup:
        """
        Make a single request using cloudscraper without retry logic.

        Args:
            url: URL to scrape

        Returns:
            BeautifulSoup object

        Raises:
            HTTPError: If request fails with non-success status
            Exception: For other request errors
        """
        logger.debug(f"Making request to {url}")

        # Initialize cloudscraper session if not already done
        if self.cloudscraper_session is None:
            self.cloudscraper_session = cloudscraper.create_scraper()
            self.cloudscraper_session.headers.update({"User-Agent": self.user_agent})
            self.cloudscraper_session.headers.update(
                self.config.get("request", {}).get("headers", {})
            )

        # Use cloudscraper for Cloudflare bypass
        response = self.cloudscraper_session.get(url, timeout=self.timeout)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")
            return soup
        elif response.status_code in [429, 500, 502, 503, 504]:
            # Check for Retry-After header on 429 responses
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    wait_time = parse_retry_after_header(retry_after)
                    if wait_time:
                        # Create custom exception with retry delay info
                        error = HTTPError(
                            response.status_code,
                            f"Rate limited, retry after {wait_time}s",
                        )
                        error.retry_after = wait_time
                        raise error

            raise HTTPError(response.status_code, f"HTTP {response.status_code}")
        else:
            raise HTTPError(response.status_code, f"HTTP {response.status_code}")

    async def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """
        Get BeautifulSoup object from URL using cloudscraper with advanced retry logic.

        Args:
            url: URL to scrape

        Returns:
            BeautifulSoup object or None if request failed
        """
        await self._rate_limit()

        try:
            return await self.retry_handler.execute(self._get_soup_raw, url)
        except Exception as e:
            logger.error(f"All retry attempts failed for {url}: {e}")
            return None

    async def _make_request_cached(
        self, url: str, **kwargs
    ) -> Optional[aiohttp.ClientResponse]:
        """
        Make HTTP request with caching support.

        Args:
            url: URL to request
            **kwargs: Additional arguments for aiohttp request

        Returns:
            aiohttp.ClientResponse or None if request failed
        """
        if not self.cache_manager:
            # No cache, use regular request
            return await self._make_request(url, **kwargs)

        provider_name = self._get_provider_name()
        request_headers = kwargs.get("headers", {})

        # Check cache first
        cache_entry = await self.cache_manager.get(url, request_headers, provider_name)
        if cache_entry and not cache_entry.needs_validation(
            self.cache_manager.config.get_provider_ttl(provider_name)
        ):
            logger.debug(f"Cache hit for {url}")
            return self._create_cached_response(cache_entry)

        # Make actual request
        response = await self._make_request(url, **kwargs)
        if response and response.status == 200:
            # Cache the response
            content = await response.read()
            await self.cache_manager.set(
                url=url,
                content=content,
                headers=dict(response.headers),
                status_code=response.status,
                provider=provider_name,
            )
            logger.debug(f"Cached response for {url}")

            # Reset response for reading again
            response._body = content

        return response

    async def _get_soup_cached(self, url: str) -> Optional[BeautifulSoup]:
        """
        Get BeautifulSoup object from URL with caching support.

        Args:
            url: URL to scrape

        Returns:
            BeautifulSoup object or None if request failed
        """
        if not self.cache_manager:
            # No cache, use regular method
            return await self._get_soup(url)

        provider_name = self._get_provider_name()

        # Check cache first
        cache_entry = await self.cache_manager.get(url, None, provider_name)
        if cache_entry and not cache_entry.needs_validation(
            self.cache_manager.config.get_provider_ttl(provider_name)
        ):
            logger.debug(f"Cache hit for {url}")
            return BeautifulSoup(cache_entry.content, "html.parser")

        # Make actual request
        soup = await self._get_soup(url)
        if soup:
            # Cache the response
            content = str(soup).encode("utf-8")
            await self.cache_manager.set(
                url=url,
                content=content,
                headers={"content-type": "text/html"},
                status_code=200,
                provider=provider_name,
            )
            logger.debug(f"Cached soup for {url}")

        return soup

    def _create_cached_response(self, cache_entry) -> aiohttp.ClientResponse:
        """
        Create a mock aiohttp.ClientResponse from cached data.

        Args:
            cache_entry: CacheEntry with cached response data

        Returns:
            Mock response object that behaves like aiohttp.ClientResponse
        """
        from aiohttp import ClientResponse
        from aiohttp.client_reqrep import RequestInfo
        from yarl import URL

        class CachedResponse:
            """Mock response object for cached data."""

            def __init__(self, cache_entry):
                self.status = cache_entry.status_code
                self.headers = cache_entry.headers
                self.url = URL(cache_entry.url)
                self._content = cache_entry.content
                self._body = cache_entry.content
                self.content_type = cache_entry.headers.get("content-type", "text/html")

            async def read(self) -> bytes:
                """Read response content."""
                return self._content

            async def text(self, encoding: str = "utf-8") -> str:
                """Get response as text."""
                return self._content.decode(encoding)

            async def json(self, **kwargs):
                """Get response as JSON."""
                import json

                return json.loads(await self.text())

            def __aenter__(self):
                return self

            def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return CachedResponse(cache_entry)

    def _extract_text_by_selector(
        self, soup: BeautifulSoup, selector: str, attribute: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract text using CSS selector.

        Args:
            soup: BeautifulSoup object
            selector: CSS selector
            attribute: Optional attribute to extract instead of text

        Returns:
            Extracted text or None if not found
        """
        try:
            element = soup.select_one(selector)
            if element:
                if attribute:
                    return element.get(attribute)
                else:
                    return element.get_text(strip=True)
        except Exception as e:
            logger.debug(f"Failed to extract with selector '{selector}': {e}")

        return None

    def _extract_list_by_selector(
        self, soup: BeautifulSoup, selector: str, attribute: Optional[str] = None
    ) -> List[str]:
        """
        Extract list of texts using CSS selector.

        Args:
            soup: BeautifulSoup object
            selector: CSS selector
            attribute: Optional attribute to extract instead of text

        Returns:
            List of extracted texts
        """
        try:
            elements = soup.select(selector)
            if attribute:
                return [elem.get(attribute) for elem in elements if elem.get(attribute)]
            else:
                return [
                    elem.get_text(strip=True)
                    for elem in elements
                    if elem.get_text(strip=True)
                ]
        except Exception as e:
            logger.debug(f"Failed to extract list with selector '{selector}': {e}")
            return []

    def _clean_content(self, soup: BeautifulSoup) -> str:
        """
        Clean chapter content by removing ads and unwanted elements while preserving paragraph structure.

        Args:
            soup: BeautifulSoup object containing chapter content

        Returns:
            Cleaned text content with proper paragraph breaks
        """
        # Remove unwanted elements based on configuration
        remove_selectors = self.config.get("content_cleaning", {}).get(
            "remove_selectors", []
        )
        for selector in remove_selectors:
            try:
                for element in soup.select(selector):
                    element.decompose()
            except Exception as e:
                logger.debug(
                    f"Failed to remove elements with selector '{selector}': {e}"
                )

        # Extract text while preserving paragraph structure
        text = self._extract_paragraphs(soup)

        # Apply text processing
        text_processing = self.config.get("content_cleaning", {}).get(
            "text_processing", {}
        )

        if text_processing.get("remove_empty_lines", True):
            # Remove empty lines but preserve paragraph breaks (double newlines)
            import re

            # First, protect double newlines by replacing them with a placeholder
            text = re.sub(r"\n\n", "<<<PARAGRAPH_BREAK>>>", text)
            # Remove empty lines
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            text = "\n".join(lines)
            # Restore paragraph breaks
            text = text.replace("<<<PARAGRAPH_BREAK>>>", "\n\n")

        if text_processing.get("normalize_whitespace", True):
            import re

            # Normalize whitespace within paragraphs but preserve paragraph breaks
            text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces/tabs to single space
            text = re.sub(
                r"\n{3,}", "\n\n", text
            )  # Multiple newlines to double newline

        return text

    def _extract_paragraphs(self, soup: BeautifulSoup) -> str:
        """
        Extract text content while preserving paragraph structure.

        Args:
            soup: BeautifulSoup object containing content

        Returns:
            Text with proper paragraph breaks
        """
        import re

        # Block-level elements that should create paragraph breaks
        block_elements = {
            "p",
            "div",
            "br",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "blockquote",
            "pre",
            "ul",
            "ol",
            "li",
            "section",
            "article",
        }

        paragraphs = []

        # First, try to extract paragraphs from <p> tags specifically
        p_tags = soup.find_all("p")
        if p_tags:
            for p in p_tags:
                text = p.get_text(strip=True)
                if text:
                    paragraphs.append(text)

        # If no <p> tags found or very few, fall back to div-based extraction
        if len(paragraphs) < 2:
            paragraphs = []

            # Look for content in div elements
            content_divs = soup.find_all(["div", "section", "article"])
            for div in content_divs:
                # Skip if this div contains other block elements (likely a container)
                if div.find(["div", "section", "article", "p"]):
                    continue

                text = div.get_text(strip=True)
                if text and len(text) > 20:  # Only consider substantial text blocks
                    paragraphs.append(text)

        # If still no good paragraphs, try line-by-line approach
        if len(paragraphs) < 2:
            paragraphs = []

            # Get all text and split by common paragraph indicators
            all_text = soup.get_text()

            # Split by double newlines, periods followed by newlines, or other indicators
            potential_paragraphs = re.split(
                r"\n\s*\n|\.\s*\n|(?<=[.!?])\s*\n(?=[A-Z])", all_text
            )

            for para in potential_paragraphs:
                text = para.strip()
                if text and len(text) > 20:  # Only substantial paragraphs
                    # Clean up whitespace within the paragraph
                    text = re.sub(r"\s+", " ", text)
                    paragraphs.append(text)

        # Join paragraphs with double newlines
        result = "\n\n".join(paragraphs) if paragraphs else soup.get_text(strip=True)

        # Final cleanup
        result = re.sub(r"\n{3,}", "\n\n", result)  # No more than double newlines
        result = result.strip()

        return result

    def _validate_url(self, url: str) -> bool:
        """
        Validate if URL belongs to this provider.

        Args:
            url: URL to validate

        Returns:
            True if URL is valid for this provider
        """
        try:
            parsed = urlparse(url)
            base_parsed = urlparse(self.base_url)
            return parsed.netloc == base_parsed.netloc
        except Exception:
            return False

    def _is_valid_chapter_url(self, url: str) -> bool:
        """
        Validate if a URL is a valid chapter URL and not an error page.

        Args:
            url: Chapter URL to validate

        Returns:
            True if URL appears to be a valid chapter, False if it looks like an error page
        """
        if not url:
            return False

        # Check for common error indicators in URLs
        error_indicators = [
            "404",
            "error",
            "not-found",
            "access-denied",
            "forbidden",
            "unavailable",
            "missing",
            "invalid",
        ]

        url_lower = url.lower()
        for indicator in error_indicators:
            if indicator in url_lower:
                logger.debug(f"Filtering out error page URL: {url}")
                return False

        return True

    def _extract_title_from_content(
        self, content: str, current_title: str, chapter_number: Optional[int] = None
    ) -> str:
        """
        Extract a better chapter title from content when the current title is just "Chapter X".

        Searches the first few paragraphs for patterns like:
        - "Chapter 447 – Wicked Heart Granny (6)"
        - "Chapter 123: The Beginning of the End"
        - "447 - The Final Battle"

        Args:
            content: Chapter content text
            current_title: Current chapter title (e.g., "Chapter 447")
            chapter_number: Chapter number if available

        Returns:
            Enhanced title if found, otherwise returns current_title
        """
        if not content or not current_title:
            return current_title

        # Check if feature is enabled in configuration
        content_config = self.config.get("content_cleaning", {}).get(
            "text_processing", {}
        )
        if not content_config:
            # Try alternative config structure for NovelFull
            content_config = self.config.get("content_processing", {})

        if not content_config.get("enhance_titles_from_content", True):
            return current_title

        import re

        # Only enhance titles that are just "Chapter X" format
        if not re.match(r"^Chapter\s+\d+$", current_title, re.IGNORECASE):
            return current_title

        # Extract chapter number from current title
        chapter_num_match = re.search(r"Chapter\s+(\d+)", current_title, re.IGNORECASE)
        if not chapter_num_match:
            return current_title

        chapter_num = chapter_num_match.group(1)

        # Get configured number of paragraphs to search for better titles
        search_paragraphs = content_config.get("title_search_paragraphs", 3)
        paragraphs = content.split("\n\n")[:search_paragraphs]
        content_to_search = "\n\n".join(paragraphs)

        # Enhanced Pattern 1: "Chapter XXX – Title" with various separators and formats
        pattern1_variants = [
            # Standard dash/em-dash patterns
            rf"Chapter\s+{re.escape(chapter_num)}\s*(?:–|—|-)\s*(.+?)(?:\n|$)",
            # With parentheses around chapter number
            rf"Chapter\s*\(\s*{re.escape(chapter_num)}\s*\)\s*(?:–|—|-)\s*(.+?)(?:\n|$)",
            # With brackets around chapter number
            rf"Chapter\s*\[\s*{re.escape(chapter_num)}\s*\]\s*(?:–|—|-)\s*(.+?)(?:\n|$)",
            # With period after chapter number
            rf"Chapter\s+{re.escape(chapter_num)}\.\s*(?:–|—|-)\s*(.+?)(?:\n|$)",
            # Multiple spaces or tabs
            rf"Chapter\s+{re.escape(chapter_num)}\s*(?:–|—|-)\s+(.+?)(?:\n|$)",
        ]

        for pattern in pattern1_variants:
            match = re.search(pattern, content_to_search, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted_title = self._clean_extracted_title(
                    match.group(1), chapter_num
                )
                if extracted_title:
                    logger.debug(
                        f"Enhanced title from content (pattern 1): '{current_title}' -> 'Chapter {chapter_num} - {extracted_title}'"
                    )
                    return f"Chapter {chapter_num} - {extracted_title}"

        # Enhanced Pattern 2: "Chapter XXX: Title" with various colon formats
        pattern2_variants = [
            # Standard colon pattern
            rf"Chapter\s+{re.escape(chapter_num)}\s*:\s*(.+?)(?:\n|$)",
            # With parentheses around chapter number
            rf"Chapter\s*\(\s*{re.escape(chapter_num)}\s*\)\s*:\s*(.+?)(?:\n|$)",
            # With brackets around chapter number
            rf"Chapter\s*\[\s*{re.escape(chapter_num)}\s*\]\s*:\s*(.+?)(?:\n|$)",
            # With period after chapter number
            rf"Chapter\s+{re.escape(chapter_num)}\.\s*:\s*(.+?)(?:\n|$)",
            # Double colon
            rf"Chapter\s+{re.escape(chapter_num)}\s*::\s*(.+?)(?:\n|$)",
        ]

        for pattern in pattern2_variants:
            match = re.search(pattern, content_to_search, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted_title = self._clean_extracted_title(
                    match.group(1), chapter_num
                )
                if extracted_title:
                    logger.debug(
                        f"Enhanced title from content (pattern 2): '{current_title}' -> 'Chapter {chapter_num}: {extracted_title}'"
                    )
                    return f"Chapter {chapter_num}: {extracted_title}"

        # Enhanced Pattern 3: Number-only patterns with various formats
        pattern3_variants = [
            # Standard number with dash
            rf"^{re.escape(chapter_num)}\s*(?:–|—|-)\s*(.+?)(?:\n|$)",
            # Number with colon
            rf"^{re.escape(chapter_num)}\s*:\s*(.+?)(?:\n|$)",
            # Number with period
            rf"^{re.escape(chapter_num)}\.\s*(.+?)(?:\n|$)",
            # Number with parentheses
            rf"^\({re.escape(chapter_num)}\)\s*(.+?)(?:\n|$)",
            # Number with brackets
            rf"^\[{re.escape(chapter_num)}\]\s*(.+?)(?:\n|$)",
            # Number with double dash
            rf"^{re.escape(chapter_num)}\s*--\s*(.+?)(?:\n|$)",
        ]

        for pattern in pattern3_variants:
            match = re.search(pattern, content_to_search, re.MULTILINE)
            if match:
                extracted_title = self._clean_extracted_title(
                    match.group(1), chapter_num
                )
                if extracted_title:
                    logger.debug(
                        f"Enhanced title from content (pattern 3): '{current_title}' -> 'Chapter {chapter_num} - {extracted_title}'"
                    )
                    return f"Chapter {chapter_num} - {extracted_title}"

        # New Pattern 4: Alternative chapter formats
        pattern4_variants = [
            # "Ch XXX - Title" or "Ch. XXX - Title"
            rf"Ch\.?\s+{re.escape(chapter_num)}\s*(?:–|—|-|:)\s*(.+?)(?:\n|$)",
            # "Episode XXX - Title"
            rf"Episode\s+{re.escape(chapter_num)}\s*(?:–|—|-|:)\s*(.+?)(?:\n|$)",
            # "Part XXX - Title"
            rf"Part\s+{re.escape(chapter_num)}\s*(?:–|—|-|:)\s*(.+?)(?:\n|$)",
            # "Volume X Chapter Y - Title" (extract just the title part)
            rf"Volume\s+\d+\s+Chapter\s+{re.escape(chapter_num)}\s*(?:–|—|-|:)\s*(.+?)(?:\n|$)",
        ]

        for pattern in pattern4_variants:
            match = re.search(pattern, content_to_search, re.IGNORECASE | re.MULTILINE)
            if match:
                extracted_title = self._clean_extracted_title(
                    match.group(1), chapter_num
                )
                if extracted_title:
                    logger.debug(
                        f"Enhanced title from content (pattern 4): '{current_title}' -> 'Chapter {chapter_num} - {extracted_title}'"
                    )
                    return f"Chapter {chapter_num} - {extracted_title}"

        # Pattern 5: Look for actual title lines (very strict criteria)
        first_paragraph = paragraphs[0] if paragraphs else ""
        lines = first_paragraph.split("\n")

        for line in lines[:2]:  # Check only first 2 lines of first paragraph
            line = line.strip()
            if not line:
                continue

            # Must be reasonable title length (not too short, not too long)
            if len(line) < 3 or len(line) > 60:
                continue

            # Skip if line contains narrative indicators (verbs, articles, pronouns)
            narrative_indicators = [
                "he ",
                "she ",
                "they ",
                "it ",
                "was ",
                "were ",
                "is ",
                "are ",
                "had ",
                "have ",
                "has ",
                "said ",
                "asked ",
                "replied ",
                "thought ",
                "looked ",
                "walked ",
                "came ",
                "went ",
                "approached ",
                "noticed ",
                "clicked ",
                "moved ",
                "turned ",
                "felt ",
                "saw ",
                "heard ",
                "the ",
                "and ",
                "but ",
                "or ",
                "so ",
                "then ",
                "now ",
                "when ",
                "where ",
                "how ",
                ".",
                "!",
                "?",
                ",",  # Sentences typically end with punctuation
            ]

            line_lower = line.lower()
            if any(indicator in line_lower for indicator in narrative_indicators):
                continue

            # Must look like a title: short phrases, proper nouns, or special formatting
            title_indicators = [
                # Contains parentheses with content (often used in titles)
                r"\([^)]+\)",
                # Contains arrows or special symbols (→, ←, etc.)
                r"[→←↑↓]",
                # Contains em-dashes or special dashes
                r"[–—]",
                # All caps words (often used in titles)
                r"\b[A-Z]{2,}\b",
                # Title case pattern (multiple capitalized words)
                r"^[A-Z][a-z]*(?:\s+[A-Z][a-z]*){1,}$",
                # Contains numbers in a title-like way
                r"^\w+\s+\d+$|^\d+\s+\w+$",
            ]

            if any(re.search(pattern, line) for pattern in title_indicators):
                # Don't extract if it's just "Chapter X" again
                if line.lower() != f"chapter {chapter_num}".lower():
                    logger.debug(
                        f"Enhanced title from content line: '{current_title}' -> 'Chapter {chapter_num} - {line}'"
                    )
                    return f"Chapter {chapter_num} - {line}"

        # No better title found, return original
        return current_title

    def _clean_extracted_title(self, raw_title: str, chapter_num: str) -> Optional[str]:
        """
        Clean and validate an extracted title.

        Args:
            raw_title: Raw extracted title text
            chapter_num: Chapter number for validation

        Returns:
            Cleaned title or None if invalid
        """
        if not raw_title:
            return None

        import re

        # Basic cleanup
        extracted_title = raw_title.strip()

        # Remove excessive whitespace
        extracted_title = re.sub(r"\s+", " ", extracted_title)

        # Remove trailing punctuation that's not part of the title
        extracted_title = extracted_title.strip(".,!?;")

        # Must have reasonable length
        if len(extracted_title) < 2 or len(extracted_title) > 100:
            return None

        # Don't extract if it's just the chapter number again
        if extracted_title.lower() in [
            f"chapter {chapter_num}",
            chapter_num,
            f"ch {chapter_num}",
            f"ch. {chapter_num}",
            f"episode {chapter_num}",
            f"part {chapter_num}",
        ]:
            return None

        # Remove common prefixes that got captured
        prefixes_to_remove = [
            r"^chapter\s+\d+\s*[–—\-:]\s*",
            r"^ch\.?\s+\d+\s*[–—\-:]\s*",
            r"^episode\s+\d+\s*[–—\-:]\s*",
            r"^part\s+\d+\s*[–—\-:]\s*",
        ]

        for prefix in prefixes_to_remove:
            extracted_title = re.sub(
                prefix, "", extracted_title, flags=re.IGNORECASE
            ).strip()

        # Final validation - must not be empty after cleanup
        if not extracted_title or len(extracted_title) < 2:
            return None

        # Remove quotes if the entire title is quoted
        if (extracted_title.startswith('"') and extracted_title.endswith('"')) or (
            extracted_title.startswith("'") and extracted_title.endswith("'")
        ):
            extracted_title = extracted_title[1:-1].strip()

        return extracted_title if extracted_title else None

    # Abstract methods that must be implemented by subclasses

    @abstractmethod
    async def get_novel_metadata(self, novel_url: str) -> Optional[NovelMetadata]:
        """
        Extract novel metadata from the main novel page.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            NovelMetadata object or None if extraction failed
        """
        pass

    @abstractmethod
    async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Get list of all available chapters.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            List of dictionaries containing chapter info (title, url, number)
        """
        pass

    @abstractmethod
    async def scrape_chapter_content(self, chapter_url: str) -> Optional[ChapterData]:
        """
        Extract content from a single chapter.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            ChapterData object or None if extraction failed
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            Provider name string
        """
        pass

    async def cleanup(self):
        """Clean up resources including cache manager."""
        if self.cache_manager:
            self.cache_manager.close()
            logger.debug("Cache manager closed")
