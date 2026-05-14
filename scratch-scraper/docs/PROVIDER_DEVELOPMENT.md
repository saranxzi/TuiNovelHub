# 🔌 Provider Development Guide

This guide covers how to add support for new web novel platforms by implementing custom providers.

## 🏗️ Provider Architecture

### Overview

A provider is a module that handles scraping from a specific web novel platform:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Novel     │───▶│   Provider       │───▶│   Structured    │
│   Website       │    │   Implementation │    │   Data          │
│                 │    │                  │    │                 │
│ • Novel pages   │    │ • HTML parsing   │    │ • Novel info    │
│ • Chapter lists │    │ • Data extraction│    │ • Chapter list  │
│ • Chapter text  │    │ • Error handling │    │ • Chapter text  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Components

1. **Scraper Class** - Inherits from `BaseNovelScraper`
2. **Configuration File** - YAML file with selectors and settings
3. **Registration** - Automatic provider discovery

## 📁 Directory Structure

```
src/wn_dl/providers/
├── __init__.py                    # Provider registration
├── registry.py                    # Provider registry system
├── [provider_name]/
│   ├── __init__.py               # Provider module init
│   └── scraper.py                # Scraper implementation
└── config/
    └── [provider_name]-provider.yaml  # Configuration
```

## 🚀 Quick Start

### 1. Analyze the Website

Before coding, analyze the target website structure:

```bash
# Use the analysis script
python scripts/analyze_html_structure.py https://example.com/novel-url

# Manual analysis
curl -s "https://example.com/novel-url" | grep -E "(title|chapter|content)"
```

### 2. Create Provider Files

```bash
# Create provider directory
mkdir -p src/wn_dl/providers/mysite

# Create scraper file
touch src/wn_dl/providers/mysite/scraper.py
touch src/wn_dl/providers/mysite/__init__.py

# Create configuration
touch config/mysite-provider.yaml
```

### 3. Implement Scraper

```python
# src/wn_dl/providers/mysite/scraper.py
from typing import Dict, List, Optional
from wn_dl.core.base_scraper import BaseNovelScraper
from wn_dl.core.models import ChapterInfo, NovelInfo

class MySiteScraper(BaseNovelScraper):
    """Scraper for MyNovelSite."""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.base_url = "https://mynovelsite.com"
    
    async def get_novel_info(self, url: str) -> Optional[NovelInfo]:
        """Extract novel information from the main page."""
        soup = await self.get_soup(url)
        if not soup:
            return None
        
        # Extract novel details using CSS selectors
        title = self.extract_text(soup, self.config["selectors"]["title"])
        author = self.extract_text(soup, self.config["selectors"]["author"])
        description = self.extract_text(soup, self.config["selectors"]["description"])
        
        return NovelInfo(
            title=title,
            author=author,
            description=description,
            url=url,
            cover_url=self.extract_attr(soup, self.config["selectors"]["cover"], "src")
        )
    
    async def get_chapter_list(self, novel_url: str) -> List[ChapterInfo]:
        """Get list of all chapters."""
        chapters = []
        
        # Handle pagination if needed
        page = 1
        while True:
            page_url = f"{novel_url}/chapters?page={page}"
            soup = await self.get_soup(page_url)
            
            if not soup:
                break
            
            # Extract chapter links
            chapter_links = soup.select(self.config["selectors"]["chapter_links"])
            
            if not chapter_links:
                break
            
            for link in chapter_links:
                title = link.get_text(strip=True)
                url = self.resolve_url(link.get("href"), page_url)
                
                chapters.append(ChapterInfo(
                    title=title,
                    url=url,
                    index=len(chapters) + 1
                ))
            
            page += 1
        
        return chapters
    
    async def get_chapter_content(self, chapter_url: str) -> Optional[str]:
        """Extract chapter content."""
        soup = await self.get_soup(chapter_url)
        if not soup:
            return None
        
        # Extract content using selector
        content_elem = soup.select_one(self.config["selectors"]["content"])
        if not content_elem:
            return None
        
        # Clean up content
        content = self.clean_content(content_elem.get_text())
        return content
```

### 4. Create Configuration

