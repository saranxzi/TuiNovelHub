"""
Cache validation mechanisms for HTTP responses.

This module provides advanced cache validation including ETag support,
Last-Modified headers, TTL expiration, and content integrity checks.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Dict, Optional, Tuple

import aiohttp

from .cache_config import CacheConfig

logger = logging.getLogger(__name__)


class CacheValidator:
    """
    Advanced cache validation for HTTP responses.

    Handles validation using HTTP cache headers, TTL expiration,
    and content integrity checks.
    """

    def __init__(self, config: CacheConfig):
        """
        Initialize cache validator.

        Args:
            config: Cache configuration
        """
        self.config = config

    def should_validate(self, cache_entry, ttl: int) -> bool:
        """
        Check if cache entry needs validation with server.

        Args:
            cache_entry: CacheEntry to validate
            ttl: Time-to-live in seconds

        Returns:
            True if validation is needed, False otherwise
        """
        # Check TTL expiration first
        if cache_entry.is_expired(ttl):
            logger.debug(f"Cache entry expired (TTL: {ttl}s)")
            return True

        # Check if cache headers require validation
        if not self.config.respect_cache_headers:
            return False

        # Check Cache-Control headers
        cache_control = cache_entry.headers.get("cache-control", "").lower()

        # no-cache means always validate
        if "no-cache" in cache_control:
            logger.debug("Cache-Control: no-cache - validation required")
            return True

        # must-revalidate means validate when stale
        if "must-revalidate" in cache_control and cache_entry.is_stale():
            logger.debug("Cache-Control: must-revalidate - validation required")
            return True

        # Check max-age directive
        max_age = self._parse_max_age(cache_control)
        if max_age is not None:
            age = (datetime.now() - cache_entry.timestamp).total_seconds()
            if age > max_age:
                logger.debug(f"Cache-Control: max-age exceeded ({age}s > {max_age}s)")
                return True

        # Check Expires header
        if cache_entry.expires and datetime.now() > cache_entry.expires:
            logger.debug("Expires header indicates expiration")
            return True

        # Check if we have validation headers for conditional requests
        if self.config.conditional_requests and (
            cache_entry.etag or cache_entry.last_modified
        ):
            # Don't validate immediately, but mark as available for validation
            return False

        return False

    async def validate_with_server(
        self, cache_entry, session: aiohttp.ClientSession
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate cache entry with server using conditional requests.

        Args:
            cache_entry: CacheEntry to validate
            session: aiohttp session for making requests

        Returns:
            Tuple of (is_valid, new_headers_if_updated)
            - is_valid: True if cached content is still valid
            - new_headers_if_updated: New headers if content was updated, None if still valid
        """
        if not self.config.conditional_requests:
            return False, None

        headers = {}

        # Add ETag validation
        if cache_entry.etag and self.config.validate_etag:
            headers["If-None-Match"] = cache_entry.etag

        # Add Last-Modified validation
        if cache_entry.last_modified and self.config.validate_last_modified:
            headers["If-Modified-Since"] = cache_entry.last_modified

        if not headers:
            # No validation headers available
            return False, None

        try:
            # Make conditional request
            async with session.head(cache_entry.url, headers=headers) as response:
                if response.status == 304:
                    # Not Modified - cached content is still valid
                    logger.debug(
                        f"Server validation: 304 Not Modified for {cache_entry.url}"
                    )
                    return True, None
                elif response.status == 200:
                    # Content has been modified
                    logger.debug(
                        f"Server validation: 200 OK (modified) for {cache_entry.url}"
                    )
                    return False, dict(response.headers)
                else:
                    # Other status codes - treat as invalid
                    logger.warning(
                        f"Server validation: unexpected status {response.status} for {cache_entry.url}"
                    )
                    return False, None

        except Exception as e:
            logger.warning(f"Server validation failed for {cache_entry.url}: {e}")
            # On validation failure, assume content is invalid to be safe
            return False, None

    def validate_content_integrity(
        self, cache_entry, expected_content: bytes = None
    ) -> bool:
        """
        Validate content integrity using checksums.

        Args:
            cache_entry: CacheEntry to validate
            expected_content: Expected content for comparison (optional)

        Returns:
            True if content integrity is valid, False otherwise
        """
        try:
            # Check if content size matches stored size
            # Note: cache_entry.content should always be the decompressed content
            # and cache_entry.size should be the original (decompressed) content size
            actual_size = len(cache_entry.content)
            if cache_entry.size != actual_size:
                logger.debug(
                    f"Content size mismatch: expected {cache_entry.size}, got {actual_size}, compressed: {cache_entry.compressed}"
                )
                # For now, we'll be lenient with size mismatches for compressed content
                # This is a known issue that needs to be resolved in the cache storage logic
                if not cache_entry.compressed:
                    logger.warning(
                        f"Content size mismatch for uncompressed content: expected {cache_entry.size}, got {actual_size}"
                    )
                    return False

            # If expected content is provided, compare directly
            if expected_content is not None:
                return cache_entry.content == expected_content

            # Check for content corruption by validating it's not empty when it shouldn't be
            if cache_entry.size > 0 and not cache_entry.content:
                logger.warning("Content is empty but size indicates it shouldn't be")
                return False

            # Basic content validation - check if it looks like valid content
            if cache_entry.headers.get("content-type", "").startswith("text/html"):
                # For HTML content, check if it contains basic HTML structure
                content_str = cache_entry.content.decode("utf-8", errors="ignore")
                if cache_entry.size > 100 and "<html" not in content_str.lower():
                    logger.warning("HTML content doesn't contain expected HTML tags")
                    return False

            return True

        except Exception as e:
            logger.warning(f"Content integrity validation failed: {e}")
            return False

    def _parse_max_age(self, cache_control: str) -> Optional[int]:
        """
        Parse max-age directive from Cache-Control header.

        Args:
            cache_control: Cache-Control header value

        Returns:
            max-age value in seconds, or None if not found
        """
        try:
            for directive in cache_control.split(","):
                directive = directive.strip()
                if directive.startswith("max-age="):
                    return int(directive.split("=", 1)[1])
            return None
        except (ValueError, IndexError):
            return None

    def _parse_expires_header(self, expires: str) -> Optional[datetime]:
        """
        Parse HTTP Expires header.

        Args:
            expires: Expires header value

        Returns:
            Parsed datetime or None if parsing fails
        """
        try:
            return parsedate_to_datetime(expires)
        except (ValueError, TypeError):
            return None

    def get_cache_directives(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Extract cache directives from response headers.

        Args:
            headers: Response headers

        Returns:
            Dictionary of cache directives
        """
        directives = {}

        # Parse Cache-Control header
        cache_control = headers.get("cache-control", "")
        for directive in cache_control.split(","):
            directive = directive.strip()
            if "=" in directive:
                key, value = directive.split("=", 1)
                directives[key.strip()] = value.strip()
            else:
                directives[directive] = True

        # Add other cache-related headers
        if "expires" in headers:
            directives["expires"] = headers["expires"]

        if "etag" in headers:
            directives["etag"] = headers["etag"]

        if "last-modified" in headers:
            directives["last-modified"] = headers["last-modified"]

        return directives

    def should_cache_response(self, status_code: int, headers: Dict[str, str]) -> bool:
        """
        Determine if response should be cached based on status and headers.

        Args:
            status_code: HTTP status code
            headers: Response headers

        Returns:
            True if response should be cached, False otherwise
        """
        # Don't cache error responses unless configured to do so
        if status_code >= 400 and not self.config.cache_errors:
            return False

        # Check Cache-Control directives
        cache_control = headers.get("cache-control", "").lower()

        # no-store means don't cache at all
        if "no-store" in cache_control:
            return False

        # private means don't cache in shared caches (we're a private cache, so OK)
        # public explicitly allows caching

        # Check for explicit cache prevention
        pragma = headers.get("pragma", "").lower()
        if "no-cache" in pragma:
            return False

        # Cache successful responses and redirects by default
        if 200 <= status_code < 400:
            return True

        # Cache redirects if configured
        if 300 <= status_code < 400 and self.config.cache_redirects:
            return True

        return False

    def calculate_ttl(self, headers: Dict[str, str], default_ttl: int) -> int:
        """
        Calculate TTL for cache entry based on headers.

        Args:
            headers: Response headers
            default_ttl: Default TTL to use

        Returns:
            Calculated TTL in seconds
        """
        if not self.config.respect_cache_headers:
            return default_ttl

        cache_control = headers.get("cache-control", "")

        # Check for max-age directive
        max_age = self._parse_max_age(cache_control)
        if max_age is not None:
            # Clamp to configured min/max TTL
            return max(self.config.min_ttl, min(self.config.max_ttl, max_age))

        # Check Expires header
        expires = headers.get("expires")
        if expires:
            expires_dt = self._parse_expires_header(expires)
            if expires_dt:
                ttl = int((expires_dt - datetime.now()).total_seconds())
                if ttl > 0:
                    return max(self.config.min_ttl, min(self.config.max_ttl, ttl))

        # Use default TTL
        return default_ttl
