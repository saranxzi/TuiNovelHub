# 📖 Complete Usage Guide

This guide covers all aspects of using wn-dl for downloading and converting web novels to EPUB format.

## 🚀 Quick Start

### Installation

```bash
# Recommended: Install with uv
uv add wn-dl

# Alternative: Install with pip
pip install wn-dl

# Development installation
git clone https://github.com/yourusername/wn-dl.git
cd wn-dl
uv sync  # or pip install -e ".[dev]"
```

### Basic Commands

```bash
# Show help
wn-dl --help

# Show system information
wn-dl info

# List supported providers
wn-dl providers
```

## 📚 Scraping Novels

### Basic Scraping

```bash
# Download a novel (markdown + EPUB)
wn-dl scrape -u https://novelfull.com/novel-name

# Download from RoyalRoad
wn-dl scrape -u https://www.royalroad.com/fiction/21220/mother-of-learning

# Specify output directory
wn-dl scrape -u https://novelfull.com/novel-name -o ./my-novels

# Download only EPUB
wn-dl scrape -u https://novelfull.com/novel-name -f epub

# Download only markdown
wn-dl scrape -u https://novelfull.com/novel-name -f markdown
```

### Advanced Scraping Options

```bash
# Custom provider (if auto-detection fails)
wn-dl scrape -u https://example.com/novel -p novelfull

# Adjust concurrency and rate limiting
wn-dl scrape -u https://example.com/novel -w 5 -r 0.5

# Skip cover image download
wn-dl scrape -u https://example.com/novel --no-cover

# Show detailed logging
wn-dl --with-info scrape -u https://example.com/novel
```

### Configuration File Usage

```bash
# Use custom configuration
wn-dl -c my-config.yaml scrape -u https://example.com/novel

# Configuration file locations (checked in order):
# 1. Specified with -c/--config
# 2. ./config/temp_config.yaml
# 3. Built-in defaults
```

## 📖 EPUB Generation

### From Existing Markdown

```bash
# Generate EPUB from markdown (uses Pandoc by default)
wn-dl generate-epub --input novel.md

# Specify output directory
wn-dl generate-epub --input novel.md --output ./epubs

# Custom title and metadata
wn-dl generate-epub --input novel.md --title "My Novel" --author "Author Name"
```

### EPUB Generation Options

```bash
# Force EbookLib usage (for large novels)
wn-dl generate-epub --input novel.md --use-ebooklib

# Disable table of contents
wn-dl generate-epub --input novel.md --no-toc

# Custom CSS file
wn-dl generate-epub --input novel.md --css custom-style.css

# Custom cover image
wn-dl generate-epub --input novel.md --cover cover.jpg

# Disable automatic fallback to EbookLib
wn-dl generate-epub --input novel.md --no-fallback

# Silent mode (only progress bar)
wn-dl generate-epub --input novel.md --silent
```

### Dual EPUB Generation System

The tool uses a smart dual-generation system:

1. **Pandoc (Primary)**: High-quality EPUB generation
   - Best for novels under 1000 chapters
   - Professional typography and formatting
   - Advanced EPUB features

2. **EbookLib (Fallback)**: Handles large novels
   - Automatically used when Pandoc fails
   - Optimized for 2000+ chapter novels
   - Memory efficient processing

```bash
# The system automatically chooses the best generator:
wn-dl generate-epub --input large-novel.md  # Auto-fallback if needed

# Force specific generator:
wn-dl generate-epub --input novel.md --use-ebooklib  # Force EbookLib
wn-dl generate-epub --input novel.md --no-fallback   # Pandoc only
```

## 📚 Novel Management

### List Scraped Novels

View all novels that have been scraped and their status:

```bash
# List all novels in default output directory
wn-dl novels list

# List novels in specific directory
wn-dl novels list --directory ~/my-novels

# Show only novels without EPUB files
wn-dl novels list --no-epub

# Output formats
wn-dl novels list --format table    # Default table view
wn-dl novels list --format simple   # Simple list
wn-dl novels list --format json     # JSON output
```

### Regenerate EPUBs

Regenerate EPUB files from existing markdown without re-scraping:

```bash
# Regenerate single novel by name
wn-dl novels regenerate --name "Novel Title"

# Regenerate using direct file path
wn-dl novels regenerate --input path/to/novel.md

# Regenerate all novels
wn-dl novels regenerate --all

# Regenerate only novels missing EPUB files
wn-dl novels regenerate --missing-epub

# Use specific font and generator
wn-dl novels regenerate --all --font bitter --use-ebooklib

# Silent mode for bulk operations
wn-dl novels regenerate --all --silent
```

### Novel Management Options

