# 🚀 Provider Quick Start Guide

This guide provides quick implementation patterns for common provider types.

## 📋 Provider Types

### 1. Simple HTML Providers (NovelFull Pattern)

**Characteristics:**
- Static HTML content
- Simple pagination
- Standard CSS selectors

**Implementation:**
```python
class SimpleProvider(BaseNovelScraper):
    async def get_novel_metadata(self, novel_url: str):
        soup = await self._get_soup(novel_url)
        return NovelMetadata(
            title=self._extract_text_by_selector(soup, "h1.title"),
            author=self._extract_text_by_selector(soup, ".author"),
            description=self._extract_text_by_selector(soup, ".description")
        )
```

### 2. AJAX-Based Providers (NovelBuddy Pattern)

**Characteristics:**
- Dynamic content loading
- API endpoints for chapter lists
- Novel ID extraction required
- Complex error handling

**Key Implementation Steps:**

#### Step 1: Novel ID Extraction
```python
async def extract_novel_id(self, novel_url: str) -> Optional[str]:
    soup = await self._get_soup(novel_url)
    
    # Method 1: JavaScript variables
    scripts = soup.find_all("script", string=True)
    for script in scripts:
        match = re.search(r'novel_id["\']?\s*[:=]\s*["\']?(\d+)', script.string)
        if match:
            return match.group(1)
    
    # Method 2: Data attributes
    container = soup.find(attrs={"data-novel-id": True})
    if container:
        return container.get("data-novel-id")
    
    return None
```

#### Step 2: AJAX Chapter Discovery
```python
async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
    novel_id = await self.extract_novel_id(novel_url)
    if not novel_id:
        return []
    
    ajax_url = f"{self.base_url}/api/manga/{novel_id}/chapters"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": novel_url
    }
    
    response = await self._make_request(ajax_url, headers=headers)
    
    # Handle HTML or JSON response
    response_type = self.config.get("chapter_discovery", {}).get("ajax_response_type", "json")
    if response_type == "html":
        soup = BeautifulSoup(response, 'html.parser')
        return self._parse_chapter_list_html(soup)
    else:
        data = json.loads(response)
        return self._parse_chapter_list_json(data)
```

#### Step 3: Configuration
```yaml
# config/provider.yaml
provider:
  name: "novelbuddy"
  base_url: "https://novelbuddy.com"

chapter_discovery:
  method: "ajax"
  ajax_response_type: "html"  # or "json"

concurrent_processing:
  max_workers: 2
  chunk_size: 5
  delay_between_chunks: 5

selectors:
  title: ".detail .name h1"
  description: "div.section-body.summary p.content"
  chapter_title_page: "div.chapter__content h1"
  chapter_content: "div.chapter__content div.content-inner"
```

### 3. Circuit Breaker Providers (NovelBin Pattern)

**Characteristics:**
- Aggressive rate limiting
- Frequent connection issues
- Requires retry logic

**Implementation:**
```python
class CircuitBreakerProvider(BaseNovelScraper):
    def __init__(self, config):
        super().__init__(config)
        self.circuit_breaker = CircuitBreaker()
    
    async def _make_request_with_circuit_breaker(self, url: str):
        if self.circuit_breaker.is_open():
            await asyncio.sleep(self.circuit_breaker.get_wait_time())
        
        try:
            response = await self._make_request(url)
            self.circuit_breaker.record_success()
            return response
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
```

## 🔧 Common Patterns

### Markdownify Integration

The `markdownify` library provides superior HTML to markdown conversion compared to simple text extraction. It preserves formatting, handles emphasis properly, and generates cleaner markdown content. **This feature is now available for all providers** (NovelBuddy, Wuxiaworld, NovelBin, and NovelFull).

**Benefits:**
- Better paragraph structure preservation
- Proper handling of emphasis (bold, italic)
- Cleaner markdown output for EPUB generation
- Configurable conversion options
- Fallback to text extraction on errors
- Consistent behavior across all providers

**Configuration:**
```yaml
# config/provider.yaml
content_cleaning:
  use_markdownify: true  # Enable markdownify conversion
```

