"""
Core cache manager for web scraping operations.

This module provides the main CacheManager class that handles HTTP response caching
with support for compression, TTL, validation, and size management.
"""

import asyncio
import gzip
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import diskcache

from .cache_config import CacheConfig
from .cache_validator import CacheValidator

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached HTTP response."""

    url: str
    content: bytes
    headers: Dict[str, str]
    status_code: int
    timestamp: datetime
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    expires: Optional[datetime] = None
    size: int = 0
    compressed: bool = False

    def __post_init__(self):
        """Calculate size if not provided."""
        if self.size == 0:
            self.size = len(self.content)

    def is_expired(self, ttl: int) -> bool:
        """Check if entry is expired based on TTL."""
        if self.expires and datetime.now() > self.expires:
            return True

        age = (datetime.now() - self.timestamp).total_seconds()
        return age > ttl

    def is_stale(self) -> bool:
        """Check if entry is stale and needs validation."""
        # Check Cache-Control headers
        cache_control = self.headers.get("cache-control", "").lower()
        if "no-cache" in cache_control or "must-revalidate" in cache_control:
            return True

        # Check if we have validation headers
        return bool(self.etag or self.last_modified)

    def needs_validation(self, ttl: int) -> bool:
        """Check if entry needs validation with server."""
        if self.is_expired(ttl):
            return True

        return self.is_stale()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "url": self.url,
            "headers": self.headers,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
            "etag": self.etag,
            "last_modified": self.last_modified,
            "expires": self.expires.isoformat() if self.expires else None,
            "size": self.size,
            "compressed": self.compressed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], content: bytes) -> "CacheEntry":
        """Create from dictionary and content."""
        return cls(
            url=data["url"],
            content=content,
            headers=data["headers"],
            status_code=data["status_code"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            etag=data.get("etag"),
            last_modified=data.get("last_modified"),
            expires=(
                datetime.fromisoformat(data["expires"]) if data.get("expires") else None
            ),
            size=data.get("size", 0),
            compressed=data.get("compressed", False),
        )


@dataclass
class CacheStats:
    """Cache statistics and metrics."""

    hits: int = 0
    misses: int = 0
    size_bytes: int = 0
    entry_count: int = 0
    hit_rate: float = 0.0

    # Performance metrics
    total_requests: int = 0
    cache_saves: int = 0
    cache_errors: int = 0
    validation_requests: int = 0
    validation_successes: int = 0

    # Timing metrics
    total_cache_time: float = 0.0  # Total time spent on cache operations
    total_validation_time: float = 0.0  # Total time spent on validation
    average_cache_time: float = 0.0
    average_validation_time: float = 0.0

    # Size metrics
    bytes_saved: int = 0  # Total bytes saved by caching
    compression_ratio: float = 0.0

    def update_hit_rate(self):
        """Update hit rate calculation."""
        total = self.hits + self.misses
        self.hit_rate = (self.hits / total) if total > 0 else 0.0

    def update_averages(self):
        """Update average timing metrics."""
        if self.total_requests > 0:
            self.average_cache_time = self.total_cache_time / self.total_requests

        if self.validation_requests > 0:
            self.average_validation_time = (
                self.total_validation_time / self.validation_requests
            )

    def record_cache_operation(self, operation_time: float):
        """Record a cache operation timing."""
        self.total_requests += 1
        self.total_cache_time += operation_time
        self.update_averages()

    def record_validation_operation(self, operation_time: float, success: bool):
        """Record a validation operation timing."""
        self.validation_requests += 1
        self.total_validation_time += operation_time
        if success:
            self.validation_successes += 1
        self.update_averages()

    def get_validation_success_rate(self) -> float:
        """Get validation success rate."""
        if self.validation_requests == 0:
            return 0.0
        return self.validation_successes / self.validation_requests


class CacheManager:
    """
    Main cache manager for HTTP responses.

    Provides high-level interface for caching HTTP responses with support for:
    - Configurable TTL and size limits
    - Compression
    - HTTP cache validation
    - Provider-specific settings
    """

    def __init__(self, config: CacheConfig):
        """
        Initialize cache manager.

        Args:
            config: Cache configuration
        """
        self.config = config
        self.stats = CacheStats()
        self.validator = CacheValidator(config)

        # Initialize cache directory
        self.cache_dir = config.get_cache_directory()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize diskcache
        self.cache = diskcache.Cache(
            directory=str(self.cache_dir),
            size_limit=config.get_size_limit_bytes(),
            eviction_policy="least-recently-used",
        )

        logger.info(
            f"Cache initialized at {self.cache_dir} with {config.size_limit} limit"
        )

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistent cache keys."""
        parsed = urlparse(url)

        # Remove fragment
        normalized = parsed._replace(fragment="")

        # Sort query parameters, ignoring configured params
        if parsed.query:
            params = parse_qsl(parsed.query)
            # Filter out ignored parameters
            filtered_params = [
                (k, v) for k, v in params if k not in self.config.ignore_query_params
            ]
            query = urlencode(sorted(filtered_params))
            normalized = normalized._replace(query=query)

        # Convert to lowercase domain
        normalized = normalized._replace(netloc=normalized.netloc.lower())

        return urlunparse(normalized)

    def _generate_cache_key(
        self, url: str, headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Generate cache key from URL and relevant headers."""
        normalized_url = self._normalize_url(url)

        # Include headers that affect response content
        relevant_headers = {}
        if headers:
            for header in ["Accept", "Accept-Language", "User-Agent"]:
                header_lower = header.lower()
                if header_lower in headers:
                    relevant_headers[header_lower] = headers[header_lower]

        # Create composite key
        key_data = {"url": normalized_url, "headers": relevant_headers}

        # Hash for consistent length
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _compress_content(self, content: bytes) -> bytes:
        """Compress content using gzip."""
        if not self.config.compression:
            return content

        return gzip.compress(content, compresslevel=self.config.compression_level)

    def _decompress_content(self, content: bytes, compressed: bool) -> bytes:
        """Decompress content if needed."""
        if compressed and self.config.compression:
            return gzip.decompress(content)
        return content

    def _extract_cache_headers(
        self, headers: Dict[str, str]
    ) -> Dict[str, Optional[str]]:
        """Extract cache-relevant headers."""
        return {
            "etag": headers.get("etag"),
            "last_modified": headers.get("last-modified"),
            "expires": headers.get("expires"),
            "cache_control": headers.get("cache-control"),
        }

    def _parse_expires_header(self, expires: str) -> Optional[datetime]:
        """Parse HTTP Expires header."""
        try:
            # Try common HTTP date formats
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(expires)
        except (ValueError, TypeError):
            return None

    async def get(
        self, url: str, headers: Optional[Dict[str, str]] = None, provider: str = None
    ) -> Optional[CacheEntry]:
        """
        Get cached response for URL.

        Args:
            url: URL to get from cache
            headers: Request headers that might affect caching
            provider: Provider name for provider-specific settings

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        start_time = time.time()

        if not self.config.enabled:
            return None

        if provider and not self.config.is_provider_enabled(provider):
            return None

        cache_key = self._generate_cache_key(url, headers)

        logger.debug(f"Cache lookup for {url} (provider: {provider or 'default'})")

        try:
            # Get from cache
            cached_data = self.cache.get(cache_key)
            if cached_data is None:
                self.stats.misses += 1
                operation_time = time.time() - start_time
                self.stats.record_cache_operation(operation_time)
                logger.debug(
                    f"Cache miss for {url} (lookup time: {operation_time*1000:.2f}ms)"
                )
                return None

            # Unpack cached data
            metadata, content = cached_data

            # Decompress content
            content = self._decompress_content(
                content, metadata.get("compressed", False)
            )

            # Create cache entry
            entry = CacheEntry.from_dict(metadata, content)

            # Check if expired or needs validation
            ttl = (
                self.config.get_provider_ttl(provider)
                if provider
                else self.config.default_ttl
            )

            # Use validator for comprehensive validation
            if self.validator.should_validate(entry, ttl):
                # Remove expired/invalid entry
                del self.cache[cache_key]
                self.stats.misses += 1
                logger.debug(f"Cache entry requires validation/expired for {url}")
                return None

            # Validate content integrity
            if not self.validator.validate_content_integrity(entry):
                # Remove corrupted entry
                del self.cache[cache_key]
                self.stats.misses += 1
                logger.warning(f"Cache entry failed integrity check for {url}")
                return None

            self.stats.hits += 1
            self.stats.update_hit_rate()

            operation_time = time.time() - start_time
            self.stats.record_cache_operation(operation_time)
            self.stats.bytes_saved += len(entry.content)

            logger.debug(
                f"Cache hit for {url} (lookup time: {operation_time*1000:.2f}ms, size: {len(entry.content)} bytes)"
            )
            return entry

        except Exception as e:
            operation_time = time.time() - start_time
            self.stats.record_cache_operation(operation_time)
            self.stats.cache_errors += 1
            logger.warning(
                f"Error retrieving from cache: {e} (lookup time: {operation_time*1000:.2f}ms)"
            )
            self.stats.misses += 1
            return None

    async def set(
        self,
        url: str,
        content: bytes,
        headers: Dict[str, str],
        status_code: int,
        provider: str = None,
    ) -> bool:
        """
        Store response in cache.

        Args:
            url: URL of the response
            content: Response content
            headers: Response headers
            status_code: HTTP status code
            provider: Provider name for provider-specific settings

        Returns:
            True if cached successfully, False otherwise
        """
        start_time = time.time()

        if not self.config.enabled:
            return False

        if provider and not self.config.is_provider_enabled(provider):
            return False

        # Use validator to determine if response should be cached
        if not self.validator.should_cache_response(status_code, headers):
            logger.debug(f"Response should not be cached: {status_code} {url}")
            return False

        cache_key = self._generate_cache_key(url, {})

        logger.debug(
            f"Caching response for {url} (status: {status_code}, size: {len(content)} bytes)"
        )

        try:
            # Extract cache headers
            cache_headers = self._extract_cache_headers(headers)

            # Parse expires header
            expires = None
            if cache_headers["expires"]:
                expires = self._parse_expires_header(cache_headers["expires"])

            # Compress content
            compressed_content = self._compress_content(content)
            compressed = len(compressed_content) < len(content)

            # Create cache entry with original content for metadata
            # but we'll store compressed content separately
            entry = CacheEntry(
                url=url,
                content=content,  # Keep original content in entry for size validation
                headers=headers,
                status_code=status_code,
                timestamp=datetime.now(),
                etag=cache_headers["etag"],
                last_modified=cache_headers["last_modified"],
                expires=expires,
                size=len(content),  # Original content size
                compressed=compressed,
            )

            # Store in cache (metadata + compressed content)
            cached_data = (entry.to_dict(), compressed_content)
            self.cache.set(cache_key, cached_data)

            # Update stats
            self.stats.entry_count = len(self.cache)
            self.stats.size_bytes = self.cache.volume()
            self.stats.cache_saves += 1

            operation_time = time.time() - start_time
            compression_ratio = (
                len(compressed_content) / len(content) if len(content) > 0 else 1.0
            )
            self.stats.compression_ratio = (
                self.stats.compression_ratio + compression_ratio
            ) / 2  # Running average

            logger.debug(
                f"Cached response for {url} (store time: {operation_time*1000:.2f}ms, "
                f"size: {len(content)} bytes, compressed: {compressed}, "
                f"compression ratio: {compression_ratio:.2f})"
            )
            return True

        except Exception as e:
            operation_time = time.time() - start_time
            self.stats.cache_errors += 1
            logger.warning(
                f"Error storing in cache: {e} (store time: {operation_time*1000:.2f}ms)"
            )
            return False

    async def validate_with_server(
        self,
        url: str,
        session,
        headers: Optional[Dict[str, str]] = None,
        provider: str = None,
    ) -> Optional["CacheEntry"]:
        """
        Validate cached entry with server using conditional requests.

        Args:
            url: URL to validate
            session: aiohttp session for making requests
            headers: Request headers that might affect caching
            provider: Provider name for provider-specific settings

        Returns:
            CacheEntry if still valid, None if invalid or not found
        """
        start_time = time.time()
        cache_key = self._generate_cache_key(url, headers)

        logger.debug(f"Server validation for {url}")

        try:
            # Get cached entry
            cached_data = self.cache.get(cache_key)
            if cached_data is None:
                return None

            metadata, content = cached_data
            content = self._decompress_content(
                content, metadata.get("compressed", False)
            )
            entry = CacheEntry.from_dict(metadata, content)

            # Validate with server
            is_valid, new_headers = await self.validator.validate_with_server(
                entry, session
            )

            if is_valid:
                # Update access time and return entry
                self.cache.touch(cache_key)
                self.stats.hits += 1

                operation_time = time.time() - start_time
                self.stats.record_validation_operation(operation_time, True)
                logger.debug(
                    f"Server validation: entry still valid for {url} (validation time: {operation_time*1000:.2f}ms)"
                )
                return entry
            else:
                # Entry is invalid, remove it
                del self.cache[cache_key]
                self.stats.misses += 1

                operation_time = time.time() - start_time
                self.stats.record_validation_operation(operation_time, False)
                logger.debug(
                    f"Server validation: entry invalid for {url} (validation time: {operation_time*1000:.2f}ms)"
                )
                return None

        except Exception as e:
            operation_time = time.time() - start_time
            self.stats.record_validation_operation(operation_time, False)
            logger.warning(
                f"Error during server validation: {e} (validation time: {operation_time*1000:.2f}ms)"
            )
            return None

    async def invalidate(
        self, url: str, headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Invalidate cached entry for URL.

        Args:
            url: URL to invalidate
            headers: Request headers used for cache key

        Returns:
            True if entry was removed, False if not found
        """
        cache_key = self._generate_cache_key(url, headers)

        try:
            if cache_key in self.cache:
                del self.cache[cache_key]
                self.stats.entry_count = len(self.cache)
                self.stats.size_bytes = self.cache.volume()
                logger.debug(f"Invalidated cache for {url}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Error invalidating cache: {e}")
            return False

    async def clear(self, pattern: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            pattern: Optional URL pattern to match (simple substring match)

        Returns:
            Number of entries removed
        """
        try:
            if pattern is None:
                # Clear all
                count = len(self.cache)
                self.cache.clear()
                self.stats = CacheStats()
                logger.info(f"Cleared all cache entries ({count} removed)")
                return count
            else:
                # Clear matching pattern
                removed = 0
                keys_to_remove = []

                for key in self.cache:
                    try:
                        cached_data = self.cache.get(key)
                        if cached_data:
                            metadata, _ = cached_data
                            if pattern in metadata.get("url", ""):
                                keys_to_remove.append(key)
                    except Exception:
                        continue

                for key in keys_to_remove:
                    try:
                        del self.cache[key]
                        removed += 1
                    except Exception:
                        continue

                # Update stats
                self.stats.entry_count = len(self.cache)
                self.stats.size_bytes = self.cache.volume()

                logger.info(
                    f"Cleared {removed} cache entries matching pattern: {pattern}"
                )
                return removed

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        # Update current stats
        self.stats.entry_count = len(self.cache)
        self.stats.size_bytes = self.cache.volume()
        self.stats.update_hit_rate()

        return self.stats

    def close(self):
        """Close cache and cleanup resources."""
        try:
            self.cache.close()
            logger.debug("Cache closed successfully")
        except Exception as e:
            logger.warning(f"Error closing cache: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
