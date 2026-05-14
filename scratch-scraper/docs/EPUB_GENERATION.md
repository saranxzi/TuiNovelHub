# 📖 EPUB Generation Guide

This guide covers the dual EPUB generation system in wn-dl, including Pandoc and EbookLib generators, optimization techniques, and troubleshooting.

## 🏗️ Dual Generation System

wn-dl features a sophisticated dual EPUB generation system designed to handle novels of all sizes:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Markdown      │───▶│   Generator      │───▶│   EPUB File     │
│   Input         │    │   Selection      │    │   Output        │
│                 │    │                  │    │                 │
│ • Novel content │    │ ┌──────────────┐ │    │ • Professional │
│ • Metadata      │    │ │   Pandoc     │ │    │   formatting   │
│ • Chapter data  │    │ │  (Primary)   │ │    │ • Table of     │
│                 │    │ └──────────────┘ │    │   contents     │
│                 │    │ ┌──────────────┐ │    │ • Embedded     │
│                 │    │ │  EbookLib    │ │    │   fonts        │
│                 │    │ │ (Fallback)   │ │    │ • Optimized    │
│                 │    │ └──────────────┘ │    │   file size    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🎯 Generator Selection

### Automatic Selection

The system automatically chooses the best generator based on:

1. **Configuration**: `use_ebooklib` setting
2. **Pandoc availability**: System check for Pandoc installation
3. **File size**: Automatic fallback for large novels
4. **Memory constraints**: EbookLib for memory-limited environments

```bash
# Automatic selection (recommended)
wn-dl generate-epub --input novel.md
```

### Manual Selection

```bash
# Force Pandoc (high quality)
wn-dl generate-epub --input novel.md --no-fallback

# Force EbookLib (large novels)
wn-dl generate-epub --input novel.md --use-ebooklib
```

## 📚 Pandoc Generator (Primary)

### Features

- ✅ **Professional typography** - Advanced font handling and spacing
- ✅ **Rich metadata support** - Complete Dublin Core metadata
- ✅ **Advanced CSS** - Complex styling and layout options
- ✅ **Standards compliance** - Full EPUB 3.0 specification
- ✅ **Plugin ecosystem** - Extensible with Pandoc filters

### Best For

- **Small to medium novels** (< 1000 chapters)
- **High-quality output** requirements
- **Complex formatting** needs
- **Standard EPUB features**

### Usage

```bash
# Basic Pandoc generation
wn-dl generate-epub --input novel.md

# With custom Pandoc arguments
wn-dl generate-epub --input novel.md --config pandoc-config.yaml
```

### Configuration

```yaml
epub:
  use_ebooklib: false  # Use Pandoc
  pandoc_args:
    - "--epub-chapter-level=2"
    - "--epub-cover-image=cover.jpg"
    - "--epub-metadata=metadata.xml"
```

### Limitations

- **Memory usage**: Exponential growth with file size
- **Large file issues**: Fails on 50MB+ markdown files
- **Processing time**: Slower for very large novels
- **System dependency**: Requires Pandoc installation

## ⚡ EbookLib Generator (Fallback)

### Features

- ✅ **Memory efficient** - Linear memory usage (~5x input size)
- ✅ **Large file support** - Handles 2000+ chapter novels
- ✅ **Fast processing** - ~1.6 MB/second throughput
- ✅ **Progress tracking** - Real-time progress bars
- ✅ **Automatic fallback** - Seamless when Pandoc fails
- ✅ **Font optimization** - Removed unnecessary monospace fonts

### Best For

- **Large novels** (1000+ chapters)
- **Memory-constrained environments**
- **Batch processing** of multiple novels
- **Automated workflows**

### Usage

```bash
# Force EbookLib usage
wn-dl generate-epub --input large-novel.md --use-ebooklib

# Silent mode with progress bar only
wn-dl generate-epub --input novel.md --use-ebooklib --silent
```

### Configuration

```yaml
epub:
  use_ebooklib: true
  ebooklib_compression: false
  ebooklib_validation: false
  include_toc: true
```

### Performance Metrics

| Novel Size | Chapters | Processing Time | Memory Usage | Output Size |
|------------|----------|-----------------|--------------|-------------|
| Small      | 50       | 2-5 seconds     | 50-100 MB    | 0.5-2 MB    |
| Medium     | 500      | 10-30 seconds   | 100-300 MB   | 2-8 MB      |
| Large      | 2000     | 30-120 seconds  | 300-800 MB   | 8-20 MB     |

## 🎨 Styling and Fonts

### Font System

The EPUB generator includes optimized font embedding:

