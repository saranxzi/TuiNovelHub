# ⚙️ Configuration Guide

This guide covers all configuration options available in wn-dl for customizing behavior, output formats, and processing settings.

## 📁 Configuration File Locations

Configuration files are loaded in the following order (first found wins):

1. **Command line specified**: `-c/--config path/to/config.yaml`
2. **Project config**: `./config/temp_config.yaml`
3. **Built-in defaults**: Internal default configuration

## 📝 Configuration File Format

Configuration files use YAML format with the following structure:

```yaml
# Complete configuration example
epub:
  chapter_level: 2
  include_toc: true
  custom_css: true
  use_ebooklib: false
  ebooklib_compression: false
  ebooklib_validation: false
  pandoc_args: []
  chapter_title_format: "title_only"
  chapter_number_format: "arabic"

images:
  download_covers: true
  target_size: [600, 800]
  quality: 85
  format: "JPEG"
  create_placeholder: true

processing:
  max_workers: 10
  rate_limit: 0.5
  timeout: 30

logging:
  level: "WARNING"  # Silent by default
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: null
```

## 📖 EPUB Configuration

### Basic EPUB Settings

```yaml
epub:
  # Chapter heading level (1-6)
  chapter_level: 2
  
  # Include table of contents
  include_toc: true
  
  # Use custom CSS styling
  custom_css: true
  
  # Force EbookLib usage (default: false, uses Pandoc)
  use_ebooklib: false
  
  # Additional Pandoc arguments
  pandoc_args: []
```

### Chapter Title Formatting

```yaml
epub:
  # Chapter title format options:
  # - "title_only": "The Beginning"
  # - "number_title": "1. The Beginning" 
  # - "chapter_number_title": "Chapter 1: The Beginning"
  # - "number_only": "1"
  chapter_title_format: "title_only"
  
  # Chapter number format:
  # - "arabic": 1, 2, 3
  # - "roman": i, ii, iii
  # - "roman_upper": I, II, III
  chapter_number_format: "arabic"
```

### EbookLib-Specific Settings

```yaml
epub:
  # Enable compression (reduces file size)
  ebooklib_compression: false
  
  # Validate EPUB structure
  ebooklib_validation: false
```

## 🖼️ Image Configuration

### Cover Image Settings

```yaml
images:
  # Download cover images
  download_covers: true
  
  # Target image size [width, height]
  target_size: [600, 800]
  
  # JPEG quality (1-100)
  quality: 85
  
  # Output format: "JPEG", "PNG", "WEBP"
  format: "JPEG"
  
  # Create placeholder if cover not found
  create_placeholder: true
```

### Image Processing Options

```yaml
images:
  # Resize strategy: "fit", "fill", "stretch"
  resize_strategy: "fit"
  
  # Background color for padding (hex)
  background_color: "#FFFFFF"
  
  # Enable image optimization
  optimize: true
```

## ⚡ Processing Configuration

### Concurrency Settings

```yaml
processing:
  # Maximum concurrent workers
  max_workers: 10
  
  # Rate limit (requests per second)
  rate_limit: 0.5
  
  # Request timeout (seconds)
  timeout: 30
```

### Advanced Processing

```yaml
processing:
  # Retry settings
  max_retries: 3
  retry_delay: 1.0
  
  # User agent string
  user_agent: "wn-dl/1.0"
  
  # Enable request caching
  enable_cache: false
  
  # Cache directory
  cache_dir: ".cache"
```

## 📊 Logging Configuration

### Basic Logging

```yaml
logging:
  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: "WARNING"  # Silent by default
  
  # Log format string
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # Log file path (null for console only)
  file: null
```

### Advanced Logging

```yaml
logging:
  # Enable colored output
  colored: true
  
  # Rotate log files
  rotate: true
  max_size: "10MB"
  backup_count: 5
  
  # Component-specific log levels
  components:
    scraper: "INFO"
    epub_generator: "WARNING"
    image_processor: "ERROR"
```

