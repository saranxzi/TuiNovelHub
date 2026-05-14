# Cache System Quick Reference

## Essential Commands

### Check Cache Status
```bash
wn-dl cache status                    # View cache statistics
wn-dl cache status --format json     # JSON output
```

### Manage Cache
```bash
wn-dl cache clear                     # Clear all cache
wn-dl cache clear --pattern "domain"  # Clear specific domain
wn-dl cache config                    # View configuration
```

## Configuration Quick Setup

### Enable Cache (User Config)
```yaml
# ~/.wn-dl/config.yaml
cache:
  enabled: true
  size_limit: 1GB
  compression: true
  default_ttl: 3600
```

### Provider-Specific Settings
```yaml
cache:
  providers:
    novelfull:
      enabled: true
      ttl: 7200
    novelbin:
      enabled: false  # Disable for rate-limited sites
```

## Common Use Cases

### High-Performance Setup
```yaml
cache:
  enabled: true
  size_limit: 5GB
  compression: true
  compression_level: 1  # Fast compression
  default_ttl: 14400    # 4 hours
```

### Conservative Setup
```yaml
cache:
  enabled: true
  size_limit: 500MB
  compression: true
  default_ttl: 1800     # 30 minutes
  respect_cache_headers: true
```

### Development Setup
```yaml
cache:
  enabled: true
  size_limit: 100MB
  compression: false
  default_ttl: 300      # 5 minutes
```

## Troubleshooting

### Low Hit Rate
1. Check TTL settings: `wn-dl cache config`
2. Verify provider settings are enabled
3. Monitor with: `wn-dl cache status`

### Storage Issues
1. Check disk space: `df -h`
2. Clear cache: `wn-dl cache clear`
3. Reduce size limit in config

### Performance Issues
1. Disable compression for speed
2. Increase cache size limit
3. Check average cache times in status

## Key Metrics

| Metric | Good Value | Action if Poor |
|--------|------------|----------------|
| Hit Rate | >60% | Check TTL, enable cache for more providers |
| Avg Cache Time | <10ms | Reduce compression level, check disk speed |
| Compression Ratio | 0.3-0.7 | Enable compression, check content types |
| Cache Errors | 0 | Check disk space, permissions |

## Provider Recommendations

| Provider | Cache Enabled | TTL | Notes |
|----------|---------------|-----|-------|
| NovelFull | ✅ Yes | 2-4 hours | Stable content |
| NovelBin | ❌ No | - | Rate limited |
| NovelBuddy | ✅ Yes | 1-2 hours | AJAX content |
| RoyalRoad | ✅ Yes | 4-8 hours | Stable content |

## Emergency Commands

### Clear All Cache
```bash
wn-dl cache clear --confirm
```

### Disable Cache Temporarily
```bash
# Edit config to set enabled: false
# Or use environment variable
export WN_DL_CACHE_ENABLED=false
```

### Check Cache Directory Size
```bash
du -sh ~/.wn-dl/cache
```

## Performance Tips

1. **Enable compression** for 60-80% space savings
2. **Set appropriate TTL** based on content update frequency
3. **Monitor hit rates** and adjust provider settings
4. **Use selective clearing** instead of full cache clears
5. **Regular maintenance** prevents cache bloat

## Integration Examples

### Basic Scraper Usage
```python
# Cache is automatically used
scraper = get_scraper_for_url(url, config, cache_config)
```

### Manual Cache Operations
```python
cache_manager = CacheManager(cache_config)
await cache_manager.set(url, content, headers, 200)
entry = await cache_manager.get(url)
```

### Custom Validation
```python
validator = CacheValidator(cache_config)
should_cache = validator.should_cache_response(200, headers)
```