```yaml
# config/mysite-provider.yaml
name: "MyNovelSite"
domains:
  - "mynovelsite.com"
  - "www.mynovelsite.com"

selectors:
  title: "h1.novel-title"
  author: ".novel-author a"
  description: ".novel-description p"
  cover: ".novel-cover img"
  chapter_links: ".chapter-list a"
  content: ".chapter-content"

settings:
  rate_limit: 0.5
  max_workers: 5
  timeout: 30
  
  # Pagination settings
  pagination:
    enabled: true
    url_pattern: "{base_url}/chapters?page={page}"
    max_pages: 1000

  # Content cleaning
  content_cleaning:
    remove_ads: true
    remove_selectors:
      - ".advertisement"
      - ".popup"
    replace_patterns:
      - pattern: "Read more at.*"
        replacement: ""
```

### 5. Register Provider

```python
# src/wn_dl/providers/mysite/__init__.py
from .scraper import MySiteScraper

__all__ = ["MySiteScraper"]
```

```python
# Update src/wn_dl/providers/__init__.py
from .mysite.scraper import MySiteScraper

# Add to provider list
PROVIDERS = [
    # ... existing providers
    MySiteScraper,
]
```

## 🔧 Advanced Features

### Handling Complex Pagination

```python
async def get_chapter_list(self, novel_url: str) -> List[ChapterInfo]:
    """Handle complex pagination patterns."""
    chapters = []
    
    # Method 1: Page-based pagination
    if self.config["pagination"]["type"] == "page":
        for page in range(1, self.config["pagination"]["max_pages"] + 1):
            page_chapters = await self._get_chapters_from_page(novel_url, page)
            if not page_chapters:
                break
            chapters.extend(page_chapters)
    
    # Method 2: AJAX-based loading
    elif self.config["pagination"]["type"] == "ajax":
        chapters = await self._get_chapters_ajax(novel_url)
    
    # Method 3: Infinite scroll
    elif self.config["pagination"]["type"] == "scroll":
        chapters = await self._get_chapters_scroll(novel_url)
    
    return chapters
```

### Error Handling and Retries

```python
async def get_chapter_content(self, chapter_url: str) -> Optional[str]:
    """Get chapter content with retry logic."""
    for attempt in range(self.config["settings"]["max_retries"]):
        try:
            soup = await self.get_soup(chapter_url)
            if soup:
                content = self._extract_content(soup)
                if content:
                    return content
        
        except Exception as e:
            self.logger.warning(f"Attempt {attempt + 1} failed for {chapter_url}: {e}")
            
            if attempt < self.config["settings"]["max_retries"] - 1:
                await asyncio.sleep(self.config["settings"]["retry_delay"])
    
    return None
```

### Content Cleaning

```python
def clean_content(self, content: str) -> str:
    """Clean and normalize chapter content."""
    # Remove ads and unwanted content
    for pattern in self.config["content_cleaning"]["remove_patterns"]:
        content = re.sub(pattern, "", content, flags=re.IGNORECASE)
    
    # Fix common issues
    content = content.replace("'", "'")  # Fix apostrophes
    content = content.replace(""", '"').replace(""", '"')  # Fix quotes
    content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
    
    return content.strip()
```

## 🧪 Testing

### Unit Testing

```python
# tests/unit/providers/test_mysite.py
import pytest
from wn_dl.providers.mysite.scraper import MySiteScraper

@pytest.fixture
def scraper():
    config = {
        "selectors": {
            "title": "h1.novel-title",
            "author": ".novel-author",
            "content": ".chapter-content"
        }
    }
    return MySiteScraper(config)

@pytest.mark.asyncio
async def test_get_novel_info(scraper):
    """Test novel info extraction."""
    novel_info = await scraper.get_novel_info("https://mysite.com/novel/test")
    assert novel_info is not None
    assert novel_info.title
    assert novel_info.author
```

### Integration Testing

```bash
# Test with real URLs
python examples/test_provider.py https://mysite.com/novel/test-novel

# Validate provider
python scripts/validate_provider.py mysite
```

## 📋 Configuration Reference

### Required Selectors

```yaml
selectors:
  title: "CSS selector for novel title"
  author: "CSS selector for author name"
  description: "CSS selector for description"
  cover: "CSS selector for cover image"
  chapter_links: "CSS selector for chapter links"
  content: "CSS selector for chapter content"
```

### Optional Settings

```yaml
settings:
  rate_limit: 0.5          # Requests per second
  max_workers: 5           # Concurrent workers
  timeout: 30              # Request timeout
  max_retries: 3           # Retry attempts
  retry_delay: 1.0         # Delay between retries
  
  # User agent string
  user_agent: "wn-dl/1.0"
  
  # Custom headers
  headers:
    Accept: "text/html"
    Accept-Language: "en-US"
```

## 🎯 Best Practices

