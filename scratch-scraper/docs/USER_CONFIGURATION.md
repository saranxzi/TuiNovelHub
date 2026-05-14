# User Configuration Guide

wn-dl features a comprehensive user configuration system that allows you to set personalized preferences for all aspects of the application. Set your preferences once and have them automatically applied to all commands.

## Quick Start

### Initialize Configuration
```bash
# Interactive setup with prompts
wn-dl config init

# View current configuration
wn-dl config show

# Modify specific settings
wn-dl config set font.default_family bookerly
wn-dl config set directories.output ~/novels
```

## Configuration Commands

### `wn-dl config init`
Interactive configuration setup with prompts for all major preferences.

```bash
wn-dl config init
# Prompts for: font, logging, directories, EPUB generator

wn-dl config init --force
# Overwrite existing configuration
```

### `wn-dl config show`
Display current configuration in a beautiful table format.

```bash
wn-dl config show
```

### `wn-dl config set <key> <value>`
Modify individual configuration values.

```bash
# Font preferences
wn-dl config set font.default_family bookerly
wn-dl config set font.fallback_family bitter

# Logging preferences  
wn-dl config set logging.level INFO
wn-dl config set logging.file ~/wn-dl.log

# Directory preferences
wn-dl config set directories.output ~/Documents/Novels
wn-dl config set directories.input ~/Downloads
wn-dl config set directories.auto_create true

# EPUB generator preferences
wn-dl config set epub.preferred_generator ebooklib
wn-dl config set epub.fallback_enabled true
wn-dl config set epub.include_toc true

# Processing preferences
wn-dl config set processing.max_workers 8
wn-dl config set processing.rate_limit 0.3
wn-dl config set processing.timeout 45
```

### `wn-dl config reset`
Reset configuration to defaults.

```bash
wn-dl config reset
# Prompts for confirmation

wn-dl config reset --confirm
# Skip confirmation prompt
```

### `wn-dl config validate`
Validate current configuration for errors.

```bash
wn-dl config validate
```

## Configuration File

### Location
- **Linux/Unix**: `~/.config/wn-dl/config.yaml`
- **Windows**: `%APPDATA%/wn-dl/config.yaml`
- **macOS**: `~/Library/Application Support/wn-dl/config.yaml`
- **Alternative**: `~/.wn-dl/config.yaml` (all platforms)

### Structure
```yaml
preferences:
  # Font Preferences
  font:
    default_family: "bookerly"     # Primary font family
    fallback_family: "bitter"      # Fallback if primary unavailable
    
  # Logging Preferences
  logging:
    level: "INFO"                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: null                     # Log file path (null = console only)
    
  # Directory Preferences
  directories:
    output: "~/Documents/Novels"   # Default output directory
    input: "~/Downloads"           # Default input directory
    working: null                  # Temporary working directory
    auto_create: true              # Auto-create directories
    
  # EPUB Generator Preferences
  epub:
    preferred_generator: "ebooklib"  # pandoc or ebooklib
    fallback_enabled: true           # Enable automatic fallback
    include_toc: true                # Include table of contents
    compression: false               # Enable EPUB compression
    
  # Processing Preferences
  processing:
    max_workers: 10                # Concurrent workers
    rate_limit: 0.5                # Requests per second
    timeout: 30                    # Request timeout (seconds)
    
  # Provider-Specific Preferences
  providers:
    novelfull:
      rate_limit: 0.5
      max_workers: 5
    novelbin:
      rate_limit: 0.2
      max_workers: 3
      
  # Image Preferences
  images:
    download_covers: true          # Download cover images
    quality: 85                    # JPEG quality (1-100)
    format: "JPEG"                 # Image format
```

## Preference Categories

### Font Preferences
Control typography and font selection for EPUB generation.

- `font.default_family`: Primary font (bitter, bookerly)
- `font.fallback_family`: Fallback font if primary unavailable

### Logging Preferences
Control application logging and verbosity.