### Content Cleaning with Markdownify
```python
def _clean_chapter_content(self, content_elem) -> str:
    # Use markdownify for better HTML to markdown conversion
    use_markdownify = self.config.get("content_cleaning", {}).get("use_markdownify", True)

    if use_markdownify:
        content = self._convert_html_to_markdown(content_elem)
    else:
        # Fallback to text extraction
        content = content_elem.get_text(separator="\n", strip=True)

    # Remove ads
    ad_patterns = [
        r'Visit.*?for.*?chapters',
        r'\[Advertisement\].*?\[/Advertisement\]'
    ]

    for pattern in ad_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)

    return content.strip()

def _convert_html_to_markdown(self, content_elem) -> str:
    """Convert HTML to markdown using markdownify for better formatting."""
    from markdownify import markdownify as md

    html_content = str(content_elem)

    markdown_content = md(
        html_content,
        heading_style="ATX",
        emphasis_mark="*",
        strong_mark="**",
        strip=["script", "style", "meta", "link", "noscript"],
        wrap=True,
        wrap_width=80,
        escape_misc=False,
        newline_exit_br=True,
        escape_asterisks=False,
        escape_underscores=False
    )

    return self._post_process_markdown(markdown_content)
```

### Title Cleaning
```python
def _clean_chapter_title(self, title: str, novel_title: str) -> str:
    if not title:
        return "Untitled Chapter"
    
    # Remove novel name prefix
    if novel_title and title.startswith(novel_title):
        title = title[len(novel_title):].strip()
        title = title.lstrip(":-–—").strip()
    
    return title or "Untitled Chapter"
```

### Content-Based Title Enhancement

The scraper can automatically enhance chapter titles by extracting better titles from the chapter content. This is useful when the scraped title is just "Chapter X" but the content contains a more descriptive title.

**How it works:**
1. Detects when title is just "Chapter X" format
2. Searches first few paragraphs for better title patterns
3. Extracts and formats the enhanced title

**Supported patterns:**
- `Chapter 447 – Wicked Heart Granny (6)` → `Chapter 447 - Wicked Heart Granny (6)`
- `Chapter 123: The Beginning of the End` → `Chapter 123: The Beginning of the End`
- `447 - The Final Battle` → `Chapter 447 - The Final Battle`

**Usage in provider:**
```python
# After extracting content and before creating ChapterData
enhanced_title = self._extract_title_from_content(content, title, chapter_number)
if enhanced_title != title:
    logger.info(f"Enhanced chapter title: '{title}' -> '{enhanced_title}'")
    title = enhanced_title
```

**Configuration:**
```yaml
content_cleaning:
  text_processing:
    enhance_titles_from_content: true  # Enable/disable feature
    title_search_paragraphs: 3         # Number of paragraphs to search
```

### Error Handling
```python
async def _make_request_with_retry(self, url: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await self._make_request(url)
        except aiohttp.ClientResponseError as e:
            if e.status == 429:  # Rate limited
                wait_time = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)
    
    return None
```

## 🧪 Testing Patterns

### Basic Provider Test
```python
async def test_provider():
    config = get_provider_config("provider_name")
    
    async with ProviderScraper(config) as scraper:
        # Test metadata extraction
        metadata = await scraper.get_novel_metadata(TEST_URL)
        assert metadata is not None
        assert metadata.title
        assert metadata.description
        
        # Test chapter discovery
        chapters = await scraper.get_chapter_list(TEST_URL)
        assert len(chapters) > 0
        
        # Test content extraction
        if chapters:
            content = await scraper.scrape_chapter_content(chapters[0]["url"])
            assert content is not None
            assert len(content.content) > 100
```

### AJAX Provider Test
```python
async def test_ajax_provider():
    config = get_provider_config("novelbuddy")
    
    async with NovelBuddyScraper(config) as scraper:
        # Test novel ID extraction
        novel_id = await scraper.extract_novel_id(TEST_URL)
        assert novel_id is not None
        
        # Test AJAX chapter discovery
        chapters = await scraper.get_chapter_list(TEST_URL)
        assert len(chapters) > 0
        
        # Verify chapter URLs are valid
        for chapter in chapters[:3]:  # Test first 3
            assert chapter["url"].startswith("http")
            assert chapter["title"]
```

## 📚 Next Steps

1. **Choose Pattern**: Select the pattern that matches your target site
2. **Implement Core Methods**: Start with `get_novel_metadata`
3. **Add Configuration**: Create YAML config with selectors
4. **Test Incrementally**: Test each method as you implement
5. **Add Error Handling**: Implement retries and circuit breakers
6. **Optimize Performance**: Add concurrent processing settings

For detailed implementation guides, see [PROVIDER_DEVELOPMENT.md](PROVIDER_DEVELOPMENT.md).
