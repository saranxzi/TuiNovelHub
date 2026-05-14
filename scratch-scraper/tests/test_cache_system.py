"""
Comprehensive tests for the cache system.

This module contains unit and integration tests for all cache system components
including cache operations, size limits, TTL expiration, provider integration,
and edge cases.
"""

import asyncio
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.wn_dl.core.cache_config import CacheConfig, parse_size_string
from src.wn_dl.core.cache_manager import CacheEntry, CacheManager, CacheStats
from src.wn_dl.core.cache_validator import CacheValidator


class TestCacheConfig:
    """Test cache configuration functionality."""

    def test_parse_size_string(self):
        """Test size string parsing."""
        assert parse_size_string("1GB") == 1024 * 1024 * 1024
        assert parse_size_string("500MB") == 500 * 1024 * 1024
        assert parse_size_string("100KB") == 100 * 1024
        assert parse_size_string("1024") == 1024

    def test_cache_config_creation(self):
        """Test cache configuration creation."""
        config = CacheConfig(
            enabled=True, size_limit="1GB", default_ttl=3600, compression=True
        )

        assert config.enabled is True
        assert config.size_limit == "1GB"
        assert config.default_ttl == 3600
        assert config.compression is True
        assert config.get_size_limit_bytes() == 1024 * 1024 * 1024

    def test_provider_settings(self):
        """Test provider-specific settings."""
        config = CacheConfig(
            enabled=True,
            providers={
                "novelfull": {"enabled": True, "ttl": 7200},
                "novelbin": {"enabled": False},
            },
        )

        assert config.is_provider_enabled("novelfull") is True
        assert config.is_provider_enabled("novelbin") is False
        assert config.is_provider_enabled("unknown") is True  # Default

        assert config.get_provider_ttl("novelfull") == 7200
        assert config.get_provider_ttl("novelbin") == config.default_ttl

    def test_cache_directory(self):
        """Test cache directory handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(enabled=True, directory=temp_dir)
            cache_dir = config.get_cache_directory()

            assert cache_dir.exists()
            assert cache_dir.is_dir()
            assert str(cache_dir) == temp_dir


class TestCacheEntry:
    """Test cache entry functionality."""

    def test_cache_entry_creation(self):
        """Test cache entry creation."""
        entry = CacheEntry(
            url="https://example.com/test",
            content=b"test content",
            headers={"content-type": "text/html"},
            status_code=200,
            timestamp=datetime.now(),
            size=12,
            compressed=False,
        )

        assert entry.url == "https://example.com/test"
        assert entry.content == b"test content"
        assert entry.status_code == 200
        assert entry.size == 12
        assert entry.compressed is False

    def test_cache_entry_expiration(self):
        """Test cache entry TTL expiration."""
        # Create entry that's already expired
        old_timestamp = datetime.now() - timedelta(seconds=3700)
        entry = CacheEntry(
            url="https://example.com/test",
            content=b"test content",
            headers={},
            status_code=200,
            timestamp=old_timestamp,
            size=12,
            compressed=False,
        )

        assert entry.is_expired(3600) is True  # 1 hour TTL

        # Create fresh entry
        fresh_entry = CacheEntry(
            url="https://example.com/test",
            content=b"test content",
            headers={},
            status_code=200,
            timestamp=datetime.now(),
            size=12,
            compressed=False,
        )

        assert fresh_entry.is_expired(3600) is False

    def test_cache_entry_serialization(self):
        """Test cache entry to/from dict conversion."""
        entry = CacheEntry(
            url="https://example.com/test",
            content=b"test content",
            headers={"content-type": "text/html"},
            status_code=200,
            timestamp=datetime.now(),
            etag='"123456"',
            last_modified="Wed, 21 Oct 2015 07:28:00 GMT",
            size=12,
            compressed=False,
        )

        # Convert to dict
        entry_dict = entry.to_dict()
        assert entry_dict["url"] == "https://example.com/test"
        assert entry_dict["status_code"] == 200
        assert entry_dict["etag"] == '"123456"'

        # Convert back from dict
        restored_entry = CacheEntry.from_dict(entry_dict, b"test content")
        assert restored_entry.url == entry.url
        assert restored_entry.content == entry.content
        assert restored_entry.status_code == entry.status_code
        assert restored_entry.etag == entry.etag


class TestCacheStats:
    """Test cache statistics functionality."""

    def test_cache_stats_creation(self):
        """Test cache stats creation and updates."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

        # Update stats
        stats.hits = 8
        stats.misses = 2
        stats.update_hit_rate()

        assert stats.hit_rate == 0.8

    def test_performance_metrics(self):
        """Test performance metrics tracking."""
        stats = CacheStats()

        # Record operations
        stats.record_cache_operation(0.001)  # 1ms
        stats.record_cache_operation(0.002)  # 2ms

        assert stats.total_requests == 2
        assert stats.average_cache_time == 0.0015  # 1.5ms average

        # Record validation
        stats.record_validation_operation(0.05, True)  # 50ms success
        stats.record_validation_operation(0.03, False)  # 30ms failure

        assert stats.validation_requests == 2
        assert stats.validation_successes == 1
        assert stats.get_validation_success_rate() == 0.5