- `logging.level`: Log verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logging.format`: Log message format
- `logging.file`: Log file path (null for console only)

### Directory Preferences
Set default directories for input and output.

- `directories.output`: Default output directory for scraping
- `directories.input`: Default input directory for EPUB generation
- `directories.working`: Temporary working directory
- `directories.auto_create`: Automatically create missing directories

### EPUB Generator Preferences
Choose between Pandoc and EbookLib for EPUB generation.

- `epub.preferred_generator`: Primary generator (pandoc, ebooklib)
- `epub.fallback_enabled`: Enable automatic fallback
- `epub.include_toc`: Include table of contents
- `epub.compression`: Enable EPUB compression (EbookLib only)

### Processing Preferences
Control performance and rate limiting.

- `processing.max_workers`: Maximum concurrent workers
- `processing.rate_limit`: Requests per second
- `processing.timeout`: Request timeout in seconds

### Provider-Specific Preferences
Customize settings for specific novel websites.

- `providers.<site>.rate_limit`: Custom rate limit
- `providers.<site>.max_workers`: Custom worker count
- `providers.<site>.timeout`: Custom timeout

### Image Preferences
Control cover image downloading and processing.

- `images.download_covers`: Download cover images
- `images.quality`: JPEG quality (1-100)
- `images.format`: Image format (JPEG, PNG, WEBP)

## Configuration Precedence

Settings are applied in this order (highest to lowest priority):

1. **CLI Arguments** (highest priority)
2. **User Configuration** (`~/.config/wn-dl/config.yaml`)
3. **Project Configuration** (`./config/temp_config.yaml`)
4. **Built-in Defaults** (lowest priority)

### Example
```bash
# User config sets font to "bookerly"
# CLI argument overrides to "bitter"
wn-dl scrape -u URL --font bitter
# Result: Uses Bitter font
```

## Integration with Commands

### Automatic Defaults
All CLI commands automatically use your user preferences as defaults:

```bash
# Uses your configured font, output directory, generator, etc.
wn-dl scrape -u https://example.com/novel

# Uses your configured input directory, font, generator, etc.
wn-dl generate-epub --input novel.md
```

### Override When Needed
CLI arguments still override user preferences:

```bash
# Override font for this command only
wn-dl scrape -u URL --font bitter --output ./special-project
```

## Advanced Configuration

### Cross-Platform Compatibility
Configuration automatically adapts to your operating system:
- Follows XDG Base Directory Specification on Linux
- Uses AppData on Windows
- Follows macOS conventions

### Atomic Updates
Configuration changes are atomic and safe:
- Automatic backups before changes
- Rollback on errors
- Validation before saving

### Migration Support
Configuration automatically migrates between versions:
- Backward compatibility maintained
- New settings added with sensible defaults
- Invalid settings cleaned up

## Examples

### Complete Setup Workflow
```bash
# 1. Initialize configuration
wn-dl config init

# 2. Customize specific preferences
wn-dl config set font.default_family bookerly
wn-dl config set directories.output ~/novels
wn-dl config set epub.preferred_generator ebooklib

# 3. Validate configuration
wn-dl config validate

# 4. View final settings
wn-dl config show
```

### Daily Usage
```bash
# Commands automatically use your preferences
wn-dl scrape -u https://novelfull.com/example-novel
wn-dl generate-epub --input existing-novel.md

# Override when needed
wn-dl scrape -u URL --font bitter --output ./temp
```

### Batch Configuration
```bash
# Set multiple preferences
wn-dl config set font.default_family bookerly
wn-dl config set logging.level DEBUG
wn-dl config set processing.max_workers 8
wn-dl config set epub.preferred_generator ebooklib

# Verify all settings
wn-dl config show
```

## Troubleshooting

### Configuration Not Found
```bash
No user configuration file found.
Run 'wn-dl config init' to create one.
```
**Solution**: Run `wn-dl config init` to create initial configuration.

### Invalid Configuration
```bash
❌ Configuration has issues:
  • Font 'invalid-font' is not available
  • Invalid log level: INVALID
```
**Solution**: Run `wn-dl config validate` and fix reported issues.

### Permission Errors
If you can't write to the config directory:
1. Check directory permissions
2. Try alternative location: `~/.wn-dl/config.yaml`
3. Run with appropriate permissions

### Reset Configuration
```bash
# Reset to defaults if configuration is corrupted
wn-dl config reset --confirm
```

## Related Documentation

- [Font Selection Guide](FONT_SELECTION.md) - Typography and font options
- [EPUB Generation Guide](EPUB_GENERATION.md) - EPUB creation options
- [CLI Reference](CLI_REFERENCE.md) - Command-line interface guide
