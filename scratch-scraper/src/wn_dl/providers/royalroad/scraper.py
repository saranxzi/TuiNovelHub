"""
RoyalRoad scraper implementation.

This module provides scraping functionality for royalroad.com,
a popular web fiction platform.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...core.base_scraper import BaseNovelScraper
from ...core.models import ChapterData, NovelMetadata, NovelStatus

logger = logging.getLogger(__name__)


class RoyalRoadScraper(BaseNovelScraper):
    """Scraper implementation for RoyalRoad (royalroad.com)."""

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "RoyalRoad"

    async def get_novel_metadata(self, novel_url: str) -> Optional[NovelMetadata]:
        """
        Extract novel metadata from RoyalRoad novel page.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            NovelMetadata object or None if extraction failed
        """
        if not self._validate_url(novel_url):
            logger.error(f"Invalid URL for RoyalRoad: {novel_url}")
            return None

        soup = await self._get_soup_cached(novel_url)
        if soup is None:
            logger.error(f"Failed to fetch novel page: {novel_url}")
            return None

        try:
            # Extract basic metadata
            title = self._extract_title(soup)
            author = self._extract_author(soup)
            description = self._extract_description(soup)

            if not title or not author:
                logger.error(f"Failed to extract required metadata from {novel_url}")
                return None

            metadata = NovelMetadata(
                title=title,
                author=author,
                description=description,
                source_url=novel_url,
                cover_url=self._extract_cover_url(soup, novel_url),
                genres=self._extract_genres(soup),
                tags=self._extract_tags(soup),
                status=self._extract_status(soup),
                rating=self._extract_rating(soup),
                provider=self.get_provider_name(),
            )

            logger.info(f"Extracted metadata for: {metadata.title}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return None

    async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Get list of all available chapters from RoyalRoad novel page.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            List of dictionaries containing chapter info (title, url, number)
        """
        soup = await self._get_soup_cached(novel_url)
        if soup is None:
            logger.error(f"Failed to fetch novel page: {novel_url}")
            return []

        try:
            chapters = []
            chapter_rows = soup.select("tr.chapter-row")

            logger.info(f"Found {len(chapter_rows)} chapters")

            for i, row in enumerate(chapter_rows):
                link = row.select_one("td a")
                if not link:
                    continue

                title = link.get_text(strip=True)
                href = link.get("href")

                if not href:
                    continue

                # Convert relative URL to absolute
                chapter_url = urljoin(novel_url, href)

                # Extract chapter number from title or URL
                chapter_number = self._extract_chapter_number_from_title(title) or (
                    i + 1
                )

                chapters.append(
                    {"title": title, "url": chapter_url, "number": str(chapter_number)}
                )

            logger.info(f"Successfully extracted {len(chapters)} chapters")
            return chapters

        except Exception as e:
            logger.error(f"Error extracting chapter list: {e}")
            return []

    async def scrape_chapter_content(self, chapter_url: str) -> Optional[ChapterData]:
        """
        Extract content from a single chapter.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            ChapterData object or None if extraction failed
        """
        soup = await self._get_soup_cached(chapter_url)
        if soup is None:
            logger.error(f"Failed to fetch chapter: {chapter_url}")
            return None

        try:
            title = self._extract_chapter_title(soup)
            content = self._extract_chapter_content(soup, title)

            if not content:
                logger.error(f"No content found: {chapter_url}")
                return None

            # Extract chapter number
            chapter_number = self._extract_chapter_number(title, chapter_url)

            # Try to enhance title from content if it's just "Chapter X"
            enhanced_title = self._extract_title_from_content(
                content, title or "Untitled Chapter", chapter_number
            )

            if enhanced_title != title:
                logger.info(f"Enhanced chapter title: '{title}' -> '{enhanced_title}'")
                title = enhanced_title

            return ChapterData(
                title=title or "Untitled Chapter",
                content=content,
                url=chapter_url,
                chapter_number=chapter_number,
            )

        except Exception as e:
            logger.error(f"Error extracting chapter content from {chapter_url}: {e}")
            return None

    # Helper methods for metadata extraction
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract novel title from soup."""
        selectors = self.config.get("selectors", {})
        title_selector = selectors.get("title", ".fic-header .fic-title h1")

        title_elem = soup.select_one(title_selector)
        if title_elem:
            return title_elem.get_text(strip=True)

        return None

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author name from soup."""
        selectors = self.config.get("selectors", {})
        author_selector = selectors.get("author", ".fic-header .fic-title h4 a")

        author_elem = soup.select_one(author_selector)
        if author_elem:
            return author_elem.get_text(strip=True)

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract novel description from soup."""
        selectors = self.config.get("selectors", {})
        desc_selector = selectors.get("description", ".description .hidden-content")

        desc_elem = soup.select_one(desc_selector)
        if desc_elem:
            # Use markdownify for better HTML to markdown conversion
            use_markdownify = self.config.get("content_cleaning", {}).get(
                "use_markdownify", True
            )

            if use_markdownify:
                return self._convert_html_to_markdown(desc_elem)
            else:
                return desc_elem.get_text(separator="\n", strip=True)

        return None

    def _extract_cover_url(self, soup: BeautifulSoup, novel_url: str) -> Optional[str]:
        """Extract cover image URL from soup."""
        selectors = self.config.get("selectors", {})
        cover_selector = selectors.get(
            "cover_image", ".fic-header .cover-art-container img.thumbnail"
        )

        cover_elem = soup.select_one(cover_selector)
        if cover_elem:
            src = cover_elem.get("src")
            if src:
                return urljoin(novel_url, src)

        return None

    def _extract_genres(self, soup: BeautifulSoup) -> List[str]:
        """Extract genres from soup."""
        selectors = self.config.get("selectors", {})
        genre_selector = selectors.get("genres", ".fiction-tag")

        genres = []
        genre_elems = soup.select(genre_selector)
        for elem in genre_elems:
            genre = elem.get_text(strip=True)
            if genre:
                genres.append(genre)

        return genres

    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract tags from soup (same as genres for RoyalRoad)."""
        return self._extract_genres(soup)

    def _extract_status(self, soup: BeautifulSoup) -> NovelStatus:
        """Extract novel status from soup."""
        # RoyalRoad doesn't have a clear status indicator, default to ongoing
        return NovelStatus.ONGOING

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract rating from soup."""
        # Look for rating in meta tags or structured data
        rating_meta = soup.find("meta", property="books:rating:value")
        if rating_meta:
            try:
                return float(rating_meta.get("content", 0))
            except (ValueError, TypeError):
                pass

        return None

    def _extract_chapter_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract chapter title from chapter page."""
        selectors = self.config.get("selectors", {})
        title_selector = selectors.get(
            "chapter_title", ".chapter-content p:first-child"
        )

        title_elem = soup.select_one(title_selector)
        if title_elem:
            # RoyalRoad chapter titles are in the first paragraph
            title_text = title_elem.get_text(strip=True)
            # Remove "Chapter XXX" prefix and extract just the title
            title_match = re.search(r"Chapter\s+\d+\s*(.+)", title_text, re.IGNORECASE)
            if title_match:
                return title_match.group(1).strip()
            return title_text

        return None

    def _extract_chapter_content(
        self, soup: BeautifulSoup, title: str
    ) -> Optional[str]:
        """Extract chapter content from soup."""
        selectors = self.config.get("selectors", {})
        content_selector = selectors.get(
            "chapter_content", ".chapter-inner.chapter-content"
        )

        content_elem = soup.select_one(content_selector)
        if not content_elem:
            return None

        # Remove the first paragraph (title) from content
        first_p = content_elem.select_one("p:first-child")
        if first_p:
            first_p.decompose()

        # Use markdownify for better HTML to markdown conversion
        use_markdownify = self.config.get("content_cleaning", {}).get(
            "use_markdownify", True
        )

        if use_markdownify:
            content = self._convert_html_to_markdown(content_elem)
        else:
            content = content_elem.get_text(separator="\n\n", strip=True)

        # Clean the content
        return self._clean_content_text(content)

    def _extract_chapter_number_from_title(self, title: str) -> Optional[int]:
        """Extract chapter number from title."""
        if not title:
            return None

        # Look for patterns like "1. Title", "Chapter 1", etc.
        patterns = [
            r"^(\d+)\.",  # "1. Title"
            r"Chapter\s+(\d+)",  # "Chapter 1"
            r"^(\d+)\s*-",  # "1 - Title"
        ]

        for pattern in patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue

        return None

    def _extract_chapter_number(self, title: str, chapter_url: str) -> int:
        """Extract chapter number from title or URL."""
        # Try to extract from title first
        if title:
            number = self._extract_chapter_number_from_title(title)
            if number:
                return number

        # Try to extract from URL
        url_match = re.search(r"/chapter/\d+/(\d+)", chapter_url)
        if url_match:
            try:
                return int(url_match.group(1))
            except ValueError:
                pass

        # Default to 1 if nothing found
        return 1

    def _convert_html_to_markdown(self, content_elem) -> str:
        """Convert HTML to markdown using markdownify for better formatting."""
        html_content = str(content_elem)

        markdown_content = md(
            html_content,
            heading_style="ATX",
            emphasis_mark="*",
            strong_mark="**",
            strip=["script", "style", "meta", "link", "noscript"],
            wrap=True,
            wrap_width=80,
            escape_misc=False,
            newline_exit_br=True,
            escape_asterisks=False,
            escape_underscores=False,
        )

        return self._post_process_markdown(markdown_content)

    def _post_process_markdown(self, content: str) -> str:
        """Post-process markdown content."""
        if not content:
            return ""

        import re

        # Remove excessive newlines
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Clean up whitespace
        lines = content.split("\n")
        cleaned_lines = [line.rstrip() for line in lines]
        content = "\n".join(cleaned_lines)

        return content.strip()

    def _clean_content_text(self, content: str) -> str:
        """Clean and normalize chapter content."""
        if not content:
            return ""

        import re

        # Apply text processing from config
        text_processing = self.config.get("content_cleaning", {}).get(
            "text_processing", {}
        )

        # Replace problematic characters
        if text_processing.get("replace_quotes", True):
            content = content.replace(""", '"').replace(""", '"')
            content = content.replace("'", "'").replace("'", "'")

        # Remove empty lines but preserve paragraph breaks
        if text_processing.get("remove_empty_lines", True):
            content = re.sub(r"\n\n+", "\n\n", content)

        return content.strip()