### 1. Respect Rate Limits

```python
# Always include rate limiting
await asyncio.sleep(1.0 / self.config["settings"]["rate_limit"])
```

### 2. Handle Errors Gracefully

```python
try:
    content = await self.get_chapter_content(url)
except Exception as e:
    self.logger.error(f"Failed to get content: {e}")
    return None
```

### 3. Use Robust Selectors

```yaml
# Good: Specific and stable
selectors:
  title: "h1.novel-title, .book-title h1"
  
# Bad: Too generic
selectors:
  title: "h1"
```

### 4. Clean Content Properly

```python
def clean_content(self, content: str) -> str:
    # Remove ads
    content = re.sub(r'Read more at.*', '', content)
    
    # Fix encoding issues
    content = content.replace('\u2019', "'")
    
    # Normalize whitespace
    content = re.sub(r'\s+', ' ', content)
    
    return content.strip()
```

### 5. Test Thoroughly

```bash
# Test with different novels
python examples/test_provider.py https://site.com/novel1
python examples/test_provider.py https://site.com/novel2

# Test edge cases
python examples/test_provider.py https://site.com/short-novel
python examples/test_provider.py https://site.com/very-long-novel
```

## 🔍 Debugging

### Enable Debug Logging

```bash
# Run with detailed logging
wn-dl --with-info scrape -u https://mysite.com/novel -p mysite
```

### Common Issues

1. **Selector not found**
   ```python
   # Add fallback selectors
   title = (self.extract_text(soup, "h1.title") or 
            self.extract_text(soup, ".novel-title") or
            self.extract_text(soup, "h1"))
   ```

2. **Rate limiting**
   ```yaml
   # Reduce rate in config
   settings:
     rate_limit: 0.1  # Slower requests
   ```

3. **Content encoding**
   ```python
   # Handle encoding issues
   content = content.encode('utf-8').decode('utf-8')
   ```

## 🔧 Advanced Patterns: NovelBuddy Case Study

NovelBuddy represents a complex AJAX-based provider that demonstrates advanced scraping patterns. This section provides detailed implementation guidance for similar platforms.

### Architecture Overview

NovelBuddy uses:
- **Novel ID Extraction**: URLs contain slugs that must be mapped to numeric IDs
- **AJAX Chapter Discovery**: Chapter lists are loaded via API endpoints
- **Dynamic Content Loading**: Metadata and content use lazy loading
- **Rate Limiting**: Requires careful request management

### Novel ID Extraction

Many modern platforms use internal IDs for API calls:

```python
async def extract_novel_id(self, novel_url: str) -> Optional[str]:
    """Extract numeric novel ID from page JavaScript."""
    soup = await self._get_soup(novel_url)
    if not soup:
        return None

    # Method 1: Parse from JavaScript variables
    scripts = soup.find_all("script", string=True)
    for script in scripts:
        script_content = script.string
        if "novel_id" in script_content:
            # Extract ID using regex
            match = re.search(r'novel_id["\']?\s*[:=]\s*["\']?(\d+)', script_content)
            if match:
                return match.group(1)

    # Method 2: Parse from data attributes
    novel_container = soup.find(attrs={"data-novel-id": True})
    if novel_container:
        return novel_container.get("data-novel-id")

    return None
```

### AJAX Chapter Discovery

For platforms with AJAX-based chapter loading:

```python
async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
    """Get chapters via AJAX endpoint."""
    novel_id = await self.extract_novel_id(novel_url)
    if not novel_id:
        logger.error(f"Could not extract novel ID from {novel_url}")
        return []

    # Build AJAX endpoint URL
    ajax_url = f"{self.base_url}/api/manga/{novel_id}/chapters"
    params = {"source": "detail"}

    try:
        # Make AJAX request with proper headers
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": novel_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        response = await self._make_request(ajax_url, params=params, headers=headers)
        if not response:
            return []

        # Handle different response types
        response_type = self.config.get("chapter_discovery", {}).get("ajax_response_type", "json")

        if response_type == "html":
            # Parse HTML response
            soup = BeautifulSoup(response, 'html.parser')
            return self._parse_chapter_list_html(soup)
        else:
            # Parse JSON response
            data = json.loads(response)
            return self._parse_chapter_list_json(data)

    except Exception as e:
        logger.error(f"Error fetching chapter list via AJAX: {e}")
        return []
```

### Configuration for AJAX Providers

