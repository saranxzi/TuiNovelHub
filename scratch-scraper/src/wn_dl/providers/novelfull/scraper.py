"""
NovelFull scraper implementation.

This module provides scraping functionality for novelfull.com,
including support for paginated chapter discovery.
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


class NovelFullScraper(BaseNovelScraper):
    """Scraper implementation for NovelFull (novelfull.com)."""

    def get_provider_name(self) -> str:
        return "NovelFull"

    async def get_novel_metadata(self, novel_url: str) -> Optional[NovelMetadata]:
        """Extract novel metadata from NovelFull."""
        if not self._validate_url(novel_url):
            logger.error(f"Invalid URL: {novel_url}")
            return None

        soup = await self._get_soup_cached(novel_url)
        if soup is None:
            return None

        try:
            # Extract additional metadata
            alternative_names = self._extract_alternative_names(soup)
            source = self._extract_source(soup)

            metadata = NovelMetadata(
                title=self._extract_title(soup),
                author=self._extract_author(soup),
                description=self._extract_description(soup),
                source_url=novel_url,
                cover_url=self._extract_cover_url(soup, novel_url),
                genres=self._extract_genres(soup),
                tags=self._extract_tags(soup),
                status=self._extract_status(soup),
                rating=self._extract_rating(soup),
                provider=self.get_provider_name(),
            )

            # Add additional metadata as custom attributes
            if alternative_names:
                metadata.alternative_names = alternative_names
            if source:
                metadata.source = source

            logger.info(f"Extracted metadata for: {metadata.title}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return None

    async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """Get list of all chapters using pagination."""
        discovery_method = self.config.get("chapter_discovery", {}).get(
            "discovery_method", "static"
        )

        if discovery_method == "pagination":
            return await self._get_chapters_pagination(novel_url)
        else:
            return await self._get_chapters_static(novel_url)

    async def scrape_chapter_content(self, chapter_url: str) -> Optional[ChapterData]:
        """Extract chapter content from NovelFull."""
        soup = await self._get_soup_cached(chapter_url)
        if soup is None:
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

            chapter_data = ChapterData(
                title=title or "Untitled Chapter",
                content=content,
                url=chapter_url,
                chapter_number=chapter_number,
                is_cleaned=True,
            )

            chapter_data.calculate_word_count()
            return chapter_data

        except Exception as e:
            logger.error(f"Error extracting chapter: {e}")
            return None

    # Helper methods for metadata extraction
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract novel title."""
        selector = self.config.get("selectors", {}).get("title")
        if selector:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return "Unknown Title"

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Extract author name."""
        # Try the configured selector first
        selector = self.config.get("selectors", {}).get("author")
        if selector:
            elements = soup.select(selector)
            if elements:
                # Join multiple authors with comma
                authors = [
                    elem.get_text(strip=True)
                    for elem in elements
                    if elem.get_text(strip=True)
                ]
                if authors:
                    return ", ".join(authors)

        # Fallback selectors
        fallback_selectors = [
            ".info div:-soup-contains('Author:') a",
            ".author",
            "meta[name='author']",
        ]

        for fallback_selector in fallback_selectors:
            if fallback_selector.startswith("meta"):
                element = soup.select_one(fallback_selector)
                if element:
                    return element.get("content", "").strip()
            else:
                elements = soup.select(fallback_selector)
                if elements:
                    authors = [
                        elem.get_text(strip=True)
                        for elem in elements
                        if elem.get_text(strip=True)
                    ]
                    if authors:
                        return ", ".join(authors)

        return "Unknown Author"

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract description."""
        selector = self.config.get("selectors", {}).get("description")
        if selector:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return ""

    def _extract_cover_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract cover image URL."""
        selector = self.config.get("selectors", {}).get("cover_image")
        if selector:
            element = soup.select_one(selector)
            if element:
                cover_url = element.get("src") or element.get("content")
                if cover_url:
                    return urljoin(base_url, cover_url)
        return None

    def _extract_genres(self, soup: BeautifulSoup) -> List[str]:
        """Extract genres."""
        selector = self.config.get("selectors", {}).get("genres")
        genres = []
        if selector:
            elements = soup.select(selector)
            for element in elements:
                genre = element.get_text(strip=True)
                if genre and genre not in genres:  # Avoid duplicates
                    genres.append(genre)

        # Fallback: try to extract from breadcrumb or other locations
        if not genres:
            fallback_selectors = [
                ".info div:-soup-contains('Genre:') a",
                ".genre a",
                ".breadcrumb a[href*='/genre/']",
            ]

            for fallback_selector in fallback_selectors:
                elements = soup.select(fallback_selector)
                for element in elements:
                    genre = element.get_text(strip=True)
                    if genre and genre not in genres:
                        genres.append(genre)
                if genres:  # Stop at first successful extraction
                    break

        return genres

    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract tags."""
        selector = self.config.get("selectors", {}).get("tags")
        tags = []
        if selector:
            elements = soup.select(selector)
            for element in elements:
                tag = element.get_text(strip=True)
                if tag:
                    tags.append(tag)
        return tags

    def _extract_status(self, soup: BeautifulSoup) -> NovelStatus:
        """Extract novel status."""
        selector = self.config.get("selectors", {}).get("status")
        if selector:
            element = soup.select_one(selector)
            if element:
                status_text = element.get_text(strip=True).lower()
                if "completed" in status_text:
                    return NovelStatus.COMPLETED
                elif "ongoing" in status_text:
                    return NovelStatus.ONGOING
                elif "hiatus" in status_text:
                    return NovelStatus.HIATUS
        return NovelStatus.UNKNOWN

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract rating."""
        # Try configured selector first
        selector = self.config.get("selectors", {}).get("rating")
        if selector:
            element = soup.select_one(selector)
            if element:
                rating_text = element.get("value") or element.get_text(strip=True)
                try:
                    return float(rating_text)
                except (ValueError, TypeError):
                    pass

        # Fallback selectors
        fallback_selectors = [
            "#rateVal",
            ".rate .small strong span:first-child",
            ".rating-value",
            "[data-rating]",
        ]

        for fallback_selector in fallback_selectors:
            element = soup.select_one(fallback_selector)
            if element:
                rating_text = (
                    element.get("value")
                    or element.get("data-rating")
                    or element.get_text(strip=True)
                )
                try:
                    return float(rating_text)
                except (ValueError, TypeError):
                    continue

        return None

    def _extract_alternative_names(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract alternative names."""
        selector = self.config.get("selectors", {}).get("alternative_names")
        if selector:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # Remove the "Alternative names:" prefix
                if ":" in text:
                    return text.split(":", 1)[1].strip()
                return text
        return None

    def _extract_source(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract source information."""
        selector = self.config.get("selectors", {}).get("source")
        if selector:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # Remove the "Source:" prefix
                if ":" in text:
                    return text.split(":", 1)[1].strip()
                return text
        return None

    # Chapter extraction methods
    def _extract_chapter_title(self, soup: BeautifulSoup) -> str:
        """Extract chapter title."""
        selectors = [
            self.config.get("selectors", {}).get("chapter_title"),
            ".chapter-title",
            "h2 .chapter-text",
            "h1",
        ]

        for selector in selectors:
            if selector:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True)
                    return self._clean_chapter_title(title)

        return "Untitled Chapter"

    def _clean_chapter_title(self, title: str) -> str:
        """
        Clean chapter title by removing unwanted parts and formatting.
        Also handles number-only titles by adding "Chapter" prefix.

        Args:
            title: Raw chapter title from HTML

        Returns:
            Cleaned chapter title
        """
        if not title:
            return "Untitled Chapter"

        import re

        # Strip whitespace and normalize
        title = title.strip()
        if not title:
            return "Untitled Chapter"

        # Remove novel name prefix patterns
        # Pattern 1: "Novel Name-Chapter X: Title" or "Novel Name - Chapter X: Title"
        pattern1 = r"^.+?[-–]\s*(Chapter\s+\d+.*?)$"
        match = re.match(pattern1, title, re.IGNORECASE)
        if match:
            cleaned_title = match.group(1).strip()
            logger.debug(
                f"Cleaned chapter title (pattern 1): '{title}' -> '{cleaned_title}'"
            )
            title = cleaned_title

        # Pattern 2: "Novel Name: Chapter X" or "Novel Name | Chapter X"
        pattern2 = r"^.+?[:|]\s*(Chapter\s+\d+.*?)$"
        match = re.match(pattern2, title, re.IGNORECASE)
        if match:
            cleaned_title = match.group(1).strip()
            logger.debug(
                f"Cleaned chapter title (pattern 2): '{title}' -> '{cleaned_title}'"
            )
            title = cleaned_title

        # Pattern 3: Remove common prefixes like "Read", "Online", etc.
        prefixes_to_remove = [
            r"^Read\s+",
            r"^Online\s+",
            r"^Free\s+",
            r"^Latest\s+",
        ]
        for prefix_pattern in prefixes_to_remove:
            if re.match(prefix_pattern, title, re.IGNORECASE):
                title = re.sub(prefix_pattern, "", title, flags=re.IGNORECASE).strip()
                logger.debug(f"Removed prefix: {prefix_pattern}")

        # Clean up extra whitespace and special characters
        title = re.sub(r"\s+", " ", title)  # Multiple spaces to single space
        title = re.sub(
            r"^\W+|\W+$", "", title
        )  # Remove leading/trailing non-word chars

        # Check if title is number-only and add "Chapter" prefix
        if re.match(r"^\d+$", title):
            title = f"Chapter {title}"
            logger.debug(f"Added 'Chapter' prefix to number-only title: {title}")

        # Ensure title is not empty after cleaning
        if not title or title.isspace():
            title = "Untitled Chapter"

        return title

    def _remove_duplicate_chapter_title(self, content: str, chapter_title: str) -> str:
        """
        Remove duplicate chapter title from content if it appears at the beginning.

        Args:
            content: Chapter content text
            chapter_title: Chapter title to remove if duplicated

        Returns:
            Content with duplicate title removed
        """
        if not content or not chapter_title:
            return content

        import re

        # Split content into lines
        lines = content.split("\n")
        if not lines:
            return content

        # Check first few lines for chapter title duplicates
        lines_to_check = min(5, len(lines))  # Check first 5 lines

        for i in range(lines_to_check):
            line = lines[i].strip()
            if not line:
                continue

            # Check for exact match (case insensitive)
            if line.lower() == chapter_title.lower():
                logger.debug(f"Removed duplicate chapter title from content: {line}")
                lines[i] = ""
                continue

            # Check for chapter title with common prefixes
            prefixed_patterns = [
                rf"^Chapter\s*:?\s*{re.escape(chapter_title)}",
                rf"^Ch\s*:?\s*{re.escape(chapter_title)}",
                rf"^{re.escape(chapter_title)}\s*$",
            ]

            for pattern in prefixed_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    logger.debug(f"Removed prefixed duplicate chapter title: {line}")
                    lines[i] = ""
                    break

            # Check if line contains chapter title as substring (for partial matches)
            if (
                chapter_title.lower() in line.lower()
                and len(line) < len(chapter_title) * 2
            ):
                # Only remove if line is not much longer than title (avoid removing content)
                logger.debug(f"Removed partial duplicate chapter title: {line}")
                lines[i] = ""

        # Rejoin lines and clean up extra newlines
        result = "\n".join(lines)
        result = re.sub(r"\n\s*\n\s*\n", "\n\n", result)  # Remove excessive newlines
        result = result.strip()

        return result

    def _extract_chapter_content(
        self, soup: BeautifulSoup, chapter_title: str = None
    ) -> str:
        """Extract and clean chapter content with ad removal and character fixes."""
        selector = self.config.get("selectors", {}).get("chapter_content")
        content_element = soup.select_one(selector)

        if not content_element:
            logger.warning("Chapter content element not found")
            return ""

        # Remove unwanted elements
        remove_selectors = self.config.get("content_processing", {}).get(
            "remove_selectors", []
        )
        for remove_selector in remove_selectors:
            for element in content_element.select(remove_selector):
                element.decompose()

        # Use markdownify for better HTML to markdown conversion if enabled
        use_markdownify = self.config.get("content_processing", {}).get(
            "use_markdownify", True
        )

        if use_markdownify:
            content_text = self._convert_html_to_markdown(content_element)
            # Apply paragraph-level cleaning to the markdown content
            paragraphs = []
            for paragraph in content_text.split("\n\n"):
                cleaned_text = self._clean_paragraph_content(paragraph.strip())
                if cleaned_text:
                    paragraphs.append(cleaned_text)
            content_result = "\n\n".join(paragraphs)
            # Remove duplicate chapter title from content if present
            if chapter_title:
                content_result = self._remove_duplicate_chapter_title(
                    content_result, chapter_title
                )
            return content_result
        else:
            # Fallback to original paragraph extraction
            paragraphs = []
            for p in content_element.find_all(["p", "div"], recursive=True):
                text = p.get_text(strip=True)
                if text and text not in paragraphs:
                    # Clean the text content
                    cleaned_text = self._clean_paragraph_content(text)
                    if cleaned_text:  # Only add if not filtered out
                        paragraphs.append(cleaned_text)
            content_result = "\n\n".join(paragraphs)
            # Remove duplicate chapter title from content if present
            if chapter_title:
                content_result = self._remove_duplicate_chapter_title(
                    content_result, chapter_title
                )
            return content_result

    def _clean_paragraph_content(self, text: str) -> str:
        """
        Clean paragraph content by removing ads and fixing invalid characters.

        Args:
            text: Raw paragraph text

        Returns:
            Cleaned text, or empty string if paragraph should be removed
        """
        if not text:
            return ""

        import re

        # Convert to lowercase for ad detection (but preserve original case for output)
        text_lower = text.lower()

        # Ad detection patterns - remove paragraphs containing these
        ad_patterns = [
            # Common ad indicators
            "advertisement",
            "sponsored",
            "ads by",
            "google ads",
            "click here",
            "visit our",
            "subscribe to",
            "follow us",
            "like us on",
            "join our",
            "download our app",
            # NovelFull specific ad patterns
            "novelfull.com",
            "read more at novelfull",
            "support us by",
            "donate to",
            "patreon",
            "discord server",
            "telegram",
            "facebook page",
            # Generic promotional content
            "support the author",
            "buy me a coffee",
            "ko-fi",
            "paypal",
            "support translation",
            "translator note",
            "tn:",
            "tl:",
            "pr:",
            "editor note",
            "ed:",
            # Navigation/UI elements that might leak through
            "previous chapter",
            "next chapter",
            "table of contents",
            "bookmark this",
            "add to library",
            "reading list",
            # Common spam/promotional phrases
            "earn money",
            "make money",
            "free download",
            "limited time",
            "special offer",
            "discount",
            "promo code",
            "coupon",
            "affiliate",
        ]

        # Check if paragraph contains ad content
        for pattern in ad_patterns:
            if pattern in text_lower:
                logger.debug(f"Removing ad paragraph: {text[:50]}...")
                return ""  # Remove this paragraph

        # Character replacements for invalid/problematic characters
        char_replacements = {
            # Curly quotes to straight quotes
            "'": "'",  # Right single quotation mark
            "'": "'",  # Left single quotation mark
            """: '"',  # Left double quotation mark
            """: '"',  # Right double quotation mark
            # Additional quote variations
            "″": '"',  # Double prime (often used as quotes)
            "‟": '"',  # Double high-reversed-9 quotation mark
            "‛": "'",  # Single high-reversed-9 quotation mark
            "´": "'",  # Acute accent (often used as apostrophe)
            "`": "'",  # Grave accent (often used as apostrophe)
            "ˈ": "'",  # Primary stress mark (sometimes used as apostrophe)
            # Em/en dashes to regular hyphens (for better compatibility)
            "—": "-",  # Em dash
            "–": "-",  # En dash
            "―": "-",  # Horizontal bar
            # Other problematic Unicode characters
            "…": "...",  # Horizontal ellipsis
            "«": '"',  # Left-pointing double angle quotation mark
            "»": '"',  # Right-pointing double angle quotation mark
            "‚": ",",  # Single low-9 quotation mark
            "„": '"',  # Double low-9 quotation mark
            "‹": "'",  # Single left-pointing angle quotation mark
            "›": "'",  # Single right-pointing angle quotation mark
            # Non-breaking spaces and other whitespace
            "\u00a0": " ",  # Non-breaking space
            "\u2009": " ",  # Thin space
            "\u200a": " ",  # Hair space
            "\u200b": "",  # Zero-width space
            "\u200c": "",  # Zero-width non-joiner
            "\u200d": "",  # Zero-width joiner
            "\ufeff": "",  # Zero-width no-break space (BOM)
            # Other special characters that can cause issues
            "¡": "!",  # Inverted exclamation mark
            "¿": "?",  # Inverted question mark
            "§": "",  # Section sign
            "¶": "",  # Pilcrow sign
            "†": "",  # Dagger
            "‡": "",  # Double dagger
            "•": "*",  # Bullet
            "‰": "%",  # Per mille sign
            "′": "'",  # Prime (sometimes used as apostrophe)
        }

        # Apply character replacements
        cleaned_text = text
        for old_char, new_char in char_replacements.items():
            cleaned_text = cleaned_text.replace(old_char, new_char)

        # Escape markdown special characters to prevent formatting issues
        cleaned_text = self._escape_markdown_characters(cleaned_text)

        # Additional cleanup
        # Normalize whitespace within lines only, preserve line breaks
        lines = cleaned_text.split("\n")
        normalized_lines = []
        for line in lines:
            # Only normalize spaces/tabs within each line, not newlines
            normalized_line = re.sub(r"[ \t]+", " ", line).strip()
            normalized_lines.append(normalized_line)
        cleaned_text = "\n".join(normalized_lines)

        # Remove empty parentheses or brackets that might be left from ad removal
        cleaned_text = re.sub(r"\(\s*\)", "", cleaned_text)
        cleaned_text = re.sub(r"\[\s*\]", "", cleaned_text)
        cleaned_text = re.sub(r"\{\s*\}", "", cleaned_text)

        # Remove standalone punctuation
        cleaned_text = re.sub(r"^\s*[.,;:!?]+\s*$", "", cleaned_text)

        return cleaned_text.strip()

    def _escape_markdown_characters(self, text: str) -> str:
        """
        Escape markdown special characters to prevent formatting issues.

        Args:
            text: Text that may contain markdown special characters

        Returns:
            Text with markdown characters properly escaped
        """
        if not text:
            return ""

        import re

        # Markdown characters that need escaping in content
        # Note: We're being selective here - only escaping characters that commonly
        # cause issues in novel content, not all possible markdown characters
        markdown_escapes = {
            # Backslash must be first to avoid double-escaping
            "\\": "\\\\",
            # Characters that commonly appear in novels and cause markdown issues
            "*": "\\*",  # Asterisk (bold/italic)
            "_": "\\_",  # Underscore (bold/italic)
            "`": "\\`",  # Backtick (code)
            "#": "\\#",  # Hash (headers) - only at start of line
            # Brackets and parentheses (links/images)
            "[": "\\[",
            "]": "\\]",
            # Less common but problematic
            "~": "\\~",  # Strikethrough
            "^": "\\^",  # Superscript
            "|": "\\|",  # Tables
            # HTML-like characters
            "<": "&lt;",
            ">": "&gt;",
            "&": "&amp;",
        }

        escaped_text = text

        # Apply escaping
        for char, escaped in markdown_escapes.items():
            if char == "#":
                # Only escape # at the beginning of lines (headers)
                escaped_text = re.sub(r"^#", "\\#", escaped_text, flags=re.MULTILINE)
            else:
                escaped_text = escaped_text.replace(char, escaped)

        # Handle special cases
        # Escape horizontal rules (--- or ***) at start of line
        escaped_text = re.sub(
            r"^(-{3,}|\*{3,})$", r"\\\1", escaped_text, flags=re.MULTILINE
        )

        # Escape numbered lists that might be interpreted as markdown
        escaped_text = re.sub(r"^(\d+)\.", r"\1\\.", escaped_text, flags=re.MULTILINE)

        return escaped_text

    async def _get_chapters_static(self, novel_url: str) -> List[Dict[str, str]]:
        """Get chapters from static page (fallback method)."""
        soup = await self._get_soup_cached(novel_url)
        if soup is None:
            return []

        chapters = []
        selector = self.config.get("selectors", {}).get("chapter_list")

        if selector:
            chapter_links = soup.select(selector)
            for i, link in enumerate(chapter_links):
                chapter_url = link.get("href")
                chapter_title = link.get_text(strip=True) or link.get("title", "")

                if chapter_url:
                    # Make URL absolute
                    if not chapter_url.startswith("http"):
                        chapter_url = urljoin(self.base_url, chapter_url)

                    # Validate chapter URL (filter out error pages)
                    if not self._is_valid_chapter_url(chapter_url):
                        continue

                    # Extract chapter number
                    chapter_number = self._extract_chapter_number(
                        chapter_title, chapter_url
                    )

                    chapters.append(
                        {
                            "title": chapter_title,
                            "url": chapter_url,
                            "number": chapter_number or (i + 1),
                        }
                    )

        logger.info(f"Found {len(chapters)} chapters via static method")
        return chapters

    async def _get_chapters_pagination(self, novel_url: str) -> List[Dict[str, str]]:
        """Get all chapters by making concurrent requests to pagination pages."""
        logger.info(f"Starting concurrent paginated chapter discovery for: {novel_url}")

        # First, get the first page to determine total pages
        soup = await self._get_soup_cached(novel_url)
        if soup is None:
            logger.error("Failed to fetch first page")
            return []

        # Extract chapters from first page
        all_chapters = self._extract_chapters_from_page(soup, 1)
        logger.debug(f"Found {len(all_chapters)} chapters on page 1")

        # Determine total number of pages
        total_pages = self._get_total_pages(soup)
        if total_pages <= 1:
            logger.info(f"Only 1 page found, returning {len(all_chapters)} chapters")
            return all_chapters

        logger.info(
            f"Found {total_pages} total pages, fetching remaining pages concurrently"
        )

        # Create tasks for remaining pages (2 to total_pages)
        import asyncio

        # Limit concurrent requests to avoid overwhelming the server
        max_concurrent = (
            self.config.get("chapter_discovery", {})
            .get("pagination", {})
            .get("max_concurrent", 5)
        )
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_page(page_num: int) -> List[Dict[str, str]]:
            async with semaphore:
                page_url = f"{novel_url}?page={page_num}"
                logger.debug(f"Fetching page {page_num}: {page_url}")

                page_soup = await self._get_soup_cached(page_url)
                if page_soup is None:
                    logger.warning(f"Failed to fetch page {page_num}")
                    return []

                chapters = self._extract_chapters_from_page(page_soup, page_num)
                logger.debug(f"Found {len(chapters)} chapters on page {page_num}")
                return chapters

        # Create tasks for pages 2 to total_pages
        tasks = [fetch_page(page_num) for page_num in range(2, total_pages + 1)]

        # Execute all tasks concurrently
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                page_num = i + 2  # Page numbers start from 2
                if isinstance(result, Exception):
                    logger.error(f"Error fetching page {page_num}: {result}")
                elif isinstance(result, list):
                    all_chapters.extend(result)
                else:
                    logger.warning(
                        f"Unexpected result type for page {page_num}: {type(result)}"
                    )

        except Exception as e:
            logger.error(f"Error in concurrent pagination: {e}")

        logger.info(
            f"Found total of {len(all_chapters)} chapters across {total_pages} pages"
        )
        return all_chapters

    def _extract_chapters_from_page(
        self, soup: BeautifulSoup, page_number: int
    ) -> List[Dict[str, str]]:
        """Extract chapters from a single page."""
        chapters = []
        selector = self.config.get("selectors", {}).get("chapter_list")

        if selector:
            chapter_links = soup.select(selector)

            for link in chapter_links:
                chapter_url = link.get("href")
                chapter_title = link.get_text(strip=True) or link.get("title", "")

                if chapter_url and chapter_title:
                    # Make URL absolute
                    if not chapter_url.startswith("http"):
                        chapter_url = urljoin(self.base_url, chapter_url)

                    # Validate chapter URL (filter out error pages)
                    if not self._is_valid_chapter_url(chapter_url):
                        continue

                    # Extract chapter number
                    chapter_number = self._extract_chapter_number(
                        chapter_title, chapter_url
                    )

                    chapters.append(
                        {
                            "title": chapter_title,
                            "url": chapter_url,
                            "number": chapter_number,
                            "page": page_number,
                        }
                    )

        return chapters

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        """Determine total number of pages from pagination."""
        try:
            # Look for the "Last" button which contains the total page number
            last_selector = self.config.get("selectors", {}).get("pagination_last")
            if last_selector:
                last_element = soup.select_one(last_selector)
                if last_element:
                    data_page = last_element.get("data-page")
                    if data_page:
                        # data-page is 0-based, so add 1 for total pages
                        return int(data_page) + 1

            # Fallback: look for pagination links and find the highest page number
            pagination_selector = self.config.get("selectors", {}).get(
                "pagination_links"
            )
            if pagination_selector:
                pagination_links = soup.select(pagination_selector)
                max_page = 1

                for link in pagination_links:
                    data_page = link.get("data-page")
                    if data_page and data_page.isdigit():
                        page_num = int(data_page) + 1  # Convert from 0-based to 1-based
                        max_page = max(max_page, page_num)

                    # Also check the link text for page numbers
                    text = link.get_text(strip=True)
                    if text.isdigit():
                        page_num = int(text)
                        max_page = max(max_page, page_num)

                return max_page

            # Final fallback: look for any pagination indicators
            pagination_container = soup.select_one(".pagination")
            if pagination_container:
                # Look for the highest numbered link
                links = pagination_container.select("a")
                max_page = 1

                for link in links:
                    text = link.get_text(strip=True)
                    if text.isdigit():
                        page_num = int(text)
                        max_page = max(max_page, page_num)

                return max_page

        except (ValueError, TypeError) as e:
            logger.debug(f"Error determining total pages: {e}")

        return 1  # Default to 1 page if we can't determine

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page in pagination."""
        # Check for next button
        next_selector = self.config.get("selectors", {}).get("pagination_next")
        if next_selector:
            next_element = soup.select_one(next_selector)
            if next_element and not next_element.parent.get("class", []):
                # Next button exists and is not disabled
                return True

        # Alternative: check pagination links
        pagination_selector = self.config.get("selectors", {}).get("pagination_links")
        if pagination_selector:
            pagination_links = soup.select(pagination_selector)
            for link in pagination_links:
                if ">" in link.get_text() or "next" in link.get_text().lower():
                    return True

        return False

    def _validate_url(self, url: str) -> bool:
        """Validate if URL belongs to NovelFull."""
        try:
            parsed = urlparse(url)
            return "novelfull.com" in parsed.netloc.lower()
        except Exception:
            return False

    async def scrape_chapters_concurrent(
        self,
        chapter_list: List[Dict[str, str]],
        progress_callback: Optional[callable] = None,
    ) -> List[ChapterData]:
        """
        Scrape multiple chapters concurrently with optimized settings for NovelFull.

        Args:
            chapter_list: List of chapter information dictionaries
            progress_callback: Optional callback for progress updates

        Returns:
            List of successfully scraped ChapterData objects
        """
        logger.info(f"Starting concurrent download of {len(chapter_list)} chapters")

        # Get configuration
        download_config = self.config.get("chapter_downloading", {})
        max_concurrent = download_config.get("max_concurrent", 20)
        chunk_size = download_config.get("chunk_size", 50)
        delay_between_chunks = download_config.get("delay_between_chunks", 0.5)
        retry_failed = download_config.get("retry_failed", True)
        max_retries = download_config.get("max_retries", 3)

        all_chapters = []
        failed_chapters = []

        # Create semaphore for concurrent downloads
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_single_chapter(
            chapter_info: Dict[str, str], attempt: int = 1
        ) -> Optional[ChapterData]:
            """Download a single chapter with retry logic."""
            async with semaphore:
                try:
                    chapter_data = await self.scrape_chapter_content(
                        chapter_info["url"]
                    )
                    if chapter_data:
                        logger.debug(f"Downloaded chapter: {chapter_data.title}")
                        if progress_callback:
                            progress_callback(chapter_data)
                        return chapter_data
                    else:
                        logger.warning(
                            f"Failed to extract content from: {chapter_info['url']}"
                        )
                        return None

                except Exception as e:
                    logger.error(
                        f"Error downloading chapter {chapter_info['url']} (attempt {attempt}): {e}"
                    )
                    if retry_failed and attempt < max_retries:
                        logger.info(
                            f"Retrying chapter {chapter_info['url']} (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(1.0 * attempt)  # Exponential backoff
                        return await download_single_chapter(chapter_info, attempt + 1)
                    return None

        # Process chapters in chunks to manage memory and connections
        total_chunks = (len(chapter_list) + chunk_size - 1) // chunk_size

        for chunk_idx in range(0, len(chapter_list), chunk_size):
            chunk = chapter_list[chunk_idx : chunk_idx + chunk_size]
            chunk_num = chunk_idx // chunk_size + 1

            logger.info(
                f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} chapters)"
            )

            # Create tasks for this chunk
            tasks = [download_single_chapter(chapter_info) for chapter_info in chunk]

            # Execute chunk concurrently
            try:
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, result in enumerate(chunk_results):
                    if isinstance(result, ChapterData):
                        all_chapters.append(result)
                    elif isinstance(result, Exception):
                        logger.error(f"Chapter download exception: {result}")
                        failed_chapters.append(chunk[i])
                    elif result is None:
                        failed_chapters.append(chunk[i])

            except Exception as e:
                logger.error(f"Error processing chunk {chunk_num}: {e}")
                failed_chapters.extend(chunk)

            # Progress update
            completed = len(all_chapters)
            total = len(chapter_list)
            logger.info(
                f"Progress: {completed}/{total} chapters downloaded ({completed/total*100:.1f}%)"
            )

            # Delay between chunks to be respectful to the server
            if chunk_idx + chunk_size < len(chapter_list):
                await asyncio.sleep(delay_between_chunks)

        # Sort chapters by chapter number
        all_chapters.sort(key=lambda x: x.chapter_number or 0)

        # Report results
        success_count = len(all_chapters)
        failed_count = len(failed_chapters)
        total_count = len(chapter_list)

        logger.info(
            f"Chapter download completed: {success_count}/{total_count} successful, {failed_count} failed"
        )

        if failed_chapters:
            logger.warning(
                f"Failed chapters: {[ch.get('title', ch.get('url', 'Unknown')) for ch in failed_chapters[:5]]}"
            )
            if len(failed_chapters) > 5:
                logger.warning(
                    f"... and {len(failed_chapters) - 5} more failed chapters"
                )

        return all_chapters

    def _extract_chapter_number(self, title: str, url: str) -> Optional[int]:
        """Extract chapter number from title or URL."""
        import re

        # Try to extract from title first
        if title:
            # Look for patterns like "Chapter 123", "Ch 123", "123"
            title_patterns = [r"chapter\s*(\d+)", r"ch\s*(\d+)", r"^(\d+)", r"(\d+)"]

            for pattern in title_patterns:
                match = re.search(pattern, title.lower())
                if match:
                    try:
                        return int(match.group(1))
                    except (ValueError, IndexError):
                        continue

        # Try to extract from URL
        if url:
            # Look for patterns like "/chapter-123", "/chapter-123-title"
            url_patterns = [
                r"/chapter-(\d+)",
                r"chapter-(\d+)",
                r"ch-(\d+)",
                r"/(\d+)\.html",
                r"/(\d+)-",
            ]

            for pattern in url_patterns:
                match = re.search(pattern, url.lower())
                if match:
                    try:
                        return int(match.group(1))
                    except (ValueError, IndexError):
                        continue

        return None

    def _convert_html_to_markdown(self, content_elem) -> str:
        """
        Convert HTML content to markdown using markdownify for better formatting.

        Args:
            content_elem: BeautifulSoup element containing HTML content

        Returns:
            Markdown-formatted text content
        """
        if not content_elem:
            return ""

        try:
            # Get the HTML content as string
            html_content = str(content_elem)

            # Configure markdownify options for novel content
            markdown_content = md(
                html_content,
                # Convert headings
                heading_style="ATX",  # Use # style headings
                # Handle emphasis
                emphasis_mark="*",  # Use * for emphasis instead of _
                strong_mark="**",  # Use ** for strong instead of __
                # Strip unwanted tags but keep content
                strip=["script", "style", "meta", "link", "noscript"],
                # Wrap width for better readability
                wrap=True,
                wrap_width=80,
                # Remove extra whitespace
                escape_misc=False,
                # Handle line breaks properly
                newline_exit_br=True,
                # Don't escape markdown characters in novel text
                escape_asterisks=False,
                escape_underscores=False,
            )

            # Post-process the markdown content
            markdown_content = self._post_process_markdown(markdown_content)

            return markdown_content.strip()

        except Exception as e:
            logger.warning(
                f"Error converting HTML to markdown, falling back to text extraction: {e}"
            )
            # Fallback to original method
            return content_elem.get_text(separator="\n", strip=True)

    def _post_process_markdown(self, markdown_content: str) -> str:
        """
        Post-process markdown content to clean up formatting issues.

        Args:
            markdown_content: Raw markdown content from markdownify

        Returns:
            Cleaned markdown content
        """
        import re

        # Remove excessive newlines (more than 2 consecutive)
        markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)

        # Clean up spacing around paragraphs
        markdown_content = re.sub(r"\n\s+\n", "\n\n", markdown_content)

        # Remove markdown artifacts that might interfere with novel text
        # Remove empty emphasis marks
        markdown_content = re.sub(r"\*\*\s*\*\*", "", markdown_content)
        markdown_content = re.sub(r"\*\s*\*", "", markdown_content)

        # Clean up line breaks within paragraphs
        lines = markdown_content.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                # Remove extra spaces
                line = re.sub(r"\s+", " ", line)
                cleaned_lines.append(line)
            else:
                # Preserve empty lines for paragraph breaks
                cleaned_lines.append("")

        # Join lines back together
        result = "\n".join(cleaned_lines)

        # Ensure proper paragraph spacing
        result = re.sub(r"\n\n+", "\n\n", result)

        return result

    def get_max_concurrent_requests(self) -> int:
        """Get maximum concurrent requests from provider config."""
        return self.config.get("chapter_downloading", {}).get("max_concurrent", 10)

    def get_chunk_size(self) -> int:
        """Get chunk size from provider config."""
        return self.config.get("chapter_downloading", {}).get("chunk_size", 50)

    def get_delay_between_chunks(self) -> float:
        """Get delay between chunks from provider config."""
        return self.config.get("chapter_downloading", {}).get(
            "delay_between_chunks", 1.0
        )
