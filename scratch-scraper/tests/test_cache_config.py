"""
Tests for cache configuration classes and utilities.
"""

import pytest
from pathlib import Path
from src.wn_dl.core.cache_config import (
    CacheConfig,
    ProviderCacheConfig,
    parse_size_string,
    get_default_cache_config
)


class TestParseSizeString:
    """Test size string parsing utility."""
    
    def test_parse_bytes(self):
        """Test parsing byte values."""
        assert parse_size_string(1024) == 1024
        assert parse_size_string("1024") == 1024
        assert parse_size_string("1024B") == 1024
    
    def test_parse_kilobytes(self):
        """Test parsing kilobyte values."""
        assert parse_size_string("1KB") == 1024
        assert parse_size_string("2KB") == 2048
        assert parse_size_string("1.5KB") == 1536
    
    def test_parse_megabytes(self):
        """Test parsing megabyte values."""
        assert parse_size_string("1MB") == 1024 * 1024
        assert parse_size_string("2.5MB") == int(2.5 * 1024 * 1024)
    
    def test_parse_gigabytes(self):
        """Test parsing gigabyte values."""
        assert parse_size_string("1GB") == 1024 ** 3
        assert parse_size_string("0.5GB") == int(0.5 * 1024 ** 3)
    
    def test_parse_terabytes(self):
        """Test parsing terabyte values."""
        assert parse_size_string("1TB") == 1024 ** 4
    
    def test_case_insensitive(self):
        """Test case insensitive parsing."""
        assert parse_size_string("1gb") == 1024 ** 3
        assert parse_size_string("1Gb") == 1024 ** 3
        assert parse_size_string("1GB") == 1024 ** 3
    
    def test_whitespace_handling(self):
        """Test whitespace handling."""
        assert parse_size_string(" 1GB ") == 1024 ** 3
        assert parse_size_string("1 GB") == 1024 ** 3
        assert parse_size_string("1  GB  ") == 1024 ** 3
    
    def test_invalid_formats(self):
        """Test invalid format handling."""
        with pytest.raises(ValueError):
            parse_size_string("invalid")
        
        with pytest.raises(ValueError):
            parse_size_string("1XB")
        
        with pytest.raises(ValueError):
            parse_size_string("")
        
        with pytest.raises(ValueError):
            parse_size_string("GB")


