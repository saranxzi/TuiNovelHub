# Web Novel Scraper Cache System

## Overview

The Web Novel Scraper includes a sophisticated HTTP response caching system designed to improve performance, reduce server load, and provide offline capabilities. The cache system supports compression, TTL-based expiration, HTTP cache validation, and provider-specific configurations.

## Features

### Core Features
- **HTTP Response Caching**: Automatic caching of web pages and API responses
- **Compression**: Optional gzip compression to reduce storage space
- **TTL Management**: Configurable time-to-live for cache entries
- **Cache Validation**: ETag and Last-Modified header support for conditional requests
- **Provider-Specific Settings**: Different cache configurations per scraping provider
- **Metrics and Monitoring**: Comprehensive statistics and performance tracking
- **CLI Management**: Command-line tools for cache administration

### Advanced Features
- **Content Integrity Validation**: Automatic detection of corrupted cache entries
- **Size Limits**: Configurable cache size limits with LRU eviction
- **Conditional Requests**: HTTP 304 Not Modified support for bandwidth savings
- **Error Handling**: Robust error recovery and logging
- **Performance Monitoring**: Detailed timing and efficiency metrics

## Architecture

### Components

1. **CacheConfig**: Configuration management for cache settings
2. **CacheManager**: Main cache interface for storing and retrieving responses
3. **CacheValidator**: HTTP cache validation and content integrity checking
4. **CacheEntry**: Data structure representing cached HTTP responses
5. **CacheStats**: Metrics collection and performance tracking

### Storage Backend