## 🌐 Provider Configuration

### Provider-Specific Settings

```yaml
providers:
  novelfull:
    rate_limit: 0.5
    max_workers: 5
    timeout: 30
    
  novelbin:
    rate_limit: 0.2  # Slower for stability
    max_workers: 3
    timeout: 45
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout: 60
```

### Custom Headers

```yaml
providers:
  default:
    headers:
      User-Agent: "Mozilla/5.0 (compatible; wn-dl)"
      Accept: "text/html,application/xhtml+xml"
      Accept-Language: "en-US,en;q=0.9"
```

## 🎨 Styling Configuration

### CSS Customization

```yaml
epub:
  custom_css: true
  css_file: "path/to/custom.css"
  
  # Font settings
  fonts:
    body: "Bitter"
    headings: "Bitter"
    # monospace fonts disabled for novels
```

### Typography Settings

```yaml
epub:
  typography:
    font_size: "1em"
    line_height: "1.6"
    margin: "1em"
    text_align: "justify"
```

## 🔧 Environment Variables

Override configuration with environment variables:

```bash
# Configuration file
export WN_DL_CONFIG="/path/to/config.yaml"

# Output directory
export WN_DL_OUTPUT="/path/to/novels"

# Log level
export WN_DL_LOG_LEVEL="INFO"

# Max workers
export WN_DL_MAX_WORKERS="5"

# Rate limit
export WN_DL_RATE_LIMIT="0.5"
```

## 📋 Configuration Templates

### Minimal Configuration

```yaml
# Minimal config for basic usage
epub:
  include_toc: true
  use_ebooklib: false

processing:
  max_workers: 5
  rate_limit: 0.5
```

### Large Novel Configuration

```yaml
# Optimized for large novels (1000+ chapters)
epub:
  include_toc: true
  use_ebooklib: true  # Better for large files
  ebooklib_compression: true

processing:
  max_workers: 5
  rate_limit: 0.3
  timeout: 60

logging:
  level: "INFO"  # Monitor progress
```

### High Performance Configuration

```yaml
# Maximum speed settings
epub:
  include_toc: false  # Faster generation
  use_ebooklib: true

processing:
  max_workers: 20
  rate_limit: 2.0
  timeout: 15

images:
  download_covers: false  # Skip covers for speed
```

### Conservative Configuration

```yaml
# Safe settings for unstable sites
epub:
  include_toc: true
  use_ebooklib: false

processing:
  max_workers: 1
  rate_limit: 0.1
  timeout: 60
  max_retries: 5

logging:
  level: "INFO"
```

## 🔍 Configuration Validation

### Validate Configuration

```bash
# Test configuration file
wn-dl --config my-config.yaml info

# Check specific settings
wn-dl --with-info --config my-config.yaml providers
```

### Common Configuration Errors

1. **Invalid YAML syntax**
   ```yaml
   # Wrong (missing quotes)
   epub:
     title: My Novel's Title
   
   # Correct
   epub:
     title: "My Novel's Title"
   ```

2. **Invalid values**
   ```yaml
   # Wrong (invalid log level)
   logging:
     level: "VERBOSE"
   
   # Correct
   logging:
     level: "INFO"
   ```

3. **Missing required sections**
   ```yaml
   # Minimal valid config
   epub: {}
   processing: {}
   ```

## 🎯 Best Practices

1. **Start with defaults** - Only override what you need
2. **Use environment variables** - For deployment-specific settings
3. **Validate configuration** - Test with `wn-dl info` before use
4. **Document changes** - Comment your configuration files
5. **Version control** - Keep configuration files in git
6. **Provider-specific configs** - Use different configs for different sites

## 📚 Configuration Examples

See the `config/` directory for example configurations:

- `temp_config.yaml` - Default configuration
- `large-novel-config.yaml` - Optimized for large novels
- `fast-config.yaml` - High-performance settings
- `conservative-config.yaml` - Safe, slow settings