class TestProviderCacheConfig:
    """Test provider-specific cache configuration."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = ProviderCacheConfig()
        assert config.enabled is True
        assert config.ttl is None
        assert config.size_limit is None
        assert config.cache_ajax is True
        assert config.cache_errors is None
        assert config.ignore_query_params == []
    
    def test_get_ttl_with_override(self):
        """Test TTL with provider override."""
        config = ProviderCacheConfig(ttl=7200)
        assert config.get_ttl(3600) == 7200
    
    def test_get_ttl_with_default(self):
        """Test TTL with default fallback."""
        config = ProviderCacheConfig()
        assert config.get_ttl(3600) == 3600
    
    def test_get_size_limit_with_override(self):
        """Test size limit with provider override."""
        config = ProviderCacheConfig(size_limit="500MB")
        expected = 500 * 1024 * 1024
        assert config.get_size_limit_bytes(1024) == expected
    
    def test_get_size_limit_with_default(self):
        """Test size limit with default fallback."""
        config = ProviderCacheConfig()
        assert config.get_size_limit_bytes(1024) == 1024
    
    def test_should_cache_errors_with_override(self):
        """Test error caching with provider override."""
        config = ProviderCacheConfig(cache_errors=True)
        assert config.should_cache_errors(False) is True
    
    def test_should_cache_errors_with_default(self):
        """Test error caching with default fallback."""
        config = ProviderCacheConfig()
        assert config.should_cache_errors(False) is False


class TestCacheConfig:
    """Test main cache configuration."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = CacheConfig()
        assert config.enabled is True
        assert config.directory is None
        assert config.size_limit == "1GB"
        assert config.compression is True
        assert config.compression_level == 6
        assert config.default_ttl == 3600
        assert config.max_ttl == 86400
        assert config.min_ttl == 300
    
    def test_get_cache_directory_default(self):
        """Test default cache directory."""
        config = CacheConfig()
        expected = Path.home() / ".wn-dl" / "cache"
        assert config.get_cache_directory() == expected
    
    def test_get_cache_directory_custom(self):
        """Test custom cache directory."""
        config = CacheConfig(directory="/tmp/cache")
        assert config.get_cache_directory() == Path("/tmp/cache")
    
    def test_get_cache_directory_expanduser(self):
        """Test cache directory with user expansion."""
        config = CacheConfig(directory="~/cache")
        expected = Path.home() / "cache"
        assert config.get_cache_directory() == expected
    
    def test_get_size_limit_bytes(self):
        """Test size limit conversion to bytes."""
        config = CacheConfig(size_limit="2GB")
        expected = 2 * 1024 ** 3
        assert config.get_size_limit_bytes() == expected
    
    def test_get_provider_config_existing(self):
        """Test getting existing provider configuration."""
        provider_config = ProviderCacheConfig(ttl=7200)
        config = CacheConfig(providers={"test": provider_config})
        
        result = config.get_provider_config("test")
        assert result.ttl == 7200
    
    def test_get_provider_config_default(self):
        """Test getting default provider configuration."""
        config = CacheConfig()
        result = config.get_provider_config("nonexistent")
        assert isinstance(result, ProviderCacheConfig)
        assert result.enabled is True
    
    def test_is_provider_enabled_global_disabled(self):
        """Test provider enabled check with global cache disabled."""
        config = CacheConfig(enabled=False)
        assert config.is_provider_enabled("test") is False
    
    def test_is_provider_enabled_provider_disabled(self):
        """Test provider enabled check with provider disabled."""
        provider_config = ProviderCacheConfig(enabled=False)
        config = CacheConfig(providers={"test": provider_config})
        assert config.is_provider_enabled("test") is False
    
    def test_is_provider_enabled_both_enabled(self):
        """Test provider enabled check with both enabled."""
        provider_config = ProviderCacheConfig(enabled=True)
        config = CacheConfig(enabled=True, providers={"test": provider_config})
        assert config.is_provider_enabled("test") is True
    
    def test_get_provider_ttl_with_clamping(self):
        """Test provider TTL with min/max clamping."""
        # TTL too high
        provider_config = ProviderCacheConfig(ttl=100000)
        config = CacheConfig(max_ttl=86400, providers={"test": provider_config})
        assert config.get_provider_ttl("test") == 86400
        
        # TTL too low
        provider_config = ProviderCacheConfig(ttl=100)
        config = CacheConfig(min_ttl=300, providers={"test": provider_config})
        assert config.get_provider_ttl("test") == 300
    
    def test_validation_compression_level(self):
        """Test compression level validation."""
        with pytest.raises(ValueError, match="compression_level must be between 1 and 9"):
            CacheConfig(compression_level=0)
        
        with pytest.raises(ValueError, match="compression_level must be between 1 and 9"):
            CacheConfig(compression_level=10)
    
    def test_validation_ttl_values(self):
        """Test TTL validation."""
        with pytest.raises(ValueError, match="default_ttl must be non-negative"):
            CacheConfig(default_ttl=-1)
        
        with pytest.raises(ValueError, match="max_ttl must be >= min_ttl"):
            CacheConfig(min_ttl=1000, max_ttl=500)
    
    def test_validation_size_limit(self):
        """Test size limit validation."""
        with pytest.raises(ValueError, match="Invalid size_limit"):
            CacheConfig(size_limit="invalid")
    
    def test_validation_cleanup_interval(self):
        """Test cleanup interval validation."""
        with pytest.raises(ValueError, match="cleanup_interval must be at least 60 seconds"):
            CacheConfig(cleanup_interval=30)
    
    def test_validation_max_entries(self):
        """Test max entries validation."""
        with pytest.raises(ValueError, match="max_entries must be at least 100"):
            CacheConfig(max_entries=50)
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "enabled": True,
            "size_limit": "2GB",
            "default_ttl": 7200,
            "providers": {
                "test": {
                    "enabled": True,
                    "ttl": 3600
                }
            }
        }
        
        config = CacheConfig.from_dict(config_dict)
        assert config.enabled is True
        assert config.size_limit == "2GB"
        assert config.default_ttl == 7200
        assert "test" in config.providers
        assert config.providers["test"].ttl == 3600
    
    def test_to_dict(self):
        """Test converting config to dictionary."""
        provider_config = ProviderCacheConfig(ttl=7200)
        config = CacheConfig(
            enabled=True,
            size_limit="2GB",
            providers={"test": provider_config}
        )
        
        result = config.to_dict()
        assert result["enabled"] is True
        assert result["size_limit"] == "2GB"
        assert "test" in result["providers"]
        assert result["providers"]["test"]["ttl"] == 7200


class TestDefaultCacheConfig:
    """Test default cache configuration."""
    
    def test_get_default_config(self):
        """Test getting default configuration."""
        config = get_default_cache_config()
        
        assert isinstance(config, CacheConfig)
        assert config.enabled is True
        assert config.size_limit == "1GB"
        assert config.default_ttl == 3600
        
        # Check default providers
        assert "novelfull" in config.providers
        assert "novelbin" in config.providers
        assert "novelbuddy" in config.providers
        assert "royalroad" in config.providers
        assert "wuxiaworld" in config.providers
        
        # Check provider-specific settings
        assert config.providers["novelfull"].ttl == 7200
        assert config.providers["novelbin"].enabled is False
        assert config.providers["novelbuddy"].cache_ajax is True
