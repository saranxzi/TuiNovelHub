# NovelFire Provider

The NovelFire provider enables scraping novels from [NovelFire](https://novelfire.net), a popular web fiction platform that hosts a wide variety of novels with paginated chapter lists.

## Features

- **Complete metadata extraction**: Title, author, description, cover image, genres, rating, and status
- **Paginated chapter discovery**: Automatically handles multiple pages of chapter lists
- **High-quality content extraction**: Uses markdownify for better HTML to markdown conversion
- **Robust error handling**: Circuit breaker, retry logic, and rate limiting
- **Concurrent processing**: Optimized for fast chapter downloads while respecting server limits

## Supported URLs

The NovelFire provider supports the following URL patterns:

- `https://novelfire.net/book/novel-name`
- `https://www.novelfire.net/book/novel-name`
- `https://novelfire.net/book/novel-name/chapters` (chapter list pages)
- `https://novelfire.net/book/novel-name/chapter-X` (individual chapters)

## Configuration

The provider is configured via `config/novelfire-provider.yaml` with the following key settings:

### Rate Limiting
- **Request rate**: 2.0 seconds between requests (conservative)
- **Concurrent downloads**: 15 workers maximum
- **Chunk processing**: 25 chapters per chunk with 1.5s delay

### Content Processing
- **Markdownify integration**: Enabled for better HTML to markdown conversion
- **Ad removal**: Comprehensive selectors for removing ads and unwanted content
- **Text processing**: Quote normalization, whitespace cleanup, and character validation

### Pagination Handling
- **Automatic discovery**: Detects and processes all chapter list pages
- **Safety limits**: Maximum 100 pages to prevent infinite loops
- **Smart navigation**: Uses pagination selectors to find next pages

## Usage Examples

### Basic Novel Scraping

```bash
# Scrape a complete novel
wn-dl scrape --url "https://novelfire.net/book/the-perfect-run"

# Scrape with specific output directory
wn-dl scrape --url "https://novelfire.net/book/the-perfect-run" --output my_novels

# Generate both markdown and EPUB
wn-dl scrape --url "https://novelfire.net/book/the-perfect-run" --format markdown epub
```

### Advanced Options

```bash
# Use verbose logging to see pagination progress
wn-dl --with-info scrape --url "https://novelfire.net/book/the-perfect-run"

# Force EbookLib for EPUB generation (if Pandoc has issues)
wn-dl scrape --url "https://novelfire.net/book/the-perfect-run" --use-ebooklib

# Scrape with custom concurrency settings
wn-dl scrape --url "https://novelfire.net/book/the-perfect-run" --max-workers 10
```

### Batch Processing

```bash
# Create a file with multiple NovelFire URLs
echo "https://novelfire.net/book/novel-1" > novelfire_list.txt
echo "https://novelfire.net/book/novel-2" >> novelfire_list.txt

# Batch scrape all novels
wn-dl scrape --files novelfire_list.txt
```

## Provider-Specific Features

### Pagination Handling

NovelFire uses paginated chapter lists, which the provider handles automatically:

1. **Chapter Discovery**: Starts from the main novel page
2. **Pagination Detection**: Finds the chapters URL (`/book/novel-name/chapters`)
3. **Page Processing**: Iterates through all pages using `?page=N` parameters
4. **Chapter Extraction**: Collects all chapter links and metadata
5. **Concurrent Download**: Downloads chapters in optimized chunks

### Content Quality

The provider includes several features for high-quality content extraction:

- **Markdownify Integration**: Converts HTML to clean markdown format
- **Ad Removal**: Removes ads, donation boxes, and navigation elements
- **Text Processing**: Normalizes quotes, fixes character encoding issues
- **Title Enhancement**: Extracts better chapter titles from content when available

### Error Handling

Robust error handling includes:

- **Circuit Breaker**: Stops requests after consecutive failures
- **Adaptive Rate Limiting**: Adjusts request rate based on server response
- **Retry Logic**: Automatically retries failed requests
- **Graceful Degradation**: Continues processing even if some chapters fail

## Performance Characteristics

### Typical Performance
- **Small novels** (50-100 chapters): 30-60 seconds
- **Medium novels** (100-300 chapters): 1-3 minutes  
- **Large novels** (300+ chapters): 3-8 minutes

### Optimization Settings
- **Concurrent workers**: 15 (balanced for NovelFire's capacity)
- **Chunk size**: 25 chapters (optimal for memory usage)
- **Rate limiting**: 2.0s between requests (respectful to server)
- **Pagination delay**: 1.0s between page requests

## Troubleshooting

### Common Issues

**Slow scraping performance:**
```bash
# Increase concurrency (use with caution)
wn-dl scrape --url "URL" --max-workers 20
```

**EPUB generation failures:**
```bash
# Use EbookLib as fallback
wn-dl scrape --url "URL" --use-ebooklib
```

**Rate limiting errors:**
```bash
# Use more conservative settings
wn-dl scrape --url "URL" --max-workers 5
```

### Debug Mode

Enable verbose logging to see detailed progress:

```bash
wn-dl --with-info scrape --url "https://novelfire.net/book/novel-name"
```

This will show:
- Pagination discovery progress
- Chapter extraction details
- Rate limiting information
- Error details and retry attempts

## Technical Details

### HTML Structure

NovelFire uses the following key HTML structure:

- **Novel metadata**: `.novel-title`, `.author`, `.summary .content`
- **Chapter lists**: `ul.chapter-list li a` with `.chapter-title` and `.chapter-no`
- **Pagination**: `.pagination .page-item a.page-link`
- **Chapter content**: `#content.clearfix`

### Content Cleaning

The provider removes these unwanted elements:
- Advertisement containers (`.ads`, `.advertisement`, etc.)
- Navigation elements (`.chapter-nav`, `.breadcrumb`)
- Social sharing buttons (`.share-buttons`, `.social-links`)
- Donation/support boxes (`.donation`, `.patreon`)
- Comments sections (`.comments`, `.comment-section`)

### Rate Limiting Strategy

NovelFire provider uses adaptive rate limiting:
1. **Base rate**: 2.0 seconds between requests
2. **Adaptive adjustment**: Increases delay on errors
3. **Burst protection**: Limits concurrent requests
4. **Circuit breaker**: Stops on consecutive failures

## Best Practices

1. **Respect rate limits**: Don't increase concurrency too aggressively
2. **Use batch processing**: For multiple novels, use the `--files` option
3. **Monitor progress**: Use `--with-info` for long-running scrapes
4. **Handle failures gracefully**: Check logs for failed chapters
5. **Test with small novels**: Verify settings before scraping large works

## Integration Notes

The NovelFire provider integrates seamlessly with all wn-dl features:

- **Font selection**: Works with all configured fonts (Bookerly, Bitter, Literata, etc.)
- **EPUB generation**: Supports both Pandoc and EbookLib backends
- **User configuration**: Respects all user preferences and settings
- **Batch processing**: Compatible with multi-URL processing
- **Progress tracking**: Shows real-time progress with chapter counts

For more information about general usage, see the [main documentation](../README.md).
