"""
Unit tests for font manager functionality.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from wn_dl.core.font_manager import (
    FontVariant,
    FontFamily,
    FontManager,
    get_font_manager,
)


class TestFontVariant:
    """Test FontVariant class."""
    
    def test_font_variant_creation(self):
        """Test creating a font variant."""
        file_path = Path("/test/font.ttf")
        variant = FontVariant("regular", "normal", 400, file_path)
        
        assert variant.style == "regular"
        assert variant.variant == "normal"
        assert variant.weight == 400
        assert variant.file_path == file_path
    
    def test_font_variant_str(self):
        """Test string representation of font variant."""
        file_path = Path("/test/font.ttf")
        variant = FontVariant("italic", "italic", 400, file_path)
        
        assert str(variant) == "italic (weight: 400)"


class TestFontFamily:
    """Test FontFamily class."""
    
    def test_font_family_creation(self):
        """Test creating a font family."""
        family = FontFamily("Test Font", "test-font")
        
        assert family.display_name == "Test Font"
        assert family.css_name == "test-font"
        assert family.variants == {}
    
    def test_add_variant(self):
        """Test adding a variant to font family."""
        family = FontFamily("Test Font", "test-font")
        file_path = Path("/test/font.ttf")
        variant = FontVariant("regular", "normal", 400, file_path)
        
        family.add_variant("regular", variant)
        
        assert "regular" in family.variants
        assert family.variants["regular"] == variant
    
    def test_has_variant(self):
        """Test checking if family has variant."""
        family = FontFamily("Test Font", "test-font")
        file_path = Path("/test/font.ttf")
        variant = FontVariant("regular", "normal", 400, file_path)
        
        family.add_variant("regular", variant)
        
        assert family.has_variant("regular")
        assert not family.has_variant("bold")
    
    def test_is_complete(self):
        """Test checking if font family is complete."""
        family = FontFamily("Test Font", "test-font")
        
        # Empty family is not complete
        assert not family.is_complete()
        
        # Add all required variants
        for style in ["regular", "bold", "italic", "bold-italic"]:
            file_path = Path(f"/test/font-{style}.ttf")
            variant = FontVariant(style, "normal", 400, file_path)
            family.add_variant(style, variant)
        
        assert family.is_complete()
    
    def test_get_variant_count(self):
        """Test getting variant count."""
        family = FontFamily("Test Font", "test-font")
        
        assert family.get_variant_count() == 0
        
        file_path = Path("/test/font.ttf")
        variant = FontVariant("regular", "normal", 400, file_path)
        family.add_variant("regular", variant)
        
        assert family.get_variant_count() == 1


class TestFontManager:
    """Test FontManager class."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.fonts_dir = self.temp_dir / "fonts"
        self.fonts_dir.mkdir()
        
        # Create test font files
        self.create_test_fonts()
        
        # Create font manager with test directory
        self.font_manager = FontManager(self.fonts_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def create_test_fonts(self):
        """Create test font files."""
        # Create Bitter font family
        bitter_files = [
            "Bitter-Regular.ttf",
            "Bitter-Bold.ttf", 
            "Bitter-Italic.ttf",
            "Bitter-BoldItalic.ttf"
        ]
        
        for font_file in bitter_files:
            (self.fonts_dir / font_file).touch()
        
        # Create incomplete Bookerly family (missing italic)
        bookerly_files = [
            "Bookerly-Regular.ttf",
            "Bookerly-Bold.ttf",
            "Bookerly-BoldItalic.ttf"
        ]
        
        for font_file in bookerly_files:
            (self.fonts_dir / font_file).touch()
    
    def test_font_manager_initialization(self):
        """Test font manager initialization."""
        assert self.font_manager.fonts_directory == self.fonts_dir
        assert isinstance(self.font_manager.font_families, dict)
    
    def test_discover_fonts(self):
        """Test font discovery."""
        self.font_manager.discover_fonts()
        
        # Should find Bitter and Bookerly families
        assert "bitter" in self.font_manager.font_families
        assert "bookerly" in self.font_manager.font_families
        
        # Check Bitter family is complete
        bitter_family = self.font_manager.font_families["bitter"]
        assert bitter_family.is_complete()
        
        # Check Bookerly family is incomplete
        bookerly_family = self.font_manager.font_families["bookerly"]
        assert not bookerly_family.is_complete()
    
    def test_get_available_fonts(self):
        """Test getting available fonts."""
        self.font_manager.discover_fonts()
        available = self.font_manager.get_available_fonts()
        
        assert "bitter" in available
        assert "bookerly" in available
        assert len(available) == 2
    
    def test_is_font_available(self):
        """Test checking font availability."""
        self.font_manager.discover_fonts()
        
        assert self.font_manager.is_font_available("bitter")
        assert self.font_manager.is_font_available("bookerly")
        assert not self.font_manager.is_font_available("nonexistent")
    
    def test_get_font_family(self):
        """Test getting font family."""
        self.font_manager.discover_fonts()
        
        bitter_family = self.font_manager.get_font_family("bitter")
        assert bitter_family is not None
        assert bitter_family.display_name == "Bitter"
        
        nonexistent = self.font_manager.get_font_family("nonexistent")
        assert nonexistent is None
    
    def test_resolve_font(self):
        """Test font resolution."""
        self.font_manager.discover_fonts()
        
        # Exact match
        assert self.font_manager.resolve_font("bitter") == "bitter"
        
        # Case insensitive
        assert self.font_manager.resolve_font("BITTER") == "bitter"
        assert self.font_manager.resolve_font("Bitter") == "bitter"
        
        # Fallback to default
        assert self.font_manager.resolve_font("nonexistent") == "bitter"
        assert self.font_manager.resolve_font(None) == "bitter"
    
    def test_get_font_info(self):
        """Test getting font information."""
        self.font_manager.discover_fonts()
        
        info = self.font_manager.get_font_info()
        
        assert len(info) == 2
        assert any(font["name"] == "bitter" for font in info)
        assert any(font["name"] == "bookerly" for font in info)
        
        # Check bitter font info
        bitter_info = next(font for font in info if font["name"] == "bitter")
        assert bitter_info["display_name"] == "Bitter"
        assert bitter_info["complete"] is True
        assert bitter_info["variant_count"] == 4
        
        # Check bookerly font info
        bookerly_info = next(font for font in info if font["name"] == "bookerly")
        assert bookerly_info["display_name"] == "Bookerly"
        assert bookerly_info["complete"] is False
        assert bookerly_info["variant_count"] == 3
    
    def test_validate_font_files(self):
        """Test font file validation."""
        self.font_manager.discover_fonts()
        
        # All files should exist since we created them
        bitter_family = self.font_manager.get_font_family("bitter")
        for variant in bitter_family.variants.values():
            assert variant.file_path.exists()


class TestGlobalFontManager:
    """Test global font manager functions."""
    
    @patch('wn_dl.core.font_manager.FontManager')
    def test_get_font_manager_singleton(self, mock_font_manager_class):
        """Test that get_font_manager returns singleton."""
        mock_instance = MagicMock()
        mock_font_manager_class.return_value = mock_instance
        
        # Clear any existing instance
        import wn_dl.core.font_manager
        wn_dl.core.font_manager._font_manager = None
        
        # First call should create instance
        manager1 = get_font_manager()
        assert manager1 == mock_instance
        
        # Second call should return same instance
        manager2 = get_font_manager()
        assert manager2 == mock_instance
        assert manager1 is manager2
        
        # Should only create FontManager once
        mock_font_manager_class.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
