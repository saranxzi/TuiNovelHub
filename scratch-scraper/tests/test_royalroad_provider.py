"""
Tests for RoyalRoad provider.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from wn_dl.config import get_provider_config
from wn_dl.providers.royalroad.scraper import RoyalRoadScraper
from wn_dl.core.models import NovelMetadata, ChapterData, NovelStatus


@pytest.fixture
def royalroad_config():
    """Get RoyalRoad provider configuration."""
    return get_provider_config('royalroad')


@pytest.fixture
def royalroad_scraper(royalroad_config):
    """Create RoyalRoad scraper instance."""
    return RoyalRoadScraper(royalroad_config)


class TestRoyalRoadScraper:
    """Test cases for RoyalRoad scraper."""

    def test_provider_name(self, royalroad_scraper):
        """Test provider name."""
        assert royalroad_scraper.get_provider_name() == "RoyalRoad"

    def test_url_validation(self, royalroad_scraper):
        """Test URL validation."""
        valid_urls = [
            "https://www.royalroad.com/fiction/21220/mother-of-learning",
            "https://royalroad.com/fiction/12345/test-novel",
            "http://www.royalroad.com/fiction/99999/another-test"
        ]
        
        invalid_urls = [
            "https://example.com/fiction/123",
            "https://novelfull.com/novel/test",
            "not-a-url",
            ""
        ]
        
        for url in valid_urls:
            assert royalroad_scraper._validate_url(url), f"Should validate: {url}"
        
        for url in invalid_urls:
            assert not royalroad_scraper._validate_url(url), f"Should not validate: {url}"

    @pytest.mark.asyncio
    async def test_metadata_extraction_mock(self, royalroad_scraper):
        """Test metadata extraction with mocked HTML."""
        mock_html = """
        <html>
            <div class="fic-header">
                <div class="fic-title">
                    <h1>Test Novel</h1>
                    <h4><a href="/profile/123">Test Author</a></h4>
                </div>
                <div class="cover-art-container">
                    <img class="thumbnail" src="/covers/test-cover.jpg" alt="Cover">
                </div>
            </div>
            <div class="description">
                <div class="hidden-content">
                    <p>This is a test description.</p>
                    <p>Second paragraph of description.</p>
                </div>
            </div>
            <span class="fiction-tag">Fantasy</span>
            <span class="fiction-tag">Adventure</span>
        </html>
        """
        
        with patch.object(royalroad_scraper, '_get_soup') as mock_get_soup:
            from bs4 import BeautifulSoup
            mock_get_soup.return_value = BeautifulSoup(mock_html, 'html.parser')
            
            metadata = await royalroad_scraper.get_novel_metadata("https://www.royalroad.com/fiction/123/test")
            
            assert metadata is not None
            assert metadata.title == "Test Novel"
            assert metadata.author == "Test Author"
            assert "test description" in metadata.description.lower()
            assert metadata.provider == "RoyalRoad"
            assert "Fantasy" in metadata.genres
            assert "Adventure" in metadata.genres

    @pytest.mark.asyncio
    async def test_chapter_list_extraction_mock(self, royalroad_scraper):
        """Test chapter list extraction with mocked HTML."""
        mock_html = """
        <html>
            <table>
                <tr class="chapter-row">
                    <td><a href="/fiction/123/test/chapter/1/chapter-1">Chapter 1: Beginning</a></td>
                </tr>
                <tr class="chapter-row">
                    <td><a href="/fiction/123/test/chapter/2/chapter-2">Chapter 2: Continuation</a></td>
                </tr>
                <tr class="chapter-row">
                    <td><a href="/fiction/123/test/chapter/3/chapter-3">Chapter 3: End</a></td>
                </tr>
            </table>
        </html>
        """
        
        with patch.object(royalroad_scraper, '_get_soup') as mock_get_soup:
            from bs4 import BeautifulSoup
            mock_get_soup.return_value = BeautifulSoup(mock_html, 'html.parser')
            
            chapters = await royalroad_scraper.get_chapter_list("https://www.royalroad.com/fiction/123/test")
            
            assert len(chapters) == 3
            assert chapters[0]["title"] == "Chapter 1: Beginning"
            assert "chapter/1/" in chapters[0]["url"]
            assert chapters[1]["title"] == "Chapter 2: Continuation"
            assert chapters[2]["title"] == "Chapter 3: End"

    @pytest.mark.asyncio
    async def test_chapter_content_extraction_mock(self, royalroad_scraper):
        """Test chapter content extraction with mocked HTML."""
        mock_html = """
        <html>
            <div class="chapter-inner chapter-content">
                <p>Chapter 1 - The Beginning</p>
                <p class="para1">This is the first paragraph of content.</p>
                <p class="para2">This is the second paragraph.</p>
                <p class="para3">And this is the third paragraph with more content.</p>
            </div>
        </html>
        """
        
        with patch.object(royalroad_scraper, '_get_soup') as mock_get_soup:
            from bs4 import BeautifulSoup
            mock_get_soup.return_value = BeautifulSoup(mock_html, 'html.parser')
            
            chapter_data = await royalroad_scraper.scrape_chapter_content(
                "https://www.royalroad.com/fiction/123/test/chapter/1/chapter-1"
            )
            
            assert chapter_data is not None
            assert chapter_data.title == "The Beginning"
            assert "first paragraph" in chapter_data.content
            assert "second paragraph" in chapter_data.content
            assert "third paragraph" in chapter_data.content
            assert chapter_data.chapter_number == 1

    def test_chapter_number_extraction(self, royalroad_scraper):
        """Test chapter number extraction from titles."""
        test_cases = [
            ("Chapter 1: Test", 1),
            ("Chapter 42 - The Answer", 42),
            ("1. Beginning", 1),
            ("99 - Final Chapter", 99),
            ("Chapter 123", 123),
            ("No number here", None),
            ("", None),
        ]
        
        for title, expected in test_cases:
            result = royalroad_scraper._extract_chapter_number_from_title(title)
            assert result == expected, f"Failed for title: '{title}'"

    def test_content_cleaning(self, royalroad_scraper):
        """Test content cleaning functionality."""
        dirty_content = """
        This is "quoted text" and 'single quoted'.
        
        
        
        Multiple empty lines above.
        """
        
        cleaned = royalroad_scraper._clean_content_text(dirty_content)
        
        assert '"quoted text"' in cleaned
        assert "'single quoted'" in cleaned
        assert cleaned.count('\n\n') <= 1  # Should reduce multiple newlines

    @pytest.mark.asyncio
    async def test_error_handling(self, royalroad_scraper):
        """Test error handling for invalid URLs and network issues."""
        # Test with None soup (network error simulation)
        with patch.object(royalroad_scraper, '_get_soup', return_value=None):
            metadata = await royalroad_scraper.get_novel_metadata("https://www.royalroad.com/fiction/123/test")
            assert metadata is None
            
            chapters = await royalroad_scraper.get_chapter_list("https://www.royalroad.com/fiction/123/test")
            assert chapters == []
            
            chapter_data = await royalroad_scraper.scrape_chapter_content("https://www.royalroad.com/fiction/123/test/chapter/1")
            assert chapter_data is None

    def test_config_loading(self, royalroad_config):
        """Test that configuration is loaded correctly."""
        assert royalroad_config is not None
        assert "selectors" in royalroad_config
        assert "request" in royalroad_config
        assert "chapter_downloading" in royalroad_config
        
        # Check specific selectors
        selectors = royalroad_config["selectors"]
        assert selectors["title"] == ".fic-header .fic-title h1"
        assert selectors["author"] == ".fic-header .fic-title h4 a"
        assert selectors["chapter_content"] == ".chapter-inner.chapter-content"

    def test_markdownify_integration(self, royalroad_scraper):
        """Test markdownify integration for HTML to markdown conversion."""
        from bs4 import BeautifulSoup
        
        html_content = BeautifulSoup("""
        <div>
            <p><strong>Bold text</strong> and <em>italic text</em></p>
            <p>Another paragraph with <a href="http://example.com">a link</a></p>
        </div>
        """, 'html.parser')
        
        markdown = royalroad_scraper._convert_html_to_markdown(html_content)
        
        assert "**Bold text**" in markdown
        assert "*italic text*" in markdown
        assert "[a link]" in markdown
        assert "http://example.com" in markdown


if __name__ == "__main__":
    # Run basic tests
    import sys
    sys.path.append('src')
    
    config = get_provider_config('royalroad')
    scraper = RoyalRoadScraper(config)
    
    print("Running basic RoyalRoad provider tests...")
    
    # Test provider name
    assert scraper.get_provider_name() == "RoyalRoad"
    print("✓ Provider name test passed")
    
    # Test URL validation
    assert scraper._validate_url("https://www.royalroad.com/fiction/21220/mother-of-learning")
    assert not scraper._validate_url("https://example.com/fiction/123")
    print("✓ URL validation test passed")
    
    # Test chapter number extraction
    assert scraper._extract_chapter_number_from_title("Chapter 1: Test") == 1
    assert scraper._extract_chapter_number_from_title("No number") is None
    print("✓ Chapter number extraction test passed")
    
    print("✅ All basic tests passed!")
