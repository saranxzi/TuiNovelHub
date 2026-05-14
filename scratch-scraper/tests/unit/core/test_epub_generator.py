"""
Tests for EPUBGenerator CSS and page break functionality.

Tests the CSS improvements for proper page breaks between chapters.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import subprocess

from wn_dl.core.epub_generator import EPUBGenerator


class TestEPUBGenerator:
    """Test cases for EPUBGenerator CSS and page break improvements."""

    @pytest.fixture
    def default_config(self):
        """Default configuration for testing."""
        return {
            "epub": {
                "chapter_level": 2,
                "include_toc": True,
                "custom_css": True,
                "pandoc_args": []
            }
        }

    @pytest.fixture
    def mock_pandoc_available(self):
        """Mock Pandoc availability."""
        with patch('wn_dl.core.epub_generator.EPUBGenerator._check_pandoc', return_value=True):
            yield

    def test_css_chapter_page_breaks(self, default_config, mock_pandoc_available):
        """Test that CSS contains proper page break rules for chapters."""
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Create CSS file
            css_file = generator._create_default_css(output_dir)
            
            assert css_file is not None
            assert Path(css_file).exists()
            
            # Read CSS content
            with open(css_file, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            # Check for chapter page break rules
            assert '.chapter {' in css_content
            assert 'page-break-before: always;' in css_content
            assert '-webkit-column-break-before: always;' in css_content
            assert 'break-before: page;' in css_content
            assert 'page-break-inside: avoid;' in css_content
            assert '-webkit-column-break-inside: avoid;' in css_content
            assert 'break-inside: avoid;' in css_content

    def test_css_heading_page_break_rules(self, default_config, mock_pandoc_available):
        """Test that CSS contains proper page break rules for headings."""
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            css_file = generator._create_default_css(output_dir)
            
            with open(css_file, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            # Check for heading page break rules
            assert 'h1,' in css_content
            assert 'h2,' in css_content
            assert 'h3 {' in css_content
            assert 'page-break-after: avoid;' in css_content
            assert 'page-break-inside: avoid;' in css_content

    def test_font_embedding_configuration(self, default_config, mock_pandoc_available):
        """Test that font embedding is properly configured."""
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            css_file = generator._create_default_css(output_dir)
            
            with open(css_file, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            # Check for font family declarations
            assert 'Atkinson Hyperlegible' in css_content
            assert 'FiraCode Nerd Font' in css_content or 'ComicCodeLigatures Nerd Font' in css_content

    @patch('subprocess.run')
    def test_pandoc_command_includes_css(self, mock_subprocess, default_config, mock_pandoc_available):
        """Test that Pandoc command includes CSS file."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Create a dummy markdown file
            markdown_file = output_dir / "test.md"
            markdown_file.write_text("# Test Content")
            
            # Generate EPUB
            result = generator.generate_epub(
                str(markdown_file),
                output_dir,
                "Test Novel"
            )
            
            # Check that subprocess was called
            mock_subprocess.assert_called_once()
            
            # Get the command that was called
            call_args = mock_subprocess.call_args[0][0]
            
            # Should include CSS argument
            assert "--css" in call_args
            
            # Find the CSS file path
            css_index = call_args.index("--css")
            css_file = call_args[css_index + 1]
            assert css_file.endswith(".css")

    @patch('subprocess.run')
    def test_pandoc_command_structure(self, mock_subprocess, default_config, mock_pandoc_available):
        """Test the complete Pandoc command structure."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            markdown_file = output_dir / "test.md"
            markdown_file.write_text("# Test Content")
            
            metadata = {
                "title": "Test Novel",
                "author": "Test Author",
                "description": "Test description"
            }
            
            result = generator.generate_epub(
                str(markdown_file),
                output_dir,
                "Test Novel",
                metadata=metadata
            )
            
            call_args = mock_subprocess.call_args[0][0]
            
            # Check basic Pandoc arguments
            assert "pandoc" in call_args
            assert "--from" in call_args
            assert "markdown" in call_args
            assert "--to" in call_args
            assert "epub3" in call_args
            assert "--standalone" in call_args
            
            # Check TOC arguments
            assert "--toc" in call_args
            assert "--toc-depth=2" in call_args
            
            # Check metadata arguments
            assert "--metadata" in call_args

    def test_css_file_creation_with_custom_path(self, default_config, mock_pandoc_available):
        """Test CSS file creation and content verification."""
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            css_file = generator._create_default_css(output_dir)
            
            # Verify file was created
            assert css_file is not None
            css_path = Path(css_file)
            assert css_path.exists()
            assert css_path.name == "novel.css"
            
            # Verify content is not empty
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert len(content) > 1000  # Should be substantial CSS content
            assert "@charset" in content
            assert "EPUB ENHANCED CSS" in content

    def test_epub_filename_generation(self, default_config, mock_pandoc_available):
        """Test EPUB filename generation."""
        generator = EPUBGenerator(default_config)
        
        # Test normal title
        filename = generator._generate_epub_filename("Test Novel")
        assert filename == "Test_Novel.epub"
        
        # Test title with special characters
        filename = generator._generate_epub_filename("Test: Novel & More!")
        assert filename == "Test_Novel_More.epub"
        
        # Test very long title
        long_title = "A" * 200
        filename = generator._generate_epub_filename(long_title)
        assert len(filename) <= 255  # Should be truncated for filesystem compatibility
        assert filename.endswith(".epub")

    @patch('wn_dl.core.epub_generator.EPUBGenerator._check_pandoc', return_value=False)
    def test_pandoc_not_available(self, mock_check_pandoc, default_config):
        """Test behavior when Pandoc is not available."""
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            markdown_file = output_dir / "test.md"
            markdown_file.write_text("# Test Content")
            
            result = generator.generate_epub(
                str(markdown_file),
                output_dir,
                "Test Novel"
            )
            
            # Should return None when Pandoc is not available
            assert result is None

    def test_css_responsive_design_rules(self, default_config, mock_pandoc_available):
        """Test that CSS includes responsive design rules."""
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            css_file = generator._create_default_css(output_dir)
            
            with open(css_file, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            # Check for responsive design elements
            assert 'margin-left: 2%' in css_content
            assert 'margin-right: 2%' in css_content
            assert 'font-size: 100%' in css_content
            
            # Check for e-reader compatibility
            assert 'line-height: inherit' in css_content
            assert 'hyphens: auto' in css_content

    def test_css_accessibility_features(self, default_config, mock_pandoc_available):
        """Test that CSS includes accessibility features."""
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            css_file = generator._create_default_css(output_dir)
            
            with open(css_file, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            # Check for accessibility features
            assert 'Atkinson Hyperlegible' in css_content  # Accessible font
            assert 'text-align: left' in css_content  # Better than justified for accessibility
            assert 'line-height:' in css_content  # Proper line spacing

    @patch('subprocess.run')
    def test_error_handling_in_epub_generation(self, mock_subprocess, default_config, mock_pandoc_available):
        """Test error handling during EPUB generation."""
        # Mock subprocess to return error
        mock_subprocess.return_value = Mock(returncode=1, stdout="", stderr="Error message")
        
        generator = EPUBGenerator(default_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            markdown_file = output_dir / "test.md"
            markdown_file.write_text("# Test Content")
            
            result = generator.generate_epub(
                str(markdown_file),
                output_dir,
                "Test Novel"
            )
            
            # Should return None on error
            assert result is None