The cache system uses [DiskCache](https://grantjenks.com/docs/diskcache/) as the storage backend, providing:
- Persistent storage across application restarts
- Atomic operations for thread safety
- LRU eviction policy for size management
- Cross-platform compatibility

## Configuration

### Basic Configuration

Cache settings are managed through the user configuration system:

```yaml
cache:
  enabled: true
  directory: ~/.wn-dl/cache
  size_limit: 1GB
  compression: true
  compression_level: 6
  default_ttl: 3600  # 1 hour
  max_ttl: 86400     # 24 hours
  min_ttl: 300       # 5 minutes
```

### HTTP Cache Headers

```yaml
cache:
  respect_cache_headers: true
  validate_etag: true
  validate_last_modified: true
  conditional_requests: true
  cache_errors: false
  cache_redirects: true
```

### Provider-Specific Settings

```yaml
cache:
  providers:
    novelfull:
      enabled: true
      ttl: 7200  # 2 hours
      cache_ajax: false
    novelbin:
      enabled: false  # Disable for rate-limited providers
    novelbuddy:
      enabled: true
      ttl: 3600
      cache_ajax: true
```

## Usage

### Programmatic Usage

```python
from wn_dl.core.cache_config import CacheConfig
from wn_dl.core.cache_manager import CacheManager

# Create cache configuration
config = CacheConfig(
    enabled=True,
    size_limit="500MB",
    default_ttl=3600,
    compression=True
)

# Initialize cache manager
async with CacheManager(config) as cache:
    # Store response
    await cache.set(
        url="https://example.com/page",
        content=b"<html>...</html>",
        headers={"content-type": "text/html"},
        status_code=200
    )
    
    # Retrieve response
    entry = await cache.get("https://example.com/page")
    if entry:
        print(f"Cached content: {entry.content}")
```

### Integration with Scrapers

The cache system is automatically integrated with all scrapers:

```python
from wn_dl.providers import get_scraper_for_url
from wn_dl.core.cache_config import get_default_cache_config

# Cache is automatically used when available
cache_config = get_default_cache_config()
scraper = get_scraper_for_url(url, provider_config, cache_config)

async with scraper:
    # All HTTP requests will use cache when possible
    metadata = await scraper.get_novel_metadata(novel_url)
```

## CLI Commands

### Cache Status

View current cache statistics and configuration:

```bash
# Table format (default)
wn-dl cache status

# JSON format
wn-dl cache status --format json
```

### Cache Configuration

View cache configuration:

```bash
# Full configuration
wn-dl cache config

# Provider-specific configuration
wn-dl cache config --provider novelfull
```

### Cache Management

Clear cache entries:

```bash
# Clear all cache entries
wn-dl cache clear

# Clear entries matching pattern
wn-dl cache clear --pattern "novelbin.com"

# Skip confirmation prompt
wn-dl cache clear --confirm
```

## Performance Benefits

### Bandwidth Savings
- Reduces HTTP requests by serving cached responses
- Supports HTTP 304 Not Modified for conditional requests
- Compression reduces storage and transfer overhead

### Speed Improvements
- Eliminates network latency for cached content
- Faster chapter downloads for previously scraped novels
- Reduced server load and rate limiting issues

### Offline Capabilities
- Cached content remains available without internet connection
- Partial novel downloads can be resumed from cache
- Metadata and chapter lists persist across sessions

## Monitoring and Metrics

### Available Metrics

The cache system tracks comprehensive performance metrics:

- **Hit/Miss Ratios**: Cache effectiveness measurement
- **Response Times**: Average cache lookup and storage times
- **Storage Efficiency**: Compression ratios and space usage
- **Validation Success**: HTTP cache validation statistics
- **Error Rates**: Cache operation failure tracking

### Accessing Metrics

```python
# Get current statistics
stats = cache_manager.get_stats()

print(f"Hit Rate: {stats.hit_rate:.1%}")
print(f"Average Cache Time: {stats.average_cache_time * 1000:.2f}ms")
print(f"Compression Ratio: {stats.compression_ratio:.2f}")
print(f"Bytes Saved: {stats.bytes_saved / (1024**2):.1f} MB")
```

## Best Practices

### Configuration Recommendations

1. **Enable Compression**: Reduces storage space by 60-80% for HTML content
2. **Set Appropriate TTL**: Balance between freshness and performance
3. **Provider-Specific Settings**: Disable cache for rate-limited providers
4. **Size Limits**: Set reasonable limits based on available disk space

### Performance Optimization

1. **Cache Warm-up**: Pre-populate cache with frequently accessed content
2. **Selective Caching**: Disable cache for dynamic or personalized content
3. **Regular Cleanup**: Use cache clear commands to remove stale entries
4. **Monitor Metrics**: Track hit rates and adjust configuration accordingly

### Troubleshooting

Common issues and solutions:

1. **Low Hit Rates**: Check TTL settings and cache validation configuration
2. **Storage Issues**: Verify disk space and size limit settings
3. **Stale Content**: Ensure cache validation is enabled for dynamic sites
4. **Performance Issues**: Monitor cache operation times and consider disabling compression

## Security Considerations

### Data Privacy
- Cache stores HTTP responses locally
- Sensitive content should use appropriate TTL settings
- Consider cache encryption for sensitive data

### Access Control
- Cache directory should have appropriate file permissions
- Shared systems should use user-specific cache directories
- Regular cache cleanup prevents data accumulation

## Advanced Topics

### Custom Cache Validation

Implement custom validation logic:

```python
from wn_dl.core.cache_validator import CacheValidator

class CustomValidator(CacheValidator):
    def should_cache_response(self, status_code, headers):
        # Custom caching logic
        if 'no-store' in headers.get('cache-control', ''):
            return False
        return super().should_cache_response(status_code, headers)
```

### Cache Debugging

Enable detailed cache logging:

```python
import logging
logging.getLogger('wn_dl.core.cache_manager').setLevel(logging.DEBUG)
```

### Performance Tuning

Optimize cache performance:

```yaml
cache:
  compression_level: 1  # Faster compression
  auto_cleanup: false   # Disable automatic cleanup
  max_entries: 50000    # Increase entry limit
```

## Migration and Maintenance

### Cache Migration

When upgrading cache system versions:

1. Export important cache entries
2. Clear old cache directory
3. Reconfigure with new settings
4. Re-populate critical content

### Regular Maintenance

Recommended maintenance tasks:

1. **Weekly**: Review cache statistics and hit rates
2. **Monthly**: Clear expired or unused cache entries
3. **Quarterly**: Analyze storage usage and adjust size limits
4. **Annually**: Review and update cache configuration

## API Reference

For detailed API documentation, see:
- [CacheConfig API](api/cache_config.md)
- [CacheManager API](api/cache_manager.md)
- [CacheValidator API](api/cache_validator.md)