```yaml
# config/novelbuddy-provider.yaml
provider:
  name: "novelbuddy"
  base_url: "https://novelbuddy.com"

# AJAX-specific settings
chapter_discovery:
  method: "ajax"
  endpoint: "/api/manga/{novel_id}/chapters"
  ajax_response_type: "html"  # or "json"
  params:
    source: "detail"
  headers:
    X-Requested-With: "XMLHttpRequest"

# Rate limiting for AJAX providers
concurrent_processing:
  max_workers: 2
  chunk_size: 5
  delay_between_chunks: 5

selectors:
  # Novel metadata
  title: ".detail .name h1"
  author: ".meta p:-soup-contains('Authors') a"
  description: "div.section-body.summary p.content"
  cover_image: "#cover .img-cover img"

  # Chapter content
  chapter_title_page: "div.chapter__content h1"
  chapter_content: "div.chapter__content div.content-inner"
```

### Content Cleaning for Complex Sites

NovelBuddy requires sophisticated content cleaning:

```python
def _clean_chapter_content(self, content: str) -> str:
    """Clean chapter content with advanced filtering."""
    if not content:
        return ""

    # Remove advertisement patterns
    ad_patterns = [
        r'Visit.*?for.*?chapters',
        r'Read.*?latest.*?chapters',
        r'Support.*?author',
        r'\[Advertisement\].*?\[/Advertisement\]'
    ]

    for pattern in ad_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)

    # Preserve paragraph structure
    content = self._extract_paragraphs_with_breaks(content)

    # Clean whitespace while preserving structure
    lines = content.split('\n')
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if line and not self._is_advertisement_line(line):
            cleaned_lines.append(line)

    return '\n\n'.join(cleaned_lines)

def _extract_paragraphs_with_breaks(self, content: str) -> str:
    """Extract paragraphs while preserving breaks."""
    # Use placeholder to preserve double newlines during cleaning
    content = content.replace("\n\n", "PARAGRAPH_BREAK_PLACEHOLDER")

    # Normalize whitespace
    content = re.sub(r'\s+', ' ', content)

    # Restore paragraph breaks
    content = content.replace("PARAGRAPH_BREAK_PLACEHOLDER", "\n\n")

    return content.strip()
```

### Error Handling for AJAX Providers

```python
async def _make_ajax_request(self, url: str, **kwargs) -> Optional[str]:
    """Make AJAX request with proper error handling."""
    try:
        response = await self._make_request(url, **kwargs)

        # Check if response is expected format
        expected_type = self.config.get("chapter_discovery", {}).get("ajax_response_type", "json")

        if expected_type == "json":
            try:
                json.loads(response)  # Validate JSON
            except json.JSONDecodeError:
                logger.warning(f"Expected JSON but got HTML from {url}")
                # Handle graceful fallback
                return response

        return response

    except aiohttp.ClientResponseError as e:
        if e.status == 429:  # Rate limited
            logger.warning(f"Rate limited on {url}, backing off...")
            await asyncio.sleep(self.config.get("settings", {}).get("rate_limit_backoff", 10))
            return await self._make_ajax_request(url, **kwargs)  # Retry once
        else:
            logger.error(f"HTTP error {e.status} for {url}")
            return None
    except Exception as e:
        logger.error(f"Unexpected error for AJAX request {url}: {e}")
        return None
```

### Testing AJAX Providers

```python
# test_novelbuddy.py
async def test_ajax_functionality():
    """Test AJAX-specific functionality."""
    config = get_provider_config("novelbuddy")

    async with NovelBuddyScraper(config) as scraper:
        # Test novel ID extraction
        novel_id = await scraper.extract_novel_id(TEST_URL)
        assert novel_id is not None, "Failed to extract novel ID"

        # Test AJAX chapter discovery
        chapters = await scraper.get_chapter_list(TEST_URL)
        assert len(chapters) > 0, "No chapters found via AJAX"

        # Test content extraction
        if chapters:
            content = await scraper.scrape_chapter_content(chapters[0]["url"])
            assert content is not None, "Failed to extract chapter content"
            assert len(content.content) > 100, "Content too short"
```

## 📚 Examples

See existing providers for reference:

- **NovelFull** - Simple structure with pagination
- **NovelBin** - Complex with circuit breaker pattern
- **NovelBuddy** - AJAX-based with novel ID extraction
- **Custom Provider** - Template for new implementations

## 🤝 Contributing

1. **Fork the repository**
2. **Create provider branch**: `git checkout -b provider/mysite`
3. **Implement provider** following this guide
4. **Add tests** for your provider
5. **Submit pull request** with documentation
