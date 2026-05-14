# Font Selection Guide

wn-dl supports multiple font families for EPUB generation, allowing you to customize the reading experience with high-quality typography.

## Available Fonts

### Bitter (Default)
- **Type**: Contemporary serif typeface
- **Optimized for**: Screen reading and print
- **Variants**: Regular, Bold, Italic, Bold Italic
- **Best for**: General novel reading, excellent readability

### Bookerly
- **Type**: Amazon's exclusive reading font
- **Optimized for**: Fast reading with excellent character recognition
- **Variants**: Regular, Bold, Italic, Bold Italic
- **Best for**: Extended reading sessions, e-reader compatibility

### Literata
- **Type**: Contemporary serif typeface designed for long-form reading
- **Optimized for**: Digital reading, excellent legibility at various sizes
- **Variants**: Regular, Bold, Italic, Bold Italic
- **Best for**: Academic texts, literary works, professional documents

## Quick Start

### List Available Fonts
```bash
wn-dl list-fonts
```

### Use Font with Scraping
```bash
# Use Bookerly font
wn-dl scrape -u https://example.com/novel --font bookerly

# Use Bitter font (default)
wn-dl scrape -u https://example.com/novel --font bitter

# Use Literata font
wn-dl scrape -u https://example.com/novel --font literata
```

### Use Font with EPUB Generation
```bash
# Generate EPUB with specific font
wn-dl generate-epub --input novel.md --font bookerly

# Use Literata font for academic/literary works
wn-dl generate-epub --input novel.md --font literata

# Use EbookLib generator with font selection (recommended)
wn-dl generate-epub --input novel.md --font literata --use-ebooklib
```

## Font Selection Benefits

### File Size Optimization
- **Before**: 8.8MB (all fonts embedded)
- **After**: 950KB (selected font only)
- **Reduction**: 90% smaller EPUB files

### Typography Quality
- Professional font rendering
- Optimized for reading comfort
- Consistent styling across devices
- Better character recognition

## Configuration

### Set Default Font
```bash
# Set user preference
wn-dl config set font.default_family bookerly

# View current settings
wn-dl config show
```

### Configuration File
```yaml
# ~/.config/wn-dl/config.yaml
preferences:
  font:
    default_family: "bookerly"
    fallback_family: "bitter"
```

## Advanced Usage

### Font Validation
```bash
# Validate font availability
wn-dl config validate

# Check specific font
wn-dl list-fonts
```

### Fallback Behavior
- Invalid font names automatically fallback to Bitter
- Missing font files use available variants
- Graceful degradation ensures EPUB generation always succeeds

### Generator Compatibility

#### EbookLib Generator (Recommended)
- ✅ Full font selection support
- ✅ Optimized file sizes
- ✅ Perfect font embedding
- ✅ 90% file size reduction

#### Pandoc Generator
- ✅ Dynamic CSS generation
- ⚠️ Currently embeds all fonts (being fixed)
- ✅ Fallback to EbookLib available

## Troubleshooting

### Font Not Found
```bash
Warning: Font 'invalid-font' not found. Available fonts: bitter, bookerly
Using default font instead.
```

**Solution**: Use `wn-dl list-fonts` to see available options.

### Large EPUB Files
If EPUB files are unexpectedly large, use EbookLib generator:
```bash
wn-dl generate-epub --input novel.md --font bookerly --use-ebooklib
```

### Font Rendering Issues
1. Validate configuration: `wn-dl config validate`
2. Check font availability: `wn-dl list-fonts`
3. Try different font: `--font bitter` or `--font bookerly`

## Technical Details

### Font File Structure
```
src/wn_dl/templates/fonts/
├── Bitter-Regular.ttf
├── Bitter-Bold.ttf
├── Bitter-Italic.ttf
├── Bitter-BoldItalic.ttf
├── Bookerly-Regular.ttf
├── Bookerly-Bold.ttf
├── Bookerly-Italic.ttf
└── Bookerly-BoldItalic.ttf
```

### CSS Generation
Dynamic CSS is generated for each font family:
```css
@font-face {
    font-family: "Bookerly";
    font-weight: normal;
    font-style: normal;
    src: url('fonts/Bookerly-Regular.ttf');
}
/* Additional @font-face declarations for Bold, Italic, BoldItalic */

body {
    font-family: "Bookerly", serif;
}
```

### Font Embedding Process
1. **Font Selection**: User specifies font via CLI or config
2. **Validation**: System validates font availability
3. **CSS Generation**: Dynamic CSS created for selected font
4. **Font Copying**: Only selected font family files copied to EPUB
5. **EPUB Creation**: Optimized EPUB with selected typography

## Best Practices

### For Novel Reading
- **Bookerly**: Best for fiction and long-form reading
- **Bitter**: Excellent for technical content and documentation

### For File Size
- Always use `--use-ebooklib` for smallest files
- Set user preference to avoid specifying font each time

### For Compatibility
- Bitter has broader device compatibility
- Bookerly optimized for modern e-readers

## Examples

### Complete Workflow
```bash
# Set up user preferences
wn-dl config init

# Scrape with preferred settings
wn-dl scrape -u https://novelfull.com/example-novel

# Generate additional EPUB with different font
wn-dl generate-epub --input novel.md --font bitter --use-ebooklib
```

### Batch Processing
```bash
# Set default font
wn-dl config set font.default_family bookerly

# All subsequent commands use Bookerly
wn-dl scrape -u https://site1.com/novel1
wn-dl scrape -u https://site2.com/novel2
wn-dl generate-epub --input existing-novel.md
```

## Integration with User Configuration

Font selection is fully integrated with the user configuration system:

```bash
# Interactive setup includes font selection
wn-dl config init

# View all preferences including font
wn-dl config show

# Modify font preference
wn-dl config set font.default_family bookerly
```

See [USER_CONFIGURATION.md](USER_CONFIGURATION.md) for complete configuration guide.

## Related Documentation

- [User Configuration Guide](USER_CONFIGURATION.md) - Complete configuration system
- [EPUB Generation Guide](EPUB_GENERATION.md) - EPUB creation options
- [CLI Reference](CLI_REFERENCE.md) - Command-line interface guide
