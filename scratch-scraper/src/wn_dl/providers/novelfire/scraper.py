"""
NovelFire scraper implementation.

This module provides scraping functionality for novelfire.net,
a popular web fiction platform with paginated chapter lists.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...core.base_scraper import BaseNovelScraper
from ...core.models import ChapterData, NovelMetadata, NovelStatus

logger = logging.getLogger(__name__)


class NovelFireScraper(BaseNovelScraper):
    """Scraper implementation for NovelFire (novelfire.net)."""

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "NovelFire"

    async def get_novel_metadata(self, novel_url: str) -> Optional[NovelMetadata]:
        """
        Extract novel metadata from NovelFire novel page.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            NovelMetadata object or None if extraction failed
        """
        if not self._validate_url(novel_url):
            logger.error(f"Invalid URL for NovelFire: {novel_url}")
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
        Get list of all available chapters from NovelFire novel page.
        Handles pagination to get all chapters across multiple pages.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            List of dictionaries containing chapter info (title, url, number)
        """
        # Get the chapters URL from the novel page
        chapters_url = self._get_chapters_url(novel_url)
        if not chapters_url:
            logger.error(f"Could not determine chapters URL for: {novel_url}")
            return []

        all_chapters = []
        page = 1
        max_pages = 100  # Safety limit

        while page <= max_pages:
            page_url = f"{chapters_url}?page={page}"
            logger.info(f"Fetching chapter page {page}: {page_url}")

            soup = await self._get_soup_cached(page_url)
            if soup is None:
                logger.error(f"Failed to fetch chapter page {page}: {page_url}")
                break

            # Extract chapters from this page
            page_chapters = self._extract_chapters_from_page(soup, novel_url)
            if not page_chapters:
                logger.info(f"No chapters found on page {page}, stopping pagination")
                break

            all_chapters.extend(page_chapters)
            logger.info(f"Found {len(page_chapters)} chapters on page {page}")

            # Check if there's a next page
            if not self._has_next_page(soup):
                logger.info(f"No more pages after page {page}")
                break

            page += 1

        logger.info(f"Successfully extracted {len(all_chapters)} chapters total")
        return all_chapters

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
            content = self._extract_chapter_content(soup)

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
        title_selector = selectors.get("title", ".novel-title")

        title_elem = soup.select_one(title_selector)
        if title_elem:
            return title_elem.get_text(strip=True)

        return None

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author name from soup."""
        selectors = self.config.get("selectors", {})
        author_selector = selectors.get("author", ".author span[itemprop='author']")

        author_elem = soup.select_one(author_selector)
        if author_elem:
            return author_elem.get_text(strip=True)

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract novel description from soup."""
        selectors = self.config.get("selectors", {})
        desc_selector = selectors.get("description", ".summary .content.expand-wrapper")

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
        cover_selector = selectors.get("cover_image", ".cover img")

        cover_elem = soup.select_one(cover_selector)
        if cover_elem:
            # NovelFire uses lazy loading with data-src
            src = cover_elem.get("data-src") or cover_elem.get("src")
            if src:
                return urljoin(novel_url, src)

        return None

    def _extract_genres(self, soup: BeautifulSoup) -> List[str]:
        """Extract genres from soup."""
        selectors = self.config.get("selectors", {})
        genre_selector = selectors.get("genres", ".categories ul li a.property-item")

        genres = []
        genre_elems = soup.select(genre_selector)
        for elem in genre_elems:
            genre = elem.get_text(strip=True)
            if genre:
                genres.append(genre)

        return genres

    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract tags from soup (same as genres for NovelFire)."""
        return self._extract_genres(soup)

    def _extract_status(self, soup: BeautifulSoup) -> NovelStatus:
        """Extract novel status from soup."""
        selectors = self.config.get("selectors", {})
        status_selector = selectors.get(
            "status", ".header-stats .completed, .header-stats .ongoing"
        )

        status_elem = soup.select_one(status_selector)
        if status_elem:
            status_text = status_elem.get_text(strip=True).lower()
            if "completed" in status_text:
                return NovelStatus.COMPLETED
            elif "ongoing" in status_text:
                return NovelStatus.ONGOING

        return NovelStatus.ONGOING

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract rating from soup."""
        selectors = self.config.get("selectors", {})
        rating_selector = selectors.get("rating", ".rating .nub")

        rating_elem = soup.select_one(rating_selector)
        if rating_elem:
            try:
                rating_text = rating_elem.get_text(strip=True)
                return float(rating_text)
            except (ValueError, TypeError):
                pass

        return None

    def _get_chapters_url(self, novel_url: str) -> Optional[str]:
        """Get the chapters URL from the novel URL."""
        # NovelFire chapters URL pattern: /book/novel-name/chapters
        if "/book/" in novel_url:
            base_url = novel_url.rstrip("/")
            return f"{base_url}/chapters"
        return None

    def _extract_chapters_from_page(
        self, soup: BeautifulSoup, novel_url: str
    ) -> List[Dict[str, str]]:
        """Extract chapters from a single chapter list page."""
        selectors = self.config.get("selectors", {})
        chapter_selector = selectors.get(
            "chapter_list", selectors.get("chapter_links", "ul.chapter-list li a")
        )

        chapters = []
        chapter_links = soup.select(chapter_selector)

        for link in chapter_links:
            title_elem = link.select_one(".chapter-title")
            number_elem = link.select_one(".chapter-no")

            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            href = link.get("href")

            if not href:
                continue

            # Convert relative URL to absolute
            chapter_url = urljoin(novel_url, href)

            # Extract chapter number
            chapter_number = None
            if number_elem:
                try:
                    chapter_number = int(number_elem.get_text(strip=True))
                except (ValueError, TypeError):
                    pass

            if chapter_number is None:
                chapter_number = (
                    self._extract_chapter_number_from_title(title) or len(chapters) + 1
                )

            chapters.append(
                {"title": title, "url": chapter_url, "number": str(chapter_number)}
            )

        return chapters

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page in pagination."""
        # Look for pagination next button that's not disabled
        next_link = soup.select_one(
            ".pagination .page-item:not(.disabled) a[aria-label*='Next'], .pagination .page-item:not(.disabled) a[rel='next']"
        )
        return next_link is not None

    def _extract_chapter_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract chapter title from chapter page."""
        selectors = self.config.get("selectors", {})
        title_selector = selectors.get("chapter_title", ".chapter-title")

        title_elem = soup.select_one(title_selector)
        if title_elem:
            return title_elem.get_text(strip=True)

        return None

    def _extract_chapter_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract chapter content from soup."""
        selectors = self.config.get("selectors", {})
        content_selector = selectors.get("chapter_content", "#content.clearfix")

        content_elem = soup.select_one(content_selector)
        if not content_elem:
            return None

        # Remove unwanted elements
        self._remove_unwanted_elements(content_elem)

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

    def _remove_unwanted_elements(self, content_elem):
        """Remove unwanted elements from content."""
        remove_selectors = self.config.get("content_cleaning", {}).get(
            "remove_selectors", []
        )

        for selector in remove_selectors:
            for elem in content_elem.select(selector):
                elem.decompose()

    def _extract_chapter_number_from_title(self, title: str) -> Optional[int]:
        """Extract chapter number from title."""
        if not title:
            return None

        # Look for patterns like "Chapter 1", "1.", etc.
        patterns = [
            r"Chapter\s+(\d+)",  # "Chapter 1"
            r"^(\d+)\.",  # "1. Title"
            r"^(\d+)\s*-",  # "1 - Title"
            r"Ch\.?\s*(\d+)",  # "Ch. 1" or "Ch 1"
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
        url_match = re.search(r"/chapter-(\d+)", chapter_url)
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

        # Remove text patterns (ads, unwanted content)
        remove_patterns = self.config.get("content_cleaning", {}).get(
            "remove_patterns", []
        )
        for pattern in remove_patterns:
            content = re.sub(pattern, "", content, flags=re.IGNORECASE | re.MULTILINE)

        # Replace problematic characters
        if text_processing.get("replace_quotes", True):
            content = content.replace(""", '"').replace(""", '"')
            content = content.replace("'", "'").replace("'", "'")

        # Remove empty lines but preserve paragraph breaks
        if text_processing.get("remove_empty_lines", True):
            content = re.sub(r"\n\n+", "\n\n", content)

        return content.strip()
