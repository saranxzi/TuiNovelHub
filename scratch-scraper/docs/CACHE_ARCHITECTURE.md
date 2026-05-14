# Web Scraping Cache Architecture

## Overview

This document outlines the architecture for implementing a high-performance, configurable caching system for web scraping operations in the wn-dl project.

## Design Goals

1. **Performance**: Sub-millisecond cache hits, minimal overhead on cache misses
2. **Reliability**: Persistent storage, crash-safe operations
3. **Configurability**: Size limits, TTL, per-provider settings
4. **Integration**: Seamless integration with existing aiohttp/cloudscraper setup
5. **Validation**: HTTP cache headers support (ETag, Last-Modified, Cache-Control)
6. **Management**: CLI tools for cache inspection and maintenance

## Architecture Components

### 1. Core Cache Manager

```python
class CacheManager:
    """Main interface for all cache operations."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.backend = HTTPCacheBackend(config)
        self.validator = CacheValidator(config)
        self.metrics = CacheMetrics()
    
    async def get(self, url: str, headers: dict = None) -> Optional[CacheEntry]
    async def set(self, url: str, response_data: bytes, headers: dict, status: int)
    async def invalidate(self, url: str)
    async def clear(self, pattern: str = None)
    def get_stats() -> CacheStats
```

### 2. HTTP Cache Backend

```python
class HTTPCacheBackend:
    """HTTP-aware caching backend using diskcache."""
    
    def __init__(self, config: CacheConfig):
        self.cache = diskcache.Cache(
            directory=config.cache_dir,
            size_limit=config.size_limit,
            eviction_policy='least-recently-used'
        )
        self.compression = config.compression
    
    def _generate_key(self, url: str, headers: dict = None) -> str
    def _compress_content(self, content: bytes) -> bytes
    def _decompress_content(self, content: bytes) -> bytes
```

### 3. Cache Entry Model

```python
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
    
    def is_expired(self) -> bool
    def is_stale(self) -> bool
    def needs_validation(self) -> bool
```

### 4. Cache Configuration

```python
@dataclass
class CacheConfig:
    """Cache configuration settings."""
    
    enabled: bool = True
    cache_dir: str = ".cache/wn-dl"
    size_limit: int = 1024 * 1024 * 1024  # 1GB default
    default_ttl: int = 3600  # 1 hour
    max_ttl: int = 86400  # 24 hours
    compression: bool = True
    compression_level: int = 6
    
    # Validation settings
    respect_cache_headers: bool = True
    validate_etag: bool = True
    validate_last_modified: bool = True
    
    # Per-provider overrides
    provider_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
```

## Cache Key Generation

### URL Normalization Strategy

```python
def normalize_url(url: str) -> str:
    """Normalize URL for consistent cache keys."""
    parsed = urlparse(url)
    
    # Remove fragment
    normalized = parsed._replace(fragment='')
    
    # Sort query parameters
    if parsed.query:
        params = sorted(parse_qsl(parsed.query))
        query = urlencode(params)
        normalized = normalized._replace(query=query)
    
    # Convert to lowercase domain
    normalized = normalized._replace(netloc=normalized.netloc.lower())
    
    return urlunparse(normalized)

def generate_cache_key(url: str, headers: dict = None) -> str:
    """Generate cache key from URL and relevant headers."""
    normalized_url = normalize_url(url)
    
    # Include headers that affect response content
    relevant_headers = {}
    if headers:
        for header in ['Accept', 'Accept-Language', 'User-Agent']:
            if header.lower() in headers:
                relevant_headers[header.lower()] = headers[header.lower()]
    
    # Create composite key
    key_data = {
        'url': normalized_url,
        'headers': relevant_headers
    }
    
    # Hash for consistent length
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_string.encode()).hexdigest()
```

## Integration with Base Scraper

### Modified Request Methods

```python
class BaseNovelScraper:
    def __init__(self, config: Dict[str, Any], session: Optional[aiohttp.ClientSession] = None):
        # ... existing initialization ...
        self.cache_manager = CacheManager(self._get_cache_config())
    
    async def _make_request_cached(self, url: str, **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Make HTTP request with caching support."""
        
        # Check cache first
        cache_entry = await self.cache_manager.get(url, kwargs.get('headers'))
        if cache_entry and not cache_entry.needs_validation():
            self.cache_manager.metrics.record_hit()
            return self._create_cached_response(cache_entry)
        
        # Make actual request
        response = await self._make_request(url, **kwargs)
        if response and response.status == 200:
            # Cache the response
            content = await response.read()
            await self.cache_manager.set(
                url=url,
                response_data=content,
                headers=dict(response.headers),
                status=response.status
            )
            self.cache_manager.metrics.record_miss()
        
        return response
```

## Cache Validation

### HTTP Headers Support

```python
class CacheValidator:
    """Handles cache validation using HTTP headers."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
    
    def should_validate(self, entry: CacheEntry) -> bool:
        """Check if cache entry needs validation."""
        if not self.config.respect_cache_headers:
            return entry.is_expired()
        
        # Check Cache-Control headers
        cache_control = entry.headers.get('cache-control', '')
        if 'no-cache' in cache_control:
            return True
        
        # Check expiration
        if entry.expires and datetime.now() > entry.expires:
            return True
        
        # Check max-age
        max_age = self._parse_max_age(cache_control)
        if max_age and (datetime.now() - entry.timestamp).seconds > max_age:
            return True
        
        return False
    
    async def validate_with_server(self, entry: CacheEntry, session) -> bool:
        """Validate cache entry with conditional request."""
        headers = {}
        
        if entry.etag and self.config.validate_etag:
            headers['If-None-Match'] = entry.etag
        
        if entry.last_modified and self.config.validate_last_modified:
            headers['If-Modified-Since'] = entry.last_modified
        
        # Make conditional request
        async with session.head(entry.url, headers=headers) as response:
            return response.status == 304  # Not Modified
```

## Storage Structure

```
cache_dir/
├── diskcache.db         # diskcache SQLite database
├── settings.json        # Cache configuration
├── stats.json          # Cache statistics
└── data/               # Cached content (managed by diskcache)
    ├── 00/
    ├── 01/
    └── ...
```

## Performance Considerations

1. **Key Hashing**: SHA256 for consistent key length and distribution
2. **Compression**: Optional gzip compression for large responses
3. **Size Limits**: Configurable per-cache and per-entry limits
4. **Eviction**: LRU eviction when size limits are reached
5. **Concurrent Access**: Thread-safe operations for parallel scraping

## Configuration Integration

### User Config Template Addition

```yaml
preferences:
  cache:
    enabled: true                    # Enable/disable caching
    directory: "~/.wn-dl/cache"     # Cache directory
    size_limit: "1GB"              # Maximum cache size
    default_ttl: 3600              # Default TTL in seconds
    compression: true               # Enable compression
    
    # Validation settings
    respect_cache_headers: true     # Honor HTTP cache headers
    validate_etag: true            # Use ETag validation
    validate_last_modified: true   # Use Last-Modified validation
    
    # Per-provider settings
    providers:
      novelfull:
        ttl: 7200                  # 2 hours for NovelFull
        enabled: true
      novelbin:
        ttl: 1800                  # 30 minutes for NovelBin
        enabled: false             # Disable for problematic providers
```

## Next Steps

1. Implement core CacheManager class
2. Create HTTPCacheBackend with diskcache
3. Add cache configuration to user preferences
4. Integrate with base scraper methods
5. Add CLI commands for cache management
6. Implement comprehensive testing
7. Add performance monitoring and metrics
