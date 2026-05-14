"""
Integration tests for EPUB formatting improvements.

Tests the complete workflow from markdown generation to EPUB creation
with all formatting improvements applied.
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import os
from unittest.mock import patch, Mock

from wn_dl.core.markdown_generator import MarkdownGenerator
from wn_dl.core.epub_generator import EPUBGenerator
from wn_dl.core.models import NovelMetadata, ChapterData, NovelStatus


class TestEPUBFormattingIntegration:
    """Integration tests for complete EPUB formatting workflow."""

    @pytest.fixture
    def sample_novel_data(self):
        """Create comprehensive sample novel data for testing."""
        metadata = NovelMetadata(
            title="The Test Novel: A Journey of Discovery",
            author="Jane Test Author",
            description="This is a comprehensive test description.\n\nIt contains multiple paragraphs to test the description formatting.\n\nThe third paragraph should also be properly formatted.\n\nAnd this final paragraph tests edge cases.",
            source_url="https://example.com/novel",
            genres=["Fantasy", "Adventure", "Romance"],
            tags=["Magic", "Dragons", "Heroes", "Quest"],
            status=NovelStatus.ONGOING,
            rating=9.2,
            rating_count=5432,
            chapter_count=50,
            provider="TestProvider",
            publication_date=datetime(2023, 1, 15),
            last_updated=datetime(2024, 1, 1)
        )
        
        chapters = [
            ChapterData(
                title="The Awakening",
                content="The morning sun cast long shadows across the ancient forest.\n\nElara opened her eyes slowly, feeling the weight of destiny upon her shoulders. She had dreamed of this moment for years, but nothing could have prepared her for the reality.\n\n\"Today changes everything,\" she whispered to herself.",
                url="https://example.com/chapter-1",
                chapter_number=1,
                word_count=156
            ),
            ChapterData(
                title="First Steps into the Unknown",
                content="The path ahead was treacherous and filled with uncertainty.\n\nElara gathered her belongings, checking her supplies one final time. The magical compass her grandmother had given her glowed softly in the morning light.\n\n\"Trust in yourself,\" she remembered her grandmother's words. \"The magic within you is stronger than any obstacle.\"",
                url="https://example.com/chapter-2",
                chapter_number=2,
                word_count=203
            ),
            ChapterData(
                title="The Dragon's Challenge",
                content="A massive shadow fell across the clearing as the ancient dragon descended.\n\nIts scales shimmered like emeralds in the sunlight, and its eyes held the wisdom of centuries. Elara stood her ground, though her heart raced with both fear and excitement.\n\n\"So, young one,\" the dragon's voice rumbled like distant thunder, \"you seek the Crystal of Eternal Light?\"",
                url="https://example.com/chapter-3",
                chapter_number=3,
                word_count=187
            )
        ]
        
        return metadata, chapters

    @pytest.fixture
    def test_configs(self):
        """Different configuration scenarios for testing."""
        return {
            "title_only": {
                "epub": {
                    "chapter_level": 2,
                    "include_toc": True,
                    "custom_css": True,
                    "chapter_title_format": "title_only",
                    "chapter_number_format": "arabic"
                },
                "output": {"add_page_breaks": True}
            },
            "number_title": {
                "epub": {
                    "chapter_level": 2,
                    "include_toc": True,
                    "custom_css": True,
                    "chapter_title_format": "number_title",
                    "chapter_number_format": "arabic"
                },
                "output": {"add_page_breaks": True}
            },
            "chapter_number_title": {
                "epub": {
                    "chapter_level": 2,
                    "include_toc": True,
                    "custom_css": True,
                    "chapter_title_format": "chapter_number_title",
                    "chapter_number_format": "arabic"
                },
                "output": {"add_page_breaks": True}
            }
        }

    def test_complete_workflow_title_only_format(self, sample_novel_data, test_configs):
        """Test complete workflow with title_only chapter format."""
        metadata, chapters = sample_novel_data
        config = test_configs["title_only"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Generate markdown
            md_generator = MarkdownGenerator(config)
            markdown_file = md_generator.generate_markdown(metadata, chapters, output_dir)
            
            assert markdown_file is not None
            assert Path(markdown_file).exists()
            
            # Read and verify markdown content
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Test chapter title formatting (should be title only)
            assert "## The Awakening {" in content
            assert "## First Steps into the Unknown {" in content
            assert "## The Dragon's Challenge {" in content
            assert "Chapter 1:" not in content
            assert "1. The Awakening" not in content
            
            # Test description formatting (should have proper paragraphs)
            assert "This is a comprehensive test description." in content
            assert "It contains multiple paragraphs" in content
            
            # Test chapter div wrappers for page breaks
            assert '<div class="chapter">' in content
            assert '</div>' in content
            
            # Test page breaks
            assert "\\newpage" in content

    def test_complete_workflow_number_title_format(self, sample_novel_data, test_configs):
        """Test complete workflow with number_title chapter format."""
        metadata, chapters = sample_novel_data
        config = test_configs["number_title"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            md_generator = MarkdownGenerator(config)
            markdown_file = md_generator.generate_markdown(metadata, chapters, output_dir)
            
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Test chapter title formatting (should be number. title)
            assert "## 1. The Awakening {" in content
            assert "## 2. First Steps into the Unknown {" in content
            assert "## 3. The Dragon's Challenge {" in content
            
            # Test TOC formatting (should match chapter format)
            assert "[1. The Awakening]" in content
            assert "[2. First Steps into the Unknown]" in content
            assert "[3. The Dragon's Challenge]" in content

    def test_complete_workflow_chapter_number_title_format(self, sample_novel_data, test_configs):
        """Test complete workflow with chapter_number_title format."""
        metadata, chapters = sample_novel_data
        config = test_configs["chapter_number_title"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            md_generator = MarkdownGenerator(config)
            markdown_file = md_generator.generate_markdown(metadata, chapters, output_dir)
            
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Test chapter title formatting (should be Chapter X: Title)
            assert "## Chapter 1: The Awakening {" in content
            assert "## Chapter 2: First Steps into the Unknown {" in content
            assert "## Chapter 3: The Dragon's Challenge {" in content

    @patch('wn_dl.core.epub_generator.EPUBGenerator._check_pandoc', return_value=True)
    @patch('subprocess.run')
    def test_epub_generation_with_css_improvements(self, mock_subprocess, mock_pandoc, sample_novel_data, test_configs):
        """Test EPUB generation includes CSS improvements."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
        
        metadata, chapters = sample_novel_data
        config = test_configs["title_only"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Generate markdown
            md_generator = MarkdownGenerator(config)
            markdown_file = md_generator.generate_markdown(metadata, chapters, output_dir)
            
            # Generate EPUB
            epub_generator = EPUBGenerator(config)
            epub_file = epub_generator.generate_epub(
                markdown_file,
                output_dir,
                metadata.title,
                metadata=metadata.to_dict()
            )
            
            # Verify subprocess was called with correct arguments
            mock_subprocess.assert_called_once()
            call_args = mock_subprocess.call_args[0][0]
            
            # Should include CSS file
            assert "--css" in call_args
            
            # Find and verify CSS file
            css_index = call_args.index("--css")
            css_file = call_args[css_index + 1]
            
            assert Path(css_file).exists()
            
            # Verify CSS content includes page break improvements
            with open(css_file, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            assert '.chapter {' in css_content
            assert 'page-break-before: always;' in css_content
            assert '-webkit-column-break-before: always;' in css_content
            assert 'break-before: page;' in css_content

    def test_description_edge_cases(self, test_configs):
        """Test description formatting with various edge cases."""
        config = test_configs["title_only"]
        md_generator = MarkdownGenerator(config)
        
        # Test empty description
        assert md_generator._format_description("") == ""
        assert md_generator._format_description(None) == ""
        
        # Test single paragraph
        single_para = "This is a single paragraph description."
        assert md_generator._format_description(single_para) == single_para
        
        # Test description with only line breaks
        line_breaks_only = "Line one\nLine two\nLine three"
        formatted = md_generator._format_description(line_breaks_only)
        assert formatted == "Line one Line two Line three"
        
        # Test mixed formatting
        mixed = "Paragraph one.\n\nParagraph two\nwith line break.\n\n\nParagraph three."
        formatted = md_generator._format_description(mixed)
        paragraphs = formatted.split('\n\n')
        assert len(paragraphs) == 3
        assert "Paragraph two with line break." in paragraphs[1]

    def test_yaml_frontmatter_includes_formatted_description(self, sample_novel_data, test_configs):
        """Test that YAML frontmatter includes properly formatted description."""
        metadata, chapters = sample_novel_data
        config = test_configs["title_only"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            md_generator = MarkdownGenerator(config)
            markdown_file = md_generator.generate_markdown(metadata, chapters, output_dir)
            
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check YAML frontmatter
            assert "---" in content
            assert "title: The Test Novel: A Journey of Discovery" in content
            assert "author: Jane Test Author" in content
            assert "description:" in content
            
            # The description in YAML should be the original (Pandoc will handle it)
            # But the title page should have formatted description
            assert "## Description" in content

    def test_chapter_content_formatting_preserved(self, sample_novel_data, test_configs):
        """Test that chapter content formatting is preserved."""
        metadata, chapters = sample_novel_data
        config = test_configs["title_only"]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            md_generator = MarkdownGenerator(config)
            markdown_file = md_generator.generate_markdown(metadata, chapters, output_dir)
            
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check that chapter content paragraphs are preserved
            assert '<p class="first-paragraph">The morning sun cast long shadows' in content
            assert '<p>Elara opened her eyes slowly' in content
            assert '"Today changes everything," she whispered' in content

    def test_toc_generation_consistency(self, sample_novel_data, test_configs):
        """Test that table of contents is consistent with chapter formatting."""
        metadata, chapters = sample_novel_data
        
        for config_name, config in test_configs.items():
            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir)
                
                md_generator = MarkdownGenerator(config)
                markdown_file = md_generator.generate_markdown(metadata, chapters, output_dir)
                
                with open(markdown_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract TOC section
                toc_start = content.find("# Table of Contents")
                toc_end = content.find("\\newpage", toc_start)
                toc_section = content[toc_start:toc_end]
                
                if config_name == "title_only":
                    assert "[The Awakening]" in toc_section
                    assert "Chapter 1:" not in toc_section
                elif config_name == "number_title":
                    assert "[1. The Awakening]" in toc_section
                elif config_name == "chapter_number_title":
                    assert "[Chapter 1: The Awakening]" in toc_section
