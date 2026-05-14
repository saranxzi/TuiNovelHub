# 🔧 Troubleshooting Guide

This guide helps you diagnose and fix common issues with wn-dl.

## 🚨 Common Issues

### Installation Problems

#### 1. Package Not Found

```bash
# Error: No package named 'wn-dl'
pip install wn-dl

# If still failing, try:
pip install --upgrade pip
pip install wn-dl

# Or use uv (recommended):
uv add wn-dl
```

#### 2. Python Version Issues

```bash
# Check Python version (requires 3.8+)
python --version

# If too old, install newer Python:
# Ubuntu/Debian: sudo apt install python3.9
# macOS: brew install python@3.9
# Windows: Download from python.org
```

#### 3. Dependency Conflicts

```bash
# Create virtual environment
python -m venv wn-dl-env
source wn-dl-env/bin/activate  # Linux/macOS
# wn-dl-env\Scripts\activate   # Windows

pip install wn-dl
```

### EPUB Generation Issues

#### 1. Pandoc Not Found

**Error**: `Pandoc is not available`

**Solution**:

```bash
# Install Pandoc
# Ubuntu/Debian:
sudo apt install pandoc

# macOS:
brew install pandoc

# Windows:
# Download from https://pandoc.org/installing.html

# Verify installation:
pandoc --version
```

#### 2. Large Novel Fails with Pandoc

**Error**: `Memory error` or `Process killed`

**Solution**:

```bash
# Force EbookLib for large novels
wn-dl generate-epub --input large-novel.md --use-ebooklib

# Or configure automatic fallback
wn-dl generate-epub --input large-novel.md  # Auto-fallback
```

#### 3. Empty EPUB Content

**Error**: EPUB file is small (~1MB) with no content

**Solution**:

```bash
# Check with verbose logging
wn-dl --with-info generate-epub --input novel.md

# Verify markdown file has content
head -n 20 novel.md

# Check chapter encoding
file novel.md  # Should show UTF-8
```

#### 4. Missing Table of Contents

**Error**: No TOC in generated EPUB

**Solution**:

```bash
# Ensure TOC is enabled
wn-dl generate-epub --input novel.md --config toc-config.yaml

# Check configuration:
cat config/temp_config.yaml | grep include_toc
# Should show: include_toc: true
```

### Scraping Issues

#### 1. Provider Not Found

**Error**: `No provider found for URL`

**Solution**:

```bash
# Check supported providers
wn-dl providers

# Manually specify provider
wn-dl scrape -u URL -p novelfull

# Check if domain is supported
wn-dl providers | grep "example.com"
```

#### 2. Rate Limiting / Blocked

**Error**: `HTTP 429` or `Access denied`

**Solution**:

```bash
# Reduce rate and workers
wn-dl scrape -u URL -w 1 -r 0.1

# Use configuration file
cat > slow-config.yaml << EOF
processing:
  max_workers: 1
  rate_limit: 0.1
  timeout: 60
EOF

wn-dl -c slow-config.yaml scrape -u URL
```

#### 3. Connection Timeouts

**Error**: `Connection timeout` or `Request failed`

**Solution**:

```bash
# Increase timeout
wn-dl scrape -u URL --config timeout-config.yaml

# timeout-config.yaml:
processing:
  timeout: 60
  max_retries: 5
  retry_delay: 2.0
```

#### 4. Incomplete Chapter List

**Error**: Only partial chapters downloaded

**Solution**:

```bash
# Enable verbose logging to see what's happening
wn-dl --with-info scrape -u URL

# Check if pagination is working
# Look for "Found X chapters" in output

# Try different provider if available
wn-dl scrape -u URL -p alternative-provider
```

### Configuration Issues

#### 1. Invalid YAML Syntax

**Error**: `YAML parsing error`

**Solution**:

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Common issues:
# - Missing quotes around strings with special characters
# - Incorrect indentation (use spaces, not tabs)
# - Missing colons after keys

# Example fix:
# Wrong: title: My Novel's Story
# Right: title: "My Novel's Story"
```

#### 2. Configuration Not Loading

**Error**: Settings not applied

**Solution**:

```bash
# Check configuration file location
wn-dl --with-info info

# Verify configuration is loaded
wn-dl -c my-config.yaml info

