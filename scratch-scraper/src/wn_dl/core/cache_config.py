"""
Cache configuration classes and utilities.

This module defines the configuration schema for the web scraping cache system,
including validation, parsing, and default values.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


def parse_size_string(size_str: Union[str, int]) -> int:
    """
    Parse size string with units (KB, MB, GB, TB) to bytes.
    
    Args:
        size_str: Size string like "1GB", "500MB" or integer bytes
        
    Returns:
        Size in bytes
        
    Raises:
        ValueError: If size string format is invalid
    """
    if isinstance(size_str, int):
        return size_str
    
    if not isinstance(size_str, str):
        raise ValueError(f"Size must be string or int, got {type(size_str)}")
    
    size_str = size_str.strip().upper()
    
    # Match number and optional unit
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")
    
    number, unit = match.groups()
    number = float(number)
    
    # Convert to bytes
    multipliers = {
        '': 1,
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
    }
    
    if unit not in multipliers:
        raise ValueError(f"Unknown size unit: {unit}")
    
    return int(number * multipliers[unit])


@dataclass
class ProviderCacheConfig:
    """Cache configuration for a specific provider."""
    
    enabled: bool = True
    ttl: Optional[int] = None  # Override default TTL
    size_limit: Optional[str] = None  # Override size limit
    cache_ajax: bool = True  # Cache AJAX responses
    cache_errors: Optional[bool] = None  # Override error caching
    ignore_query_params: List[str] = field(default_factory=list)
    
    def get_ttl(self, default_ttl: int) -> int:
        """Get TTL with fallback to default."""
        return self.ttl if self.ttl is not None else default_ttl
    
    def get_size_limit_bytes(self, default_size: int) -> int:
        """Get size limit in bytes with fallback to default."""
        if self.size_limit is None:
            return default_size
        return parse_size_string(self.size_limit)
    
    def should_cache_errors(self, default_cache_errors: bool) -> bool:
        """Get error caching setting with fallback to default."""
        return self.cache_errors if self.cache_errors is not None else default_cache_errors


@dataclass
class CacheConfig:
    """Main cache configuration class."""
    
    # Basic settings
    enabled: bool = True
    directory: Optional[str] = None  # None = default ~/.wn-dl/cache
    
    # Size and storage
    size_limit: str = "1GB"
    compression: bool = True
    compression_level: int = 6
    
    # Time-based settings
    default_ttl: int = 3600  # 1 hour
    max_ttl: int = 86400  # 24 hours
    min_ttl: int = 300  # 5 minutes
    
    # HTTP validation
    respect_cache_headers: bool = True
    validate_etag: bool = True
    validate_last_modified: bool = True
    conditional_requests: bool = True
    
    # Cache behavior
    cache_errors: bool = False
    cache_redirects: bool = True
    ignore_query_params: List[str] = field(default_factory=list)
    
    # Cleanup and maintenance
    auto_cleanup: bool = True
    cleanup_interval: int = 3600  # 1 hour
    max_entries: int = 10000
    
    # Per-provider settings
    providers: Dict[str, ProviderCacheConfig] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()
        self._normalize_providers()
    
    def _validate_config(self):
        """Validate configuration values."""
        # Validate compression level
        if not 1 <= self.compression_level <= 9:
            raise ValueError("compression_level must be between 1 and 9")
        
        # Validate TTL values
        if self.default_ttl < 0:
            raise ValueError("default_ttl must be non-negative")
        
        if self.max_ttl < self.min_ttl:
            raise ValueError("max_ttl must be >= min_ttl")
        
        if self.default_ttl > self.max_ttl:
            logger.warning(f"default_ttl ({self.default_ttl}) > max_ttl ({self.max_ttl}), clamping")
            self.default_ttl = self.max_ttl
        
        if self.default_ttl < self.min_ttl:
            logger.warning(f"default_ttl ({self.default_ttl}) < min_ttl ({self.min_ttl}), clamping")
            self.default_ttl = self.min_ttl
        
        # Validate size limit
        try:
            self.get_size_limit_bytes()
        except ValueError as e:
            raise ValueError(f"Invalid size_limit: {e}")
        
        # Validate cleanup interval
        if self.cleanup_interval < 60:
            raise ValueError("cleanup_interval must be at least 60 seconds")
        
        # Validate max entries
        if self.max_entries < 100:
            raise ValueError("max_entries must be at least 100")
    
    def _normalize_providers(self):
        """Convert provider dict to ProviderCacheConfig objects."""
        normalized = {}
        for provider_name, config in self.providers.items():
            if isinstance(config, dict):
                normalized[provider_name] = ProviderCacheConfig(**config)
            elif isinstance(config, ProviderCacheConfig):
                normalized[provider_name] = config
            else:
                raise ValueError(f"Invalid provider config for {provider_name}: {type(config)}")
        
        self.providers = normalized
    
    def get_cache_directory(self) -> Path:
        """Get cache directory path with default fallback."""
        if self.directory:
            return Path(self.directory).expanduser()
        
        # Default to ~/.wn-dl/cache
        return Path.home() / ".wn-dl" / "cache"
    
    def get_size_limit_bytes(self) -> int:
        """Get size limit in bytes."""
        return parse_size_string(self.size_limit)
    
    def get_provider_config(self, provider_name: str) -> ProviderCacheConfig:
        """Get provider-specific configuration with defaults."""
        return self.providers.get(provider_name, ProviderCacheConfig())
    
    def is_provider_enabled(self, provider_name: str) -> bool:
        """Check if caching is enabled for a provider."""
        if not self.enabled:
            return False
        
        provider_config = self.get_provider_config(provider_name)
        return provider_config.enabled
    
    def get_provider_ttl(self, provider_name: str) -> int:
        """Get TTL for a specific provider."""
        provider_config = self.get_provider_config(provider_name)
        ttl = provider_config.get_ttl(self.default_ttl)
        
        # Clamp to min/max TTL
        return max(self.min_ttl, min(self.max_ttl, ttl))
    
    def should_cache_errors_for_provider(self, provider_name: str) -> bool:
        """Check if errors should be cached for a provider."""
        provider_config = self.get_provider_config(provider_name)
        return provider_config.should_cache_errors(self.cache_errors)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'CacheConfig':
        """Create CacheConfig from dictionary (e.g., from YAML)."""
        # Handle nested provider configs
        providers = {}
        if 'providers' in config_dict:
            for name, provider_config in config_dict['providers'].items():
                if isinstance(provider_config, dict):
                    providers[name] = ProviderCacheConfig(**provider_config)
                else:
                    providers[name] = provider_config
        
        # Create config with providers
        config_dict = config_dict.copy()
        config_dict['providers'] = providers
        
        return cls(**config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert CacheConfig to dictionary for serialization."""
        result = {}
        
        for field_name, field_value in self.__dict__.items():
            if field_name == 'providers':
                # Convert provider configs to dicts
                result[field_name] = {
                    name: config.__dict__ for name, config in field_value.items()
                }
            else:
                result[field_name] = field_value
        
        return result


def get_default_cache_config() -> CacheConfig:
    """Get default cache configuration."""
    return CacheConfig(
        enabled=True,
        directory=None,  # Use default
        size_limit="1GB",
        compression=True,
        compression_level=6,
        default_ttl=3600,
        max_ttl=86400,
        min_ttl=300,
        respect_cache_headers=True,
        validate_etag=True,
        validate_last_modified=True,
        conditional_requests=True,
        cache_errors=False,
        cache_redirects=True,
        ignore_query_params=[],
        auto_cleanup=True,
        cleanup_interval=3600,
        max_entries=10000,
        providers={
            'novelfull': ProviderCacheConfig(enabled=True, ttl=7200),
            'novelbin': ProviderCacheConfig(enabled=False, ttl=1800),
            'novelbuddy': ProviderCacheConfig(enabled=True, ttl=3600, cache_ajax=True),
            'royalroad': ProviderCacheConfig(enabled=True, ttl=14400),
            'wuxiaworld': ProviderCacheConfig(enabled=True, ttl=10800),
        }
    )