```bash
# Search in specific directory
wn-dl novels regenerate --name "Novel" --directory ~/novels

# Custom output directory
wn-dl novels regenerate --name "Novel" --output ~/epubs

# Force EbookLib for large novels
wn-dl novels regenerate --missing-epub --use-ebooklib
```

## ⚙️ Configuration

### Configuration File Structure

```yaml
# config/temp_config.yaml
epub:
  chapter_level: 2
  include_toc: true
  custom_css: true
  use_ebooklib: false  # Default to Pandoc
  pandoc_args: []

images:
  download_covers: true
  target_size: [600, 800]
  quality: 85
  format: "JPEG"

processing:
  max_workers: 10
  rate_limit: 0.5
  timeout: 30
```

### Environment Variables

```bash
# Set default configuration file
export WN_DL_CONFIG=/path/to/config.yaml

# Set default output directory
export WN_DL_OUTPUT=/path/to/novels
```

## 🔧 Advanced Usage

### Content Cleaning and Ad Removal

The scraper automatically removes ads and unwanted content from chapters:

```bash
# NovelFire automatically removes promotional text like:
# "Search the **NovelFire.net** website on Google to access chapters..."

# Content cleaning features:
# - Removes advertisement paragraphs
# - Fixes character encoding issues
# - Normalizes whitespace and formatting
# - Removes duplicate content
```

**Supported ad removal patterns:**
- NovelFire promotional messages
- Generic "Visit website" messages
- Advertisement containers and banners
- Social media links and donation requests

### Custom Provider Development

```bash
# Validate a custom provider
python scripts/validate_provider.py my_provider

# Test provider implementation
python examples/test_provider.py https://example.com/novel
```

### Batch Processing

```bash
# Process multiple novels
for url in $(cat novel-urls.txt); do
    wn-dl scrape -u "$url" -o ./batch-novels
done

# Parallel processing with GNU parallel
parallel -j 3 "wn-dl scrape -u {} -o ./batch-novels" :::: novel-urls.txt
```

### Integration with Other Tools

```bash
# Convert existing EPUB to different format
pandoc novel.epub -o novel.pdf

# Extract text from EPUB
unzip -p novel.epub OEBPS/text/*.xhtml | html2text

# Validate EPUB
epubcheck novel.epub
```

## 🐛 Troubleshooting

### Common Issues

1. **Pandoc not found**
   ```bash
   # Install Pandoc
   sudo apt install pandoc  # Ubuntu/Debian
   brew install pandoc      # macOS
   ```

2. **Large novel fails**
   ```bash
   # Force EbookLib for large novels
   wn-dl generate-epub --input large-novel.md --use-ebooklib
   ```

3. **Rate limiting issues**
   ```bash
   # Reduce rate and workers
   wn-dl scrape -u URL -w 2 -r 1.0
   ```

4. **Memory issues**
   ```bash
   # Use EbookLib for memory efficiency
   wn-dl generate-epub --input novel.md --use-ebooklib
   ```

### Debug Mode

```bash
# Enable detailed logging
wn-dl --with-info scrape -u https://example.com/novel

# Check system information
wn-dl info --check-pandoc
```

## 📊 Performance Tips

### For Large Novels (1000+ chapters)

```bash
# Optimal settings for large novels
wn-dl scrape -u URL -w 5 -r 0.5 -f epub
wn-dl generate-epub --input novel.md --use-ebooklib --no-toc
```

### For Fast Processing

```bash
# Maximum performance settings
wn-dl scrape -u URL -w 20 -r 2.0 --no-cover
```

### For Slow/Unstable Sites

```bash
# Conservative settings
wn-dl scrape -u URL -w 1 -r 0.2
```

## 🎯 Best Practices

1. **Always test with small novels first**
2. **Use configuration files for consistent settings**
3. **Monitor rate limits to avoid being blocked**
4. **Keep backups of markdown files**
5. **Use EbookLib for novels over 1000 chapters**
6. **Enable logging for debugging issues**

## 📱 eReader Compatibility

The generated EPUBs are optimized for:

- ✅ **Kindle** (via conversion)
- ✅ **Kobo**
- ✅ **Apple Books**
- ✅ **Google Play Books**
- ✅ **Adobe Digital Editions**
- ✅ **Calibre**

### File Size Optimization

- **Small novels** (< 100 chapters): ~0.5-2 MB
- **Medium novels** (100-500 chapters): ~2-5 MB  
- **Large novels** (500+ chapters): ~5-15 MB

The tool automatically optimizes file sizes by:
- Removing unnecessary monospace fonts (67-94% reduction)
- Compressing images
- Optimizing CSS and HTML structure