# Check file permissions
ls -la config/temp_config.yaml
```

### Performance Issues

#### 1. Slow Scraping

**Problem**: Very slow download speed

**Solution**:

```bash
# Increase workers and rate limit
wn-dl scrape -u URL -w 10 -r 2.0

# Skip cover images for speed
wn-dl scrape -u URL --no-cover

# Use fast configuration
cat > fast-config.yaml << EOF
processing:
  max_workers: 20
  rate_limit: 2.0
images:
  download_covers: false
EOF
```

#### 2. High Memory Usage

**Problem**: Process uses too much RAM

**Solution**:

```bash
# Use EbookLib for memory efficiency
wn-dl generate-epub --input novel.md --use-ebooklib

# Reduce workers
wn-dl scrape -u URL -w 2

# Monitor memory usage
top -p $(pgrep -f wn-dl)
```

#### 3. Large EPUB Files

**Problem**: EPUB files are too large

**Solution**:

```bash
# Files should be optimized automatically
# Check if fonts are properly optimized:
unzip -l novel.epub | grep -E "\.(ttf|otf)"
# Should only show Bitter fonts, not FiraCode

# If still large, check content:
unzip -l novel.epub | head -20
```

## 🔍 Debugging Tools

### System Information

```bash
# Check system status
wn-dl info

# Check with Pandoc validation
wn-dl info --check-pandoc

# Show detailed system info
wn-dl --with-info info
```

### Verbose Logging

```bash
# Enable detailed logging for any command
wn-dl --with-info [command]

# Examples:
wn-dl --with-info scrape -u URL
wn-dl --with-info generate-epub --input novel.md
wn-dl --with-info providers
```

### Configuration Testing

```bash
# Test configuration file
wn-dl -c my-config.yaml info

# Validate provider configuration
python scripts/validate_provider.py provider-name
```

### Content Analysis

```bash
# Analyze EPUB content
python -c "
import zipfile
with zipfile.ZipFile('novel.epub', 'r') as z:
    print('Files:', len(z.namelist()))
    for f in z.namelist()[:10]:
        print(f'  {f}')
"

# Check markdown structure
head -n 50 novel.md
grep -c "^# " novel.md  # Count chapters
```

## 🆘 Getting Help

### Before Reporting Issues

1. **Update to latest version**:
   

```bash
   pip install --upgrade wn-dl
   ```

2. **Check existing issues**:
   - Search GitHub issues
   - Check documentation

3. **Gather information**:
   

```bash
   # System info
   wn-dl info
   
   # Error with verbose logging
   wn-dl --with-info [failing-command] 2>&1 | tee error.log
   ```

### Reporting Bugs

Include this information:

1. **Command that failed**:
   

```bash
   wn-dl scrape -u https://example.com/novel
   ```

2. **Error output**:
   

```
   Full error message and stack trace
   ```

3. **System information**:
   

```bash
   wn-dl info
   python --version
   pip list | grep -E "(wn-dl|pandoc|ebooklib)"
   ```

4. **Configuration** (if using custom config):
   

```yaml
   # Your config file content (remove sensitive data)
   ```

### Community Support

* **GitHub Issues**: Bug reports and feature requests
* **Discussions**: General questions and help
* **Documentation**: Check all guides in `docs/`

## 🔧 Advanced Debugging

### Provider Issues

```bash
# Test specific provider
python examples/test_provider.py https://site.com/novel

# Analyze HTML structure
python scripts/analyze_html_structure.py https://site.com/novel

# Debug selectors
python -c "
import requests
from bs4 import BeautifulSoup
soup = BeautifulSoup(requests.get('URL').content, 'html.parser')
print(soup.select('your-selector'))
"
```

### NovelBuddy-Specific Issues

#### 1. AJAX Response Format Error

**Error**: `WARNING AJAX response was not JSON, got HTML instead`

**Cause**: NovelBuddy returns HTML instead of JSON for chapter discovery

**Solution**:
```yaml
# In config/novelbuddy-provider.yaml
chapter_discovery:
  ajax_response_type: "html"  # Set to html instead of json
