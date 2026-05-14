# 📚 Documentation Index

Welcome to the wn-dl documentation! This directory contains comprehensive guides for using, configuring, and extending wn-dl.

## 📖 User Guides

### [📋 Complete Usage Guide](USAGE.md)

Comprehensive guide covering all aspects of using wn-dl, from basic commands to advanced features.

**Topics covered:**
* Installation and setup
* Scraping novels from websites
* EPUB generation options
* Configuration file usage
* Performance optimization
* Troubleshooting common issues

### [⚙️ Configuration Guide](CONFIGURATION.md)

Detailed reference for all configuration options and settings.

**Topics covered:**
* Configuration file structure
* EPUB generation settings
* Image processing options
* Provider-specific configurations
* Environment variables
* Performance tuning

### [🔧 Troubleshooting Guide](TROUBLESHOOTING.md)

Solutions for common problems and debugging techniques.

**Topics covered:**
* Installation issues
* EPUB generation problems
* Scraping failures
* Performance issues
* Debug tools and techniques

## 🛠️ Developer Guides

### [📖 EPUB Generation Guide](EPUB_GENERATION.md)

Technical guide to the dual EPUB generation system.

**Topics covered:**
* Pandoc vs EbookLib generators
* Font optimization and styling
* Table of contents generation
* Performance metrics
* eReader compatibility

### [🚀 Provider Quick Start Guide](PROVIDER_QUICK_START.md)

Quick implementation patterns for common provider types.

**Topics covered:**
* Simple HTML providers (NovelFull pattern)
* AJAX-based providers (NovelBuddy pattern)
* Circuit breaker providers (NovelBin pattern)
* Common implementation patterns
* Testing strategies

### [🔌 Provider Development Guide](PROVIDER_DEVELOPMENT.md)

Complete guide for adding support for new novel websites.

**Topics covered:**
* Provider architecture
* Implementation steps
* HTML analysis techniques
* Configuration patterns
* Testing and validation
* Advanced AJAX patterns
* NovelBuddy case study

### [🤝 Contributing Guide](CONTRIBUTING.md)

Guidelines for contributing to the wn-dl project.

**Topics covered:**
* Development setup
* Code style guidelines
* Testing requirements
* Pull request process
* Community guidelines

## 🚀 Quick Reference

### Essential Commands

```bash
# Download a novel
wn-dl scrape -u https://novelfull.com/novel-name

# Generate EPUB from markdown
wn-dl generate-epub --input novel.md

# Show detailed logging
wn-dl --with-info [command]

# Check system status
wn-dl info
```

### Key Features

* **🌐 Multi-Provider Support** - NovelFull, NovelBin, and more
* **📖 Dual EPUB Generation** - Pandoc (quality) + EbookLib (large novels)
* **🎨 Professional Typography** - Optimized fonts and styling
* **⚡ High Performance** - Concurrent processing with progress tracking
* **🔧 Highly Configurable** - Extensive customization options

## 📋 Documentation Standards

All documentation follows these principles:

* **Clear structure** with logical organization
* **Practical examples** for all features
* **Troubleshooting sections** for common issues
* **Cross-references** between related topics
* **Regular updates** to match current features

## 🔗 External Resources

* **[GitHub Repository](https://github.com/wongpinter/webnovel-scraper)** - Source code and issues
* **[PyPI Package](https://pypi.org/project/wn-dl/)** - Package installation
* **[Pandoc Documentation](https://pandoc.org/MANUAL.html)** - EPUB generation reference
* **[EbookLib Documentation](https://ebooklib.readthedocs.io/)** - Alternative EPUB library

---

**Need help?** Start with the [Usage Guide](USAGE.md) or check the [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues.