```
Fonts Included:
├── Bitter-Regular.ttf     (Body text)
├── Bitter-Bold.ttf        (Headings, emphasis)
├── Bitter-Italic.ttf      (Italics)
└── Bitter-BoldItalic.ttf  (Bold italics)

Fonts Removed (for novels):
├── FiraCode-* (Monospace fonts)
└── Other code fonts
```

### File Size Impact

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| **Fonts** | 13 MB  | 0.7 MB| 94%       |
| **Total** | 10.7 MB| 3.5 MB| 67%       |

### CSS Optimization

```css
/* Novel-optimized CSS */
body {
    font-family: "Bitter", serif;
    line-height: 1.6;
    text-align: justify;
}

h1, h2, h3 {
    font-family: "Bitter", serif;
    font-weight: bold;
    page-break-before: always;
}

/* Monospace fallback (no embedded fonts) */
code, pre {
    font-family: "Courier New", monospace;
}
```

## 📑 Table of Contents

### TOC Generation

Both generators create comprehensive table of contents:

- **NCX TOC** - EPUB 2.0 compatibility
- **Navigation Document** - EPUB 3.0 standard
- **Chapter linking** - Direct chapter navigation
- **Hierarchical structure** - Nested chapter organization

### TOC Configuration

```yaml
epub:
  include_toc: true
  chapter_level: 2  # H2 headings become chapters
```

### TOC Features

```bash
# Enable TOC (default)
wn-dl generate-epub --input novel.md

# Disable TOC (faster generation)
wn-dl generate-epub --input novel.md --no-toc
```

## 🔧 Advanced Features

### Progress Tracking

```bash
# Verbose mode with detailed progress
wn-dl --with-info generate-epub --input novel.md --use-ebooklib

# Silent mode with progress bar only
wn-dl generate-epub --input novel.md --use-ebooklib --silent
```

### Custom CSS

```bash
# Use custom CSS file
wn-dl generate-epub --input novel.md --css custom-style.css

# Disable custom CSS
wn-dl generate-epub --input novel.md --config no-css-config.yaml
```

### Metadata Handling

```yaml
# Embedded in markdown YAML frontmatter
---
title: "My Novel"
author: "Author Name"
description: "Novel description"
cover_path: "/path/to/cover.jpg"
epub-css: "custom-style.css"
---
```

## 🐛 Troubleshooting

### Common Issues

1. **Pandoc Memory Error**
   ```bash
   # Solution: Use EbookLib
   wn-dl generate-epub --input large-novel.md --use-ebooklib
   ```

2. **Empty EPUB Content**
   ```bash
   # Check chapter encoding
   wn-dl --with-info generate-epub --input novel.md
   ```

3. **Missing TOC**
   ```bash
   # Ensure TOC is enabled
   wn-dl generate-epub --input novel.md --config toc-enabled.yaml
   ```

4. **Large File Size**
   ```bash
   # Use optimized settings
   wn-dl generate-epub --input novel.md --use-ebooklib
   ```

### Debug Mode

```bash
# Enable detailed logging
wn-dl --with-info generate-epub --input novel.md

# Test with small sample
head -n 100 large-novel.md > test-novel.md
wn-dl generate-epub --input test-novel.md
```

## 📊 Performance Optimization

### For Small Novels (< 100 chapters)

```bash
# Use Pandoc for best quality
wn-dl generate-epub --input novel.md --no-fallback
```

### For Medium Novels (100-1000 chapters)

```bash
# Auto-selection works best
wn-dl generate-epub --input novel.md
```

### For Large Novels (1000+ chapters)

```bash
# Force EbookLib for reliability
wn-dl generate-epub --input novel.md --use-ebooklib --silent
```

### Batch Processing

```bash
# Process multiple novels efficiently
for novel in *.md; do
    wn-dl generate-epub --input "$novel" --use-ebooklib --silent
done
```

## 🎯 Best Practices

1. **Test with small samples** before processing large novels
2. **Use EbookLib for novels > 1000 chapters**
3. **Enable TOC for better navigation**
4. **Monitor memory usage** during generation
5. **Keep markdown backups** before EPUB generation
6. **Validate EPUBs** with epubcheck when possible
7. **Use silent mode** for automated workflows

## 📱 eReader Compatibility

Generated EPUBs are tested and optimized for:

- ✅ **Kindle** (via Calibre conversion)
- ✅ **Kobo Clara/Libra/Sage**
- ✅ **Apple Books** (iOS/macOS)
- ✅ **Google Play Books**
- ✅ **Adobe Digital Editions**
- ✅ **Calibre** (all formats)
- ✅ **Moon+ Reader** (Android)
- ✅ **FBReader** (cross-platform)

### Validation

```bash
# Validate EPUB structure (if epubcheck available)
epubcheck generated-novel.epub

# Test in Calibre
calibre generated-novel.epub
```