```

#### 2. Novel ID Extraction Failed

**Error**: `Could not extract novel ID from URL`

**Cause**: Novel ID extraction logic failed to parse the page

**Debug Steps**:
```bash
# Test novel ID extraction manually
python -c "
import asyncio
from wn_dl.providers.novelbuddy import NovelBuddyScraper
from wn_dl.config import get_provider_config

async def test():
    config = get_provider_config('novelbuddy')
    async with NovelBuddyScraper(config) as scraper:
        novel_id = await scraper.extract_novel_id('YOUR_URL')
        print(f'Novel ID: {novel_id}')

asyncio.run(test())
"
```

**Manual Fix**:
```python
# Check page source for novel ID patterns:
# - JavaScript variables: novel_id = 12345
# - Data attributes: data-novel-id="12345"
# - URL patterns: /api/manga/12345/chapters
```

#### 3. Empty Description Field

**Error**: Description shows as empty in generated files

**Cause**: CSS selector not matching the summary content

**Debug Steps**:
```bash
# Test description extraction
python -c "
import requests
from bs4 import BeautifulSoup

url = 'YOUR_NOVEL_URL'
soup = BeautifulSoup(requests.get(url).content, 'html.parser')

# Test different selectors
selectors = [
    'div.section-body.summary p.content',
    '.summary-content',
    '.description',
    'div.summary p'
]

for selector in selectors:
    result = soup.select_one(selector)
    print(f'{selector}: {result.get_text() if result else None}')
"
```

#### 4. Chapter Title Extraction Issues

**Error**: Chapter titles showing as novel name instead of chapter title

**Cause**: Wrong CSS selector or title cleaning needed

**Solution**:
```yaml
# Use page-specific selector
selectors:
  chapter_title_page: "div.chapter__content h1"  # For individual chapter pages
  chapter_title: ".c-breadcrumb li.active"       # For chapter lists
```

**Title Cleaning**:
```python
# Implement title cleaning in scraper
def _clean_chapter_title(self, title: str, novel_title: str) -> str:
    if not title:
        return "Untitled Chapter"

    # Remove novel name prefix
    if novel_title and title.startswith(novel_title):
        title = title[len(novel_title):].strip()
        title = title.lstrip(":-–—").strip()

    return title or "Untitled Chapter"
```

#### 5. Rate Limiting Issues

**Error**: Frequent timeouts or connection errors

**Cause**: Too many concurrent requests

**Solution**:
```yaml
# Reduce concurrent processing
concurrent_processing:
  max_workers: 2        # Reduce from default
  chunk_size: 5         # Smaller chunks
  delay_between_chunks: 5  # Longer delays
```

#### 6. Content Formatting Issues

**Error**: Poor paragraph formatting in EPUB

**Cause**: Content cleaning removing paragraph breaks

**Solution**:
```python
# Preserve paragraph structure during cleaning
def _extract_paragraphs_with_breaks(self, content: str) -> str:
    # Use placeholder to preserve double newlines
    content = content.replace("\n\n", "PARAGRAPH_BREAK_PLACEHOLDER")

    # Clean content
    content = re.sub(r'\s+', ' ', content)

    # Restore paragraph breaks
    content = content.replace("PARAGRAPH_BREAK_PLACEHOLDER", "\n\n")

    return content.strip()
```

### EPUB Validation

```bash
# Install epubcheck (if available)
java -jar epubcheck.jar novel.epub

# Manual EPUB inspection
unzip novel.epub -d epub-contents/
ls -la epub-contents/
```

### Network Issues

```bash
# Test connectivity
curl -I https://target-site.com

# Check DNS resolution
nslookup target-site.com

# Test with different user agent
curl -H "User-Agent: wn-dl/1.0" https://target-site.com
```

## 📊 Performance Monitoring

### Monitor Resource Usage

```bash
# CPU and memory usage
top -p $(pgrep -f wn-dl)

# Disk I/O
iotop -p $(pgrep -f wn-dl)

# Network usage
nethogs
```

### Optimize Settings

```yaml
# For slow/unstable sites
processing:
  max_workers: 1
  rate_limit: 0.1
  timeout: 60

# For fast/stable sites  
processing:
  max_workers: 20
  rate_limit: 2.0
  timeout: 15

# For large novels
epub:
  use_ebooklib: true
  include_toc: true
```

---

**Need more help?** Check the [complete documentation](README.md) or open an issue on GitHub.
