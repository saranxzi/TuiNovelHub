# 📚 Web Novel Downloader (wn-dl)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A powerful, modular tool for downloading web novels and converting them to high-quality EPUB files with professional formatting and accessibility features.

## ✨ Features

* 🌐 **Multi-Provider Support** - Download from various web novel platforms
* 📖 **Dual EPUB Generation** - Pandoc (primary) + EbookLib (fallback) for maximum compatibility
* 🎨 **Professional Typography** - Multiple font families (Bitter, Bookerly) with 90% file size reduction
* ⚙️ **User Configuration** - Personalized preferences with cross-platform config management
* 📑 **Complete Navigation** - Full table of contents with chapter jumping
* ⚡ **High Performance** - Concurrent processing with progress tracking
* 🗄️ **Persistent Storage** - SQLite database for novel tracking and progress monitoring
* 🔍 **Advanced Search** - Filter novels by status, provider, and metadata
* 📊 **Progress Tracking** - Real-time scraping status and chapter completion
* 💾 **Database Management** - Backup, restore, and sync capabilities
* 🚀 **Intelligent Caching** - HTTP response caching with 50x+ speed improvements
* 🗜️ **Smart Compression** - Automatic content compression with 60-80% space savings
* 🔧 **Highly Configurable** - Extensive customization options
* 🛡️ **Robust & Reliable** - Rate limiting, retries, and error recovery
* 📱 **eReader Optimized** - Compact file sizes and fast loading

## 🚀 Quick Start

### Installation

```bash
# Install with uv (recommended)
uv add wn-dl

# Or with pip
pip install wn-dl
```

### Basic Usage

```bash
# Download a novel (uses EbookLib by default for scraping)
wn-dl scrape -u https://example.com/novel-url

# Generate EPUB from existing markdown (uses Pandoc by default)
wn-dl generate-epub --input novel.md

# Show detailed logging
wn-dl --with-info scrape -u https://example.com/novel-url

# List novels with database filtering
wn-dl novels list --status completed --provider NovelFull

# Search novels
wn-dl novels list --search "dragon"

# Database management
wn-dl novels sync    # Sync with filesystem
wn-dl novels stats   # Show statistics
wn-dl novels backup  # Create backup
```

### 🎨 Font Selection & User Configuration

wn-dl features professional typography with multiple font families and a comprehensive user configuration system:

```bash
# List available fonts
wn-dl list-fonts

# Use specific font for EPUB generation
wn-dl scrape -u https://example.com/novel --font bookerly
wn-dl generate-epub --input novel.md --font bitter

# Set up personalized preferences (interactive)
wn-dl config init

# View current configuration
wn-dl config show

# Set default font preference
wn-dl config set font.default_family bookerly

# Set default directories
wn-dl config set directories.output ~/novels
wn-dl config set epub.preferred_generator ebooklib
```

**Available Fonts:**
- **Bitter** (default): Contemporary serif, excellent for general reading
- **Bookerly**: Amazon's reading-optimized font, perfect for extended sessions
- **Literata**: Google's serif typeface designed for long-form reading

**Benefits:**
- 📉 **90% smaller EPUB files** (950KB vs 8.8MB) with font selection
- 🎯 **Personalized defaults** - Set preferences once, use everywhere
- ⚡ **Optimized typography** - Professional fonts designed for reading

## 📖 Documentation

* **[Complete Usage Guide](docs/USAGE.md)** - Comprehensive usage instructions
* **[Font Selection Guide](docs/FONT_SELECTION.md)** - Typography and font options
* **[User Configuration Guide](docs/USER_CONFIGURATION.md)** - Personalized preferences
* **[Configuration Guide](docs/CONFIGURATION.md)** - All configuration options
* **[Cache System Guide](docs/CACHE_SYSTEM.md)** - HTTP caching and performance optimization
* **[Cache Quick Reference](docs/CACHE_QUICK_REFERENCE.md)** - Essential cache commands and tips
* **[Provider Development](docs/PROVIDER_DEVELOPMENT.md)** - Adding new novel sources
* **[EPUB Generation](docs/EPUB_GENERATION.md)** - EPUB creation and customization
* **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## 🎯 Key Features

### Dual EPUB Generation System

* **Pandoc** (Primary): Professional-grade EPUB generation with advanced features
* **EbookLib** (Fallback): Handles large novels (2000+ chapters) that cause Pandoc to fail

### Smart Provider System

* Auto-detection of novel sources
* Modular provider architecture
* Easy to extend with new sites

### Optimized for Novels

* Removed unnecessary monospace fonts (67-94% smaller files)
* Beautiful Bitter typography for excellent reading
* Complete table of contents for easy navigation

### Intelligent Caching System

* **HTTP Response Caching** - Automatic caching of web pages and API responses
* **Performance Boost** - 50x+ faster scraping for cached content
* **Smart Compression** - 60-80% storage space reduction with gzip compression
* **Cache Validation** - ETag and Last-Modified header support for fresh content
* **Provider-Specific Settings** - Customizable cache behavior per novel source
* **CLI Management** - Easy cache monitoring and management tools

```bash
# View cache status and statistics
wn-dl cache status

# Clear cache when needed
wn-dl cache clear

# View cache configuration
wn-dl cache config
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Novels    │───▶│   wn-dl Scraper  │───▶│   EPUB Files    │
│                 │    │                  │    │                 │
│ • NovelFull     │    │ • Provider System│    │ • Pandoc (High  │
│ • NovelFire     │    │ • Rate Limiting  │    │   Quality)      │
│ • NovelBin      │    │ • Progress Track │    │ • EbookLib      │
│ • RoyalRoad     │    │ • Error Recovery │    │   (Large Novels)│
│ • Custom Sites  │    │ • Concurrent Proc│    │ • Font Support  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/wongpinter/webnovel-scraper.git
cd webnovel-scraper

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e ".[dev]"
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

* **Pandoc** - Primary EPUB generation engine
* **EbookLib** - Fallback EPUB generation for large novels
* **Bitter Fonts** - Beautiful typography for novel reading
* **Rich** - Beautiful terminal UI and progress tracking

## 📊 Project Status

✅ **Stable** - Ready for production use with comprehensive EPUB generation capabilities.

---

**Made with ❤️ for web novel readers everywhere**