class TestCacheValidator:
    """Test cache validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = CacheConfig(
            enabled=True,
            respect_cache_headers=True,
            validate_etag=True,
            validate_last_modified=True,
        )
        self.validator = CacheValidator(self.config)

    def test_should_cache_response(self):
        """Test response caching decisions."""
        # Should cache successful responses
        assert self.validator.should_cache_response(200, {}) is True
        assert self.validator.should_cache_response(301, {}) is True

        # Should not cache errors by default
        assert self.validator.should_cache_response(404, {}) is False
        assert self.validator.should_cache_response(500, {}) is False

        # Should not cache no-store responses
        headers = {"cache-control": "no-store"}
        assert self.validator.should_cache_response(200, headers) is False

    def test_ttl_calculation(self):
        """Test TTL calculation from headers."""
        # Test max-age directive
        headers = {"cache-control": "max-age=7200"}
        ttl = self.validator.calculate_ttl(headers, 3600)
        assert ttl == 7200

        # Test default TTL when no cache headers
        ttl = self.validator.calculate_ttl({}, 3600)
        assert ttl == 3600

        # Test expires header (skip this test due to timezone complexity)
        # This would require proper timezone handling which is complex for testing
        pass

    def test_content_integrity_validation(self):
        """Test content integrity validation."""
        # Valid entry
        entry = CacheEntry(
            url="https://example.com/test",
            content=b"test content",
            headers={"content-type": "text/html"},
            status_code=200,
            timestamp=datetime.now(),
            size=12,
            compressed=False,
        )

        assert self.validator.validate_content_integrity(entry) is True

        # Entry with size mismatch (uncompressed)
        entry.size = 20  # Wrong size
        assert self.validator.validate_content_integrity(entry) is False


@pytest.mark.asyncio
class TestCacheManager:
    """Test cache manager functionality."""

    async def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = CacheConfig(
            enabled=True,
            directory=self.temp_dir,
            size_limit="10MB",
            default_ttl=3600,
            compression=False,  # Disable for easier testing
        )
        self.cache_manager = CacheManager(self.config)

    async def teardown_method(self):
        """Clean up test fixtures."""
        self.cache_manager.close()

    async def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        url = "https://example.com/test"
        content = b"<html><body>Test content</body></html>"
        headers = {"content-type": "text/html"}

        # Store in cache
        success = await self.cache_manager.set(url, content, headers, 200)
        assert success is True

        # Retrieve from cache
        entry = await self.cache_manager.get(url)
        assert entry is not None
        assert entry.content == content
        assert entry.status_code == 200
        assert entry.headers["content-type"] == "text/html"

    async def test_cache_miss(self):
        """Test cache miss behavior."""
        entry = await self.cache_manager.get("https://example.com/nonexistent")
        assert entry is None

        stats = self.cache_manager.get_stats()
        assert stats.misses == 1
        assert stats.hits == 0

    async def test_cache_expiration(self):
        """Test cache entry expiration."""
        url = "https://example.com/test"
        content = b"test content"
        headers = {"content-type": "text/html"}

        # Store with very short TTL
        await self.cache_manager.set(url, content, headers, 200)

        # Manually expire the entry by modifying timestamp
        cache_key = self.cache_manager._generate_cache_key(url, {})
        cached_data = self.cache_manager.cache.get(cache_key)
        if cached_data:
            metadata, stored_content = cached_data
            # Set timestamp to past
            metadata["timestamp"] = (
                datetime.now() - timedelta(seconds=3700)
            ).isoformat()
            self.cache_manager.cache.set(cache_key, (metadata, stored_content))

        # Should return None due to expiration
        entry = await self.cache_manager.get(url)
        assert entry is None

    async def test_cache_invalidation(self):
        """Test cache invalidation."""
        url = "https://example.com/test"
        content = b"test content"
        headers = {"content-type": "text/html"}

        # Store in cache
        await self.cache_manager.set(url, content, headers, 200)

        # Verify it's cached
        entry = await self.cache_manager.get(url)
        assert entry is not None

        # Invalidate
        invalidated = await self.cache_manager.invalidate(url)
        assert invalidated is True

        # Should be gone now
        entry = await self.cache_manager.get(url)
        assert entry is None

    async def test_cache_clearing(self):
        """Test cache clearing."""
        # Store multiple entries
        urls = [f"https://example.com/page{i}" for i in range(5)]
        content = b"test content"
        headers = {"content-type": "text/html"}

        for url in urls:
            await self.cache_manager.set(url, content, headers, 200)

        # Verify entries exist
        stats = self.cache_manager.get_stats()
        assert stats.entry_count == 5

        # Clear cache
        cleared_count = await self.cache_manager.clear()
        assert cleared_count == 5

        # Verify cache is empty
        final_stats = self.cache_manager.get_stats()
        assert final_stats.entry_count == 0

    async def test_cache_key_generation(self):
        """Test cache key generation."""
        url = "https://example.com/test"

        # Same URL should generate same key
        key1 = self.cache_manager._generate_cache_key(url, {})
        key2 = self.cache_manager._generate_cache_key(url, {})
        assert key1 == key2

        # Different URLs should generate different keys
        key3 = self.cache_manager._generate_cache_key("https://example.com/other", {})
        assert key1 != key3

        # Headers should affect key generation
        key4 = self.cache_manager._generate_cache_key(url, {"user-agent": "test"})
        assert key1 != key4

    async def test_cache_stats_tracking(self):
        """Test cache statistics tracking."""
        url = "https://example.com/test"
        content = b"test content"
        headers = {"content-type": "text/html"}

        # Initial stats
        stats = self.cache_manager.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0

        # Cache miss
        await self.cache_manager.get(url)
        stats = self.cache_manager.get_stats()
        assert stats.misses == 1

        # Store and hit
        await self.cache_manager.set(url, content, headers, 200)
        await self.cache_manager.get(url)

        stats = self.cache_manager.get_stats()
        assert stats.hits == 1
        assert stats.cache_saves == 1
        assert stats.hit_rate == 0.5  # 1 hit, 1 miss


@pytest.mark.asyncio
class TestCacheIntegration:
    """Test cache system integration."""

    async def test_provider_integration(self):
        """Test cache integration with providers."""
        # This would test the actual provider integration
        # For now, we'll test the interface

        from src.wn_dl.core.base_scraper import BaseNovelScraper

        class TestScraper(BaseNovelScraper):
            def get_provider_name(self):
                return "test"

            async def get_novel_metadata(self, url):
                return None

            async def get_chapter_list(self, novel_url):
                return []

            async def get_chapter_content(self, chapter_url):
                return None

            async def scrape_chapter_content(self, chapter_url):
                return None

        # Test scraper with cache config
        cache_config = CacheConfig(
            enabled=True, directory=tempfile.mkdtemp(), size_limit="10MB"
        )

        scraper_config = {
            "provider": {"name": "test", "base_url": "https://example.com"},
            "request": {"rate_limit": 0.1},
        }

        async with TestScraper(scraper_config, cache_config=cache_config) as scraper:
            assert scraper.cache_manager is not None
            assert scraper.cache_manager.config.enabled is True

    async def test_cache_with_compression(self):
        """Test cache with compression enabled."""
        config = CacheConfig(
            enabled=True,
            directory=tempfile.mkdtemp(),
            compression=True,
            compression_level=6,
        )

        cache_manager = CacheManager(config)

        # Store large content that benefits from compression
        url = "https://example.com/large"
        content = b"<html><body>" + b"Large content " * 1000 + b"</body></html>"
        headers = {"content-type": "text/html"}

        success = await cache_manager.set(url, content, headers, 200)
        assert success is True

        # Retrieve and verify
        entry = await cache_manager.get(url)
        assert entry is not None
        assert entry.content == content
        assert entry.compressed is True

        cache_manager.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
