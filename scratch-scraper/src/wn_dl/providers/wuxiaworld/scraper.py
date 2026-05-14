"""
Wuxiaworld scraper implementation.

This module provides a concrete scraper for Wuxiaworld (wuxiaworld.site).
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...core.base_scraper import BaseNovelScraper
from ...core.models import ChapterData, NovelMetadata, NovelStatus

logger = logging.getLogger(__name__)


class WuxiaworldScraper(BaseNovelScraper):
    """
    Scraper implementation for Wuxiaworld (wuxiaworld.site).

    Handles extraction of novel metadata and chapter content from Wuxiaworld pages.
    Uses AJAX for chapter list retrieval and WordPress/Madara theme selectors.
    """

    def __init__(self, config: Dict[str, Any], session=None):
        """
        Initialize the Wuxiaworld scraper.

        Args:
            config: Configuration dictionary (if empty, will load provider config)
            session: Optional aiohttp session
        """
        # Load provider configuration if not provided
        if not config:
            from ...config import get_provider_config

            try:
                config = get_provider_config("wuxiaworld")
            except Exception as e:
                logger.warning(f"Could not load wuxiaworld provider config: {e}")
                config = {}

        super().__init__(config, session)

    async def _make_post_request(
        self, url: str, headers: Dict[str, str] = None, data: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Make a POST request and return the response text.

        Args:
            url: URL to make POST request to
            headers: Optional headers for the request
            data: Optional data to send in POST body

        Returns:
            Response text or None if request failed
        """
        await self._rate_limit()

        try:
            request_headers = {"User-Agent": self.user_agent}
            if headers:
                request_headers.update(headers)

            async with self.session.post(
                url, headers=request_headers, data=data
            ) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.error(
                        f"POST request failed with status {response.status}: {url}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error making POST request to {url}: {e}")
            return None

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "Wuxiaworld"

    def get_max_concurrent_requests(self) -> int:
        """
        Get maximum concurrent requests for Wuxiaworld.

        Returns:
            Maximum number of concurrent requests
        """
        download_config = self.config.get("chapter_downloading", {})
        return download_config.get("max_concurrent", 3)

    def get_chunk_size(self) -> int:
        """
        Get chunk size for processing chapters.

        Returns:
            Number of chapters to process in each chunk
        """
        download_config = self.config.get("chapter_downloading", {})
        return download_config.get("chunk_size", 10)

    def get_delay_between_chunks(self) -> float:
        """
        Get delay between processing chunks.

        Returns:
            Delay in seconds between chunks
        """
        download_config = self.config.get("chapter_downloading", {})
        return download_config.get("delay_between_chunks", 3.0)

    async def get_novel_metadata(self, novel_url: str) -> Optional[NovelMetadata]:
        """
        Extract novel metadata from Wuxiaworld novel page.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            NovelMetadata object or None if extraction failed
        """
        if not self._validate_url(novel_url):
            logger.error(f"Invalid URL for Wuxiaworld: {novel_url}")
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

            # Extract optional metadata
            cover_url = self._extract_cover_url(soup)
            genres = self._extract_genres(soup)
            tags = self._extract_tags(soup)
            status = self._extract_status(soup)
            alternative_names = self._extract_alternative_names(soup)
            rating = self._extract_rating(soup)
            rating_count = self._extract_rating_count(soup)

            # Create metadata object
            metadata = NovelMetadata(
                title=title,
                author=author,
                description=description or "",
                source_url=novel_url,
                cover_url=cover_url,
                genres=genres,
                tags=tags,
                status=status,
                alternative_names=alternative_names,
                rating=rating,
                rating_count=rating_count,
                provider_id=self.get_provider_name(),
            )

            logger.info(f"Successfully extracted metadata for: {title}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata from {novel_url}: {e}")
            return None

    async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Get list of all chapters using AJAX endpoint.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            List of dictionaries containing chapter info (title, url, number)
        """
        if not self._validate_url(novel_url):
            logger.error(f"Invalid URL for Wuxiaworld: {novel_url}")
            return []

        # Extract novel slug from URL
        novel_slug = self._extract_novel_slug(novel_url)
        if not novel_slug:
            logger.error(f"Could not extract novel slug from URL: {novel_url}")
            return []

        # Build AJAX endpoint URL
        ajax_endpoint = f"{self.base_url}/novel/{novel_slug}/ajax/chapters/"

        try:
            # Prepare AJAX request headers
            ajax_headers = self.config.get("request", {}).get("ajax_headers", {})
            headers = {
                **self.config.get("request", {}).get("headers", {}),
                **ajax_headers,
                "Referer": novel_url,
                "Origin": self.base_url,
            }

            # Make AJAX POST request
            response_text = await self._make_post_request(
                ajax_endpoint,
                headers=headers,
                data={},  # Empty POST data as shown in requirements
            )

            if not response_text:
                logger.error(f"Failed to get AJAX response from: {ajax_endpoint}")
                return []

            # Parse the HTML response
            soup = BeautifulSoup(response_text, "html.parser")
            chapters = self._parse_chapter_list(soup)

            logger.info(f"Found {len(chapters)} chapters for novel: {novel_slug}")
            return chapters

        except Exception as e:
            logger.error(f"Error retrieving chapter list from {ajax_endpoint}: {e}")
            return []

    def _extract_novel_slug(self, novel_url: str) -> Optional[str]:
        """Extract novel slug from the novel URL."""
        try:
            # First validate that this is a wuxiaworld URL
            if not self._validate_url(novel_url):
                return None

            # URL pattern: https://wuxiaworld.site/novel/{slug}/
            parsed = urlparse(novel_url)
            path_parts = [part for part in parsed.path.split("/") if part]

            if len(path_parts) >= 2 and path_parts[0] == "novel":
                slug = path_parts[1]
                logger.debug(f"Extracted novel slug: {slug}")
                return slug

            logger.warning(f"Could not extract slug from URL: {novel_url}")
            return None

        except Exception as e:
            logger.error(f"Error extracting novel slug: {e}")
            return None

    def _parse_chapter_list(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Parse chapter list from AJAX response HTML."""
        chapters = []
        selectors = self.config.get("selectors", {})
        chapter_selector = selectors.get("chapter_list", ".wp-manga-chapter a")

        chapter_elements = soup.select(chapter_selector)

        for element in chapter_elements:
            try:
                chapter_url = element.get("href")
                chapter_title = element.get_text(strip=True)

                if not chapter_url or not chapter_title:
                    continue

                # Ensure absolute URL
                if chapter_url.startswith("/"):
                    chapter_url = urljoin(self.base_url, chapter_url)

                # Validate chapter URL (filter out error pages)
                if not self._is_valid_chapter_url(chapter_url):
                    continue

                # Extract chapter number from URL or title
                chapter_number = self._extract_chapter_number_from_url(chapter_url)
                if chapter_number is None:
                    chapter_number = self._extract_chapter_number_from_title(
                        chapter_title
                    )

                chapter_data = {
                    "title": chapter_title,
                    "url": chapter_url,
                    "number": chapter_number,
                }

                chapters.append(chapter_data)
                logger.debug(f"Parsed chapter: {chapter_title} -> {chapter_url}")

            except Exception as e:
                logger.warning(f"Error parsing chapter element: {e}")
                continue

        # Sort chapters by number if available
        chapters_with_numbers = [ch for ch in chapters if ch["number"] is not None]
        chapters_without_numbers = [ch for ch in chapters if ch["number"] is None]

        if chapters_with_numbers:
            chapters_with_numbers.sort(key=lambda x: x["number"])
            chapters = chapters_with_numbers + chapters_without_numbers

        return chapters

    def _extract_chapter_number_from_url(self, chapter_url: str) -> Optional[int]:
        """Extract chapter number from chapter URL."""
        try:
            # URL pattern: /novel/{slug}/chapter-{number}/
            match = re.search(r"/chapter-(\d+)/?", chapter_url)
            if match:
                return int(match.group(1))
            return None
        except Exception:
            return None

    def _extract_chapter_number_from_title(self, chapter_title: str) -> Optional[int]:
        """Extract chapter number from chapter title."""
        try:
            # Look for patterns like "Chapter 123", "Ch 123", "123 -", etc.
            patterns = [
                r"chapter\s+(\d+)",
                r"ch\s+(\d+)",
                r"^(\d+)\s*[-:]",
                r"(\d+)\s*$",
            ]

            for pattern in patterns:
                match = re.search(pattern, chapter_title.lower())
                if match:
                    return int(match.group(1))

            return None
        except Exception:
            return None

    async def scrape_chapter_content(self, chapter_url: str) -> Optional[ChapterData]:
        """
        Extract content from a single chapter.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            ChapterData object or None if extraction failed
        """
        if not self._validate_url(chapter_url):
            logger.error(f"Invalid chapter URL for Wuxiaworld: {chapter_url}")
            return None

        try:
            # Use cloudscraper for chapter pages (better for bypassing protection)
            soup = await self._get_soup_cached(chapter_url)
            if not soup:
                logger.error(f"Failed to get response from: {chapter_url}")
                return None

            # Extract chapter title
            chapter_title = self._extract_chapter_title(soup)
            if not chapter_title:
                logger.warning(f"Could not extract chapter title from: {chapter_url}")
                chapter_title = "Untitled Chapter"

            # Extract chapter content
            chapter_content = self._extract_chapter_content(soup, chapter_title)
            if not chapter_content:
                logger.error(f"Could not extract chapter content from: {chapter_url}")
                return None

            # Extract chapter number from URL or title
            chapter_number = self._extract_chapter_number_from_url(chapter_url)
            if chapter_number is None:
                chapter_number = self._extract_chapter_number_from_title(chapter_title)

            # Try to enhance title from content if it's just "Chapter X"
            enhanced_title = self._extract_title_from_content(
                chapter_content, chapter_title, chapter_number
            )
            if enhanced_title != chapter_title:
                logger.info(
                    f"Enhanced chapter title: '{chapter_title}' -> '{enhanced_title}'"
                )
                chapter_title = enhanced_title

            # Create ChapterData object
            chapter_data = ChapterData(
                title=chapter_title,
                content=chapter_content,
                url=chapter_url,
                chapter_number=chapter_number,
            )

            logger.debug(f"Successfully extracted chapter: {chapter_title}")
            return chapter_data

        except Exception as e:
            logger.error(f"Error extracting chapter content from {chapter_url}: {e}")
            return None

    def _extract_chapter_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract chapter title from the page."""
        selectors = self.config.get("selectors", {})
        fallback_selectors = self.config.get("error_handling", {}).get(
            "fallback_selectors", {}
        )

        # Try primary selector first
        title_selector = selectors.get("chapter_title", ".entry-header .entry-title")
        title_element = soup.select_one(title_selector)

        if title_element:
            title = title_element.get_text(strip=True)
            if title:
                return self._clean_chapter_title(title)

        # Try fallback selectors
        for fallback_selector in fallback_selectors.get("chapter_title", []):
            title_element = soup.select_one(fallback_selector)
            if title_element:
                title = title_element.get_text(strip=True)
                if title:
                    logger.debug(
                        f"Used fallback selector for title: {fallback_selector}"
                    )
                    return self._clean_chapter_title(title)

        return None

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
    ) -> Optional[str]:
        """Extract and clean chapter content from the page."""
        selectors = self.config.get("selectors", {})
        fallback_selectors = self.config.get("error_handling", {}).get(
            "fallback_selectors", {}
        )

        # Try primary selector first
        content_selector = selectors.get(
            "chapter_content", ".reading-content .text-left"
        )
        content_element = soup.select_one(content_selector)

        if not content_element:
            # Try fallback selectors
            for fallback_selector in fallback_selectors.get("chapter_content", []):
                content_element = soup.select_one(fallback_selector)
                if content_element:
                    logger.debug(
                        f"Used fallback selector for content: {fallback_selector}"
                    )
                    break

        if not content_element:
            logger.error("Could not find chapter content with any selector")
            return None

        # Clean the content
        cleaned_content = self._clean_chapter_content(content_element)

        # Validate content length
        min_length = self.config.get("validation", {}).get(
            "min_chapter_content_length", 50
        )
        if len(cleaned_content) < min_length:
            logger.warning(
                f"Chapter content too short: {len(cleaned_content)} characters"
            )
            return None

        return cleaned_content

    def _clean_chapter_content(self, content_element) -> str:
        """Clean and format chapter content."""
        import re

        # Get cleaning configuration
        cleaning_config = self.config.get("content_cleaning", {})
        remove_selectors = cleaning_config.get("remove_selectors", [])
        text_processing = cleaning_config.get("text_processing", {})

        # Remove unwanted elements
        for selector in remove_selectors:
            for element in content_element.select(selector):
                element.decompose()

        # Use markdownify for better HTML to markdown conversion if enabled
        use_markdownify = cleaning_config.get("use_markdownify", True)

        if use_markdownify:
            content_text = self._convert_html_to_markdown(content_element)
        else:
            # Fallback to original text extraction
            content_text = content_element.get_text(separator="\n", strip=True)

        # Remove any remaining HTML tags that might be embedded as text
        content_text = self._remove_html_tags(content_text)

        # Apply text processing
        if text_processing.get("convert_html_entities", True):
            import html

            content_text = html.unescape(content_text)

        if text_processing.get("normalize_whitespace", True):
            # Normalize whitespace within lines only, preserve line breaks
            lines = content_text.split("\n")
            normalized_lines = []
            for line in lines:
                # Only normalize spaces/tabs within each line, not newlines
                normalized_line = re.sub(r"[ \t]+", " ", line)
                normalized_lines.append(normalized_line)
            content_text = "\n".join(normalized_lines)

        if text_processing.get("remove_empty_lines", True):
            # Remove empty lines
            lines = content_text.split("\n")
            lines = [line.strip() for line in lines if line.strip()]
            content_text = "\n".join(lines)

        if text_processing.get("preserve_paragraph_breaks", True):
            # Ensure paragraph breaks are preserved
            content_text = re.sub(r"\n+", "\n\n", content_text)

        if text_processing.get("remove_extra_spaces", True):
            # Remove extra spaces
            content_text = re.sub(r" +", " ", content_text)

        # Remove duplicate chapter title from content if present
        if chapter_title:
            content_text = self._remove_duplicate_chapter_title(
                content_text, chapter_title
            )

        return content_text.strip()

    def _remove_html_tags(self, text: str) -> str:
        """Remove any remaining HTML tags from text content."""
        if not text:
            return ""

        # Remove HTML tags using regex
        # This handles cases where HTML tags are embedded as text content
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Remove any remaining HTML entities that weren't caught by html.unescape
        text = re.sub(r"&[a-zA-Z0-9#]+;", "", text)

        # Clean up any extra whitespace that might result from tag removal
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def _remove_ads_from_text(self, text: str) -> str:
        """Remove advertisement content from text."""
        if not text:
            return ""

        import re

        # Common ad patterns to remove
        ad_patterns = [
            r"Read latest Chapters at Wuxia World\.Site Only",
            r"Read latest Chapters at.*?Only",
            r"Visit.*?for more chapters",
            r"Support.*?by reading.*?at.*?",
            r"Please read.*?at.*?",
            r"Read.*?chapters.*?at.*?",
            r"Advertisement",
            r"\[Advertisement\]",
            r"<Advertisement>",
            r"Read more at.*?",
            r"Continue reading at.*?",
        ]

        for pattern in ad_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Clean up extra whitespace after ad removal
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    def _validate_url(self, url: str) -> bool:
        """Validate if URL is a valid Wuxiaworld URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc in ["wuxiaworld.site", "www.wuxiaworld.site"]
        except Exception:
            return False

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract novel title from the page."""
        selectors = self.config.get("selectors", {})
        title_selector = selectors.get("title", ".post-title h1")

        title_element = soup.select_one(title_selector)
        if title_element:
            title = title_element.get_text(strip=True)
            logger.debug(f"Extracted title: {title}")
            return title

        # Fallback selectors
        fallback_selectors = (
            self.config.get("error_handling", {})
            .get("fallback_selectors", {})
            .get("title", [])
        )
        for selector in fallback_selectors:
            title_element = soup.select_one(selector)
            if title_element:
                title = title_element.get_text(strip=True)
                logger.debug(
                    f"Extracted title using fallback selector '{selector}': {title}"
                )
                return title

        logger.warning("Could not extract title")
        return None

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author from the page."""
        selectors = self.config.get("selectors", {})
        author_selector = selectors.get("author", ".author-content a")

        author_element = soup.select_one(author_selector)
        if author_element:
            author = author_element.get_text(strip=True)
            logger.debug(f"Extracted author: {author}")
            return author

        # Fallback selectors
        fallback_selectors = (
            self.config.get("error_handling", {})
            .get("fallback_selectors", {})
            .get("author", [])
        )
        for selector in fallback_selectors:
            author_element = soup.select_one(selector)
            if author_element:
                author = author_element.get_text(strip=True)
                logger.debug(
                    f"Extracted author using fallback selector '{selector}': {author}"
                )
                return author

        logger.warning("Could not extract author")
        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract description from the page."""
        selectors = self.config.get("selectors", {})
        description_selector = selectors.get(
            "description", ".description-summary .summary__content"
        )

        description_element = soup.select_one(description_selector)
        if description_element:
            # Remove any nested elements that might contain ads or unwanted content
            for unwanted in description_element.select("script, style, .advertisement"):
                unwanted.decompose()

            description = description_element.get_text(strip=True)
            logger.debug(f"Extracted description: {description[:100]}...")
            return description

        # Fallback selectors
        fallback_selectors = (
            self.config.get("error_handling", {})
            .get("fallback_selectors", {})
            .get("description", [])
        )
        for selector in fallback_selectors:
            description_element = soup.select_one(selector)
            if description_element:
                description = description_element.get_text(strip=True)
                logger.debug(
                    f"Extracted description using fallback selector '{selector}': {description[:100]}..."
                )
                return description

        logger.warning("Could not extract description")
        return None

    def _extract_cover_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract cover image URL from the page."""
        selectors = self.config.get("selectors", {})
        cover_selector = selectors.get("cover_image", ".summary_image img")

        cover_element = soup.select_one(cover_selector)
        if cover_element:
            cover_url = cover_element.get("src") or cover_element.get("data-src")
            if cover_url:
                # Convert relative URLs to absolute
                if cover_url.startswith("//"):
                    cover_url = "https:" + cover_url
                elif cover_url.startswith("/"):
                    cover_url = urljoin(self.base_url, cover_url)
                logger.debug(f"Extracted cover URL: {cover_url}")
                return cover_url

        logger.warning("Could not extract cover URL")
        return None

    def _extract_genres(self, soup: BeautifulSoup) -> List[str]:
        """Extract genres from the page."""
        selectors = self.config.get("selectors", {})
        genres_selector = selectors.get("genres", ".genres-content a")

        genres = []
        genre_elements = soup.select(genres_selector)
        for element in genre_elements:
            genre = element.get_text(strip=True)
            if genre:
                genres.append(genre)

        logger.debug(f"Extracted genres: {genres}")
        return genres

    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract tags from the page."""
        selectors = self.config.get("selectors", {})
        tags_selector = selectors.get("tags", ".tags-content a")

        tags = []
        tag_elements = soup.select(tags_selector)
        for element in tag_elements:
            tag = element.get_text(strip=True)
            if tag:
                tags.append(tag)

        logger.debug(f"Extracted tags: {tags}")
        return tags

    def _extract_status(self, soup: BeautifulSoup) -> NovelStatus:
        """Extract novel status from the page."""
        selectors = self.config.get("selectors", {})
        status_selector = selectors.get("status", ".post-status .summary-content")

        status_element = soup.select_one(status_selector)
        if status_element:
            status_text = status_element.get_text(strip=True).lower()

            if "ongoing" in status_text or "updating" in status_text:
                return NovelStatus.ONGOING
            elif "completed" in status_text or "finished" in status_text:
                return NovelStatus.COMPLETED
            elif "hiatus" in status_text or "paused" in status_text:
                return NovelStatus.HIATUS
            elif "dropped" in status_text or "cancelled" in status_text:
                return NovelStatus.DROPPED

        logger.debug("Could not extract status, defaulting to UNKNOWN")
        return NovelStatus.UNKNOWN

    def _extract_alternative_names(self, soup: BeautifulSoup) -> List[str]:
        """Extract alternative names from the page."""
        import re

        selectors = self.config.get("selectors", {})
        alt_names_selector = selectors.get(
            "alternative_names",
            ".post-content_item:contains('Alternative') .summary-content",
        )

        alt_names = []
        alt_element = soup.select_one(alt_names_selector)
        if alt_element:
            alt_text = alt_element.get_text(strip=True)
            if alt_text and alt_text != "N/A":
                # Split by common separators
                names = re.split(r"[,;|]", alt_text)
                alt_names = [name.strip() for name in names if name.strip()]

        logger.debug(f"Extracted alternative names: {alt_names}")
        return alt_names

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract rating from the page."""
        selectors = self.config.get("selectors", {})
        rating_selector = selectors.get("rating", ".post-total-rating .score")

        rating_element = soup.select_one(rating_selector)
        if rating_element:
            try:
                rating_text = rating_element.get_text(strip=True)
                rating = float(rating_text)
                logger.debug(f"Extracted rating: {rating}")
                return rating
            except (ValueError, TypeError):
                pass

        # Try schema.org markup
        rating_element = soup.select_one("[property='ratingValue']")
        if rating_element:
            try:
                rating_text = rating_element.get_text(strip=True)
                rating = float(rating_text)
                logger.debug(f"Extracted rating from schema.org: {rating}")
                return rating
            except (ValueError, TypeError):
                pass

        logger.debug("Could not extract rating")
        return None

    def _extract_rating_count(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract rating count from the page."""
        import re

        selectors = self.config.get("selectors", {})
        rating_count_selector = selectors.get(
            "rating_count", ".post-total-rating .total"
        )

        rating_count_element = soup.select_one(rating_count_selector)
        if rating_count_element:
            try:
                count_text = rating_count_element.get_text(strip=True)
                count = int(re.sub(r"[^\d]", "", count_text))
                logger.debug(f"Extracted rating count: {count}")
                return count
            except (ValueError, TypeError):
                pass

        # Try schema.org markup
        rating_count_element = soup.select_one("[property='ratingCount']")
        if rating_count_element:
            try:
                count_text = rating_count_element.get_text(strip=True)
                count = int(re.sub(r"[^\d]", "", count_text))
                logger.debug(f"Extracted rating count from schema.org: {count}")
                return count
            except (ValueError, TypeError):
                pass

        logger.debug("Could not extract rating count")
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
