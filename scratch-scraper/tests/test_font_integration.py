"""
Integration tests for font selection with EPUB generation.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import zipfile

from wn_dl.core.epub_generator import EPUBGenerator
from wn_dl.core.font_manager import get_font_manager
from wn_dl.core.user_config import get_user_config_manager


class TestFontEPUBIntegration:
    """Test font selection integration with EPUB generation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir()
        
        # Create test markdown content
        self.test_markdown = """---
title: "Test Novel"
author: "Test Author"
description: "A test novel for font integration testing"
---

# Chapter 1: The Beginning

This is a test chapter with **bold text** and *italic text*.

## Section 1.1

Regular paragraph text for testing font rendering.

> This is a blockquote to test different text styles.

# Chapter 2: Font Testing

Testing different typography:

1. Numbered list item
2. Another numbered item

- Bullet point
- Another bullet point

**Bold text** and *italic text* and ***bold italic text***.
"""
        
        self.markdown_file = self.temp_dir / "test_novel.md"
        with open(self.markdown_file, 'w', encoding='utf-8') as f:
            f.write(self.test_markdown)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_epub_generation_with_bitter_font(self):
        """Test EPUB generation with Bitter font."""
        config = {
            "epub": {
                "font_family": "bitter",
                "use_ebooklib": True,
                "include_toc": True
            }
        }
        
        generator = EPUBGenerator(config)
        
        # Generate EPUB
        epub_path = generator.generate_epub_from_markdown(
            input_file=self.markdown_file,
            output_dir=self.output_dir,
            title="Test Novel",
            author="Test Author"
        )
        
        assert epub_path is not None
        assert epub_path.exists()
        assert epub_path.suffix == ".epub"
        
        # Verify EPUB contains Bitter fonts
        self._verify_epub_fonts(epub_path, "Bitter")
    
    def test_epub_generation_with_bookerly_font(self):
        """Test EPUB generation with Bookerly font."""
        config = {
            "epub": {
                "font_family": "bookerly",
                "use_ebooklib": True,
                "include_toc": True
            }
        }
        
        generator = EPUBGenerator(config)
        
        # Generate EPUB
        epub_path = generator.generate_epub_from_markdown(
            input_file=self.markdown_file,
            output_dir=self.output_dir,
            title="Test Novel",
            author="Test Author"
        )
        
        assert epub_path is not None
        assert epub_path.exists()
        
        # Verify EPUB contains Bookerly fonts
        self._verify_epub_fonts(epub_path, "Bookerly")
    
    def test_epub_generation_with_invalid_font_fallback(self):
        """Test EPUB generation with invalid font falls back to default."""
        config = {
            "epub": {
                "font_family": "nonexistent-font",
                "use_ebooklib": True,
                "include_toc": True
            }
        }
        
        generator = EPUBGenerator(config)
        
        # Generate EPUB (should fallback to Bitter)
        epub_path = generator.generate_epub_from_markdown(
            input_file=self.markdown_file,
            output_dir=self.output_dir,
            title="Test Novel",
            author="Test Author"
        )
        
        assert epub_path is not None
        assert epub_path.exists()
        
        # Should contain Bitter fonts (default fallback)
        self._verify_epub_fonts(epub_path, "Bitter")
    
    def test_css_generation_with_font_selection(self):
        """Test CSS generation includes correct font references."""
        from wn_dl.core.css_generator import CSSGenerator
        
        # Test Bitter font CSS
        css_generator = CSSGenerator()
        bitter_css = css_generator.generate_css_for_font("bitter")
        
        assert bitter_css is not None
        assert "font-family: \"Bitter\"" in bitter_css
        assert "Bitter-Regular.ttf" in bitter_css
        assert "Bitter-Bold.ttf" in bitter_css
        assert "Bitter-Italic.ttf" in bitter_css
        assert "Bitter-BoldItalic.ttf" in bitter_css
        
        # Test Bookerly font CSS
        bookerly_css = css_generator.generate_css_for_font("bookerly")
        
        assert bookerly_css is not None
        assert "font-family: \"Bookerly\"" in bookerly_css
        assert "Bookerly-Regular.ttf" in bookerly_css
        assert "Bookerly-Bold.ttf" in bookerly_css
        assert "Bookerly-Italic.ttf" in bookerly_css
        assert "Bookerly-BoldItalic.ttf" in bookerly_css
    
    def test_font_manager_integration(self):
        """Test font manager integration with EPUB generation."""
        font_manager = get_font_manager()
        
        # Verify fonts are available
        available_fonts = font_manager.get_available_fonts()
        assert "bitter" in available_fonts
        assert "bookerly" in available_fonts
        
        # Test font resolution
        assert font_manager.resolve_font("bitter") == "bitter"
        assert font_manager.resolve_font("BITTER") == "bitter"
        assert font_manager.resolve_font("Bitter") == "bitter"
        assert font_manager.resolve_font("bookerly") == "bookerly"
        assert font_manager.resolve_font("invalid") == "bitter"  # fallback
    
    @patch('wn_dl.core.user_config.get_user_preferences')
    def test_user_config_font_integration(self, mock_get_preferences):
        """Test user configuration font preferences integration."""
        # Mock user preferences
        mock_preferences = MagicMock()
        mock_preferences.font_family = "bookerly"
        mock_preferences.preferred_generator = "ebooklib"
        mock_get_preferences.return_value = mock_preferences
        
        # Test that user preferences are used
        user_config_manager = get_user_config_manager()
        preferences = user_config_manager.get_preferences()
        
        # Should use mocked preferences
        assert preferences.font_family == "bookerly"
        assert preferences.preferred_generator == "ebooklib"
    
    def test_font_file_size_optimization(self):
        """Test that font selection reduces EPUB file size."""
        # Generate EPUB with all fonts (should be larger)
        config_all_fonts = {
            "epub": {
                "font_family": "bitter",
                "use_ebooklib": True,
                "include_toc": True
            }
        }
        
        # Generate EPUB with selected font only
        config_selected_font = {
            "epub": {
                "font_family": "bitter", 
                "use_ebooklib": True,
                "include_toc": True
            }
        }
        
        generator = EPUBGenerator(config_selected_font)
        
        epub_path = generator.generate_epub_from_markdown(
            input_file=self.markdown_file,
            output_dir=self.output_dir,
            title="Test Novel",
            author="Test Author"
        )
        
        assert epub_path.exists()
        
        # Verify only selected font family is included
        with zipfile.ZipFile(epub_path, 'r') as epub_zip:
            font_files = [f for f in epub_zip.namelist() if f.endswith('.ttf')]
            
            # Should only contain Bitter fonts
            bitter_fonts = [f for f in font_files if 'Bitter' in f]
            other_fonts = [f for f in font_files if 'Bitter' not in f]
            
            assert len(bitter_fonts) == 4  # Regular, Bold, Italic, BoldItalic
            assert len(other_fonts) == 0   # No other font families
    
    def _verify_epub_fonts(self, epub_path: Path, expected_font_family: str):
        """Verify EPUB contains expected font family."""
        with zipfile.ZipFile(epub_path, 'r') as epub_zip:
            # Check for font files
            font_files = [f for f in epub_zip.namelist() if f.endswith('.ttf')]
            expected_fonts = [f for f in font_files if expected_font_family in f]
            
            assert len(expected_fonts) >= 4, f"Expected at least 4 {expected_font_family} font files"
            
            # Check CSS contains font references
            css_files = [f for f in epub_zip.namelist() if f.endswith('.css')]
            if css_files:
                css_content = epub_zip.read(css_files[0]).decode('utf-8')
                assert f'font-family: "{expected_font_family}"' in css_content
    
    def test_cli_font_option_integration(self):
        """Test CLI font option integration."""
        from wn_dl.cli import _convert_config_value, _validate_config_key
        
        # Test config value conversion
        assert _convert_config_value("bitter") == "bitter"
        assert _convert_config_value("true") is True
        assert _convert_config_value("false") is False
        assert _convert_config_value("10") == 10
        assert _convert_config_value("1.5") == 1.5
        
        # Test config key validation
        assert _validate_config_key("font.default_family") is True
        assert _validate_config_key("epub.preferred_generator") is True
        assert _validate_config_key("invalid.key") is False


if __name__ == "__main__":
    pytest.main([__file__])
