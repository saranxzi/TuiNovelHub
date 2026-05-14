"""
NovelBuddy scraper implementation.

This module provides a concrete scraper for NovelBuddy (novelbuddy.com).
Handles AJAX-based chapter discovery and novel ID extraction.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...core.base_scraper import BaseNovelScraper
from ...core.cache_config import CacheConfig
from ...core.models import ChapterData, NovelMetadata, NovelStatus

logger = logging.getLogger(__name__)


class NovelBuddyScraper(BaseNovelScraper):
    """
    Scraper implementation for NovelBuddy (novelbuddy.com).

    Handles extraction of novel metadata and chapter content from NovelBuddy pages.
    Uses AJAX for chapter list retrieval and requires novel ID extraction.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        session=None,
        cache_config: Optional[CacheConfig] = None,
    ):
        """
        Initialize the NovelBuddy scraper.

        Args:
            config: Configuration dictionary (if empty, will load provider config)
            session: Optional aiohttp session
            cache_config: Optional cache configuration
        """
        # Load provider configuration if not provided
        if not config:
            from ...config import get_provider_config

            try:
                config = get_provider_config("novelbuddy")
            except Exception as e:
                logger.warning(f"Could not load novelbuddy provider config: {e}")
                config = {}

        super().__init__(config, session, cache_config)

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "NovelBuddy"

    def get_max_concurrent_requests(self) -> int:
        """
        Get maximum concurrent requests for NovelBuddy.

        Returns:
            Maximum number of concurrent requests
        """
        download_config = self.config.get("chapter_downloading", {})
        return download_config.get("max_concurrent", 2)

    def get_chunk_size(self) -> int:
        """
        Get chunk size for batch processing.

        Returns:
            Number of chapters to process in each chunk
        """
        download_config = self.config.get("chapter_downloading", {})
        return download_config.get("chunk_size", 5)

    def get_delay_between_chunks(self) -> float:
        """
        Get delay between chunks in seconds.

        Returns:
            Delay in seconds between processing chunks
        """
        download_config = self.config.get("chapter_downloading", {})
        return download_config.get("delay_between_chunks", 5.0)

    async def extract_novel_id(self, novel_url: str) -> Optional[str]:
        """
        Extract the numeric novel ID from a NovelBuddy novel page.

        This is critical for AJAX API calls which require the numeric ID.

        Args:
            novel_url: URL of the novel page

        Returns:
            Numeric novel ID as string, or None if extraction failed
        """
        try:
            # Get the novel page HTML
            soup = await self._get_soup_cached(novel_url)
            if not soup:
                logger.error(f"Failed to fetch novel page: {novel_url}")
                return None

            # Method 1: Extract from JavaScript variables
            novel_id = self._extract_id_from_javascript(str(soup))
            if novel_id:
                logger.info(f"Extracted novel ID from JavaScript: {novel_id}")
                return novel_id

            # Method 2: Look for data attributes or hidden inputs
            novel_id = self._extract_id_from_attributes(soup)
            if novel_id:
                logger.info(f"Extracted novel ID from attributes: {novel_id}")
                return novel_id

            # Method 3: Try to find ID in AJAX requests or API calls
            novel_id = self._extract_id_from_ajax_patterns(str(soup))
            if novel_id:
                logger.info(f"Extracted novel ID from AJAX patterns: {novel_id}")
                return novel_id

            logger.error(f"Could not extract novel ID from: {novel_url}")
            return None

        except Exception as e:
            logger.error(f"Error extracting novel ID from {novel_url}: {e}")
            return None

    def _extract_id_from_javascript(self, html_content: str) -> Optional[str]:
        """
        Extract novel ID from JavaScript variables in the HTML.

        Args:
            html_content: Raw HTML content of the page

        Returns:
            Novel ID as string or None if not found
        """
        import re

        try:
            # Look for bookId variable
            bookid_pattern = r"var\s+bookId\s*=\s*(\d+)"
            match = re.search(bookid_pattern, html_content)
            if match:
                return match.group(1)

            # Look for mangaId variable (alternative)
            mangaid_pattern = r"var\s+mangaId\s*=\s*(\d+)"
            match = re.search(mangaid_pattern, html_content)
            if match:
                return match.group(1)

            # Look for other common patterns
            patterns = [
                r"bookId\s*:\s*(\d+)",
                r"mangaId\s*:\s*(\d+)",
                r'"id"\s*:\s*(\d+)',
                r"novel_id\s*=\s*(\d+)",
                r"manga_id\s*=\s*(\d+)",
            ]

            for pattern in patterns:
                match = re.search(pattern, html_content)
                if match:
                    return match.group(1)

            return None

        except Exception as e:
            logger.error(f"Error extracting ID from JavaScript: {e}")
            return None

    def _parse_novel_status(self, status_text: Optional[str]) -> NovelStatus:
        """
        Parse novel status from text.

        Args:
            status_text: Raw status text from the page

        Returns:
            NovelStatus enum value
        """
        if not status_text:
            return NovelStatus.UNKNOWN

        status_text = status_text.lower().strip()

        if "ongoing" in status_text or "updating" in status_text:
            return NovelStatus.ONGOING
        elif "completed" in status_text or "complete" in status_text:
            return NovelStatus.COMPLETED
        elif "hiatus" in status_text or "pause" in status_text:
            return NovelStatus.HIATUS
        elif "dropped" in status_text or "discontinued" in status_text:
            return NovelStatus.DROPPED
        else:
            return NovelStatus.UNKNOWN

    def _extract_id_from_attributes(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract novel ID from HTML attributes or data elements.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Novel ID as string or None if not found
        """
        try:
            # Look for data attributes
            for attr in ["data-novel-id", "data-manga-id", "data-book-id", "data-id"]:
                element = soup.find(attrs={attr: True})
                if element:
                    return element.get(attr)

            # Look for hidden inputs
            for name in ["novel_id", "manga_id", "book_id", "id"]:
                input_elem = soup.find("input", {"name": name, "type": "hidden"})
                if input_elem and input_elem.get("value"):
                    return input_elem.get("value")

            # Look for meta tags
            for name in ["novel-id", "manga-id", "book-id"]:
                meta_elem = soup.find("meta", {"name": name})
                if meta_elem and meta_elem.get("content"):
                    return meta_elem.get("content")

            return None

        except Exception as e:
            logger.error(f"Error extracting ID from attributes: {e}")
            return None

    def _extract_id_from_ajax_patterns(self, html_content: str) -> Optional[str]:
        """
        Extract novel ID from AJAX URL patterns in the HTML.

        Args:
            html_content: Raw HTML content of the page

        Returns:
            Novel ID as string or None if not found
        """
        try:
            # Look for API endpoint patterns
            api_patterns = [
                r"/api/manga/(\d+)/chapters",
                r"/api/novel/(\d+)/",
                r"/manga/(\d+)/chapters",
                r'manga_id["\']?\s*:\s*["\']?(\d+)',
                r'novel_id["\']?\s*:\s*["\']?(\d+)',
            ]

            for pattern in api_patterns:
                match = re.search(pattern, html_content)
                if match:
                    return match.group(1)

            return None

        except Exception as e:
            logger.error(f"Error extracting ID from AJAX patterns: {e}")
            return None

    async def _make_ajax_request(
        self,
        url: str,
        headers: Dict[str, str] = None,
        data: Dict[str, Any] = None,
        expected_type: str = "json",
    ) -> Optional[Dict[str, Any]]:
        """
        Make an AJAX request and return the response.

        Args:
            url: URL to make AJAX request to
            headers: Optional headers for the request
            data: Optional data to send in request body
            expected_type: Expected response type ("json" or "html")

        Returns:
            Response as dict or None if request failed
        """
        await self._rate_limit()

        try:
            request_headers = {"User-Agent": self.user_agent}

            # Add AJAX-specific headers from config
            ajax_headers = self.config.get("request", {}).get("ajax_headers", {})
            request_headers.update(ajax_headers)

            if headers:
                request_headers.update(headers)

            async with self.session.get(
                url, headers=request_headers, params=data
            ) as response:
                if response.status == 200:
                    if expected_type == "html":
                        # Expecting HTML response
                        text_content = await response.text()
                        logger.debug(f"Received HTML response from: {url}")
                        return {"html": text_content}
                    else:
                        # Expecting JSON response
                        try:
                            return await response.json()
                        except (json.JSONDecodeError, aiohttp.ContentTypeError):
                            # If not JSON, return text content with warning
                            text_content = await response.text()
                            logger.warning(
                                f"AJAX response was not JSON, got HTML instead: {url}"
                            )
                            return {"html": text_content}
                else:
                    logger.error(
                        f"AJAX request failed with status {response.status}: {url}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error making AJAX request to {url}: {e}")
            return None

    async def get_novel_metadata(self, novel_url: str) -> Optional[NovelMetadata]:
        """
        Extract novel metadata from NovelBuddy novel page.

        Args:
            novel_url: URL of the novel page

        Returns:
            NovelMetadata object or None if extraction failed
        """
        try:
            # First extract the novel ID - this is critical for NovelBuddy
            novel_id = await self.extract_novel_id(novel_url)
            if not novel_id:
                logger.error(f"Could not extract novel ID from {novel_url}")
                return None

            # Get the novel page HTML
            soup = await self._get_soup_cached(novel_url)
            if not soup:
                return None
            selectors = self.config.get("selectors", {})

            # Extract basic metadata
            title = self._extract_text_by_selector(soup, selectors.get("title", "h1"))
            if not title:
                logger.error(f"Could not extract title from {novel_url}")
                return None

            author = self._extract_text_by_selector(
                soup, selectors.get("author", "p strong")
            )
            description = self._extract_text_by_selector(
                soup, selectors.get("description", "div.section-body.summary p.content")
            )

            # Handle lazy-loaded cover images
            cover_url = self._extract_cover_image(
                soup, selectors.get("cover_image", "img.lazy[data-src]")
            )
            if cover_url:
                cover_url = urljoin(novel_url, cover_url)

            # Extract additional metadata
            genres = self._extract_list_by_selector(
                soup, selectors.get("genres", ".genres-content a")
            )
            # Clean genres list - remove empty strings and extra whitespace
            genres = [genre.strip() for genre in genres if genre.strip()]

            tags = self._extract_list_by_selector(
                soup, selectors.get("tags", ".tags-content a")
            )
            # Clean tags list - remove empty strings and extra whitespace
            tags = [tag.strip() for tag in tags if tag.strip()]

            status_text = self._extract_text_by_selector(
                soup, selectors.get("status", ".post-status .summary-content")
            )
            status = self._parse_novel_status(status_text)

            # Store novel ID for later use
            metadata = NovelMetadata(
                title=title,
                author=author or "Unknown",
                description=description or "",
                source_url=novel_url,
                cover_url=cover_url,
                genres=genres,
                tags=tags,
                status=status,
                provider="NovelBuddy",
                provider_id=novel_id,  # Store the extracted ID
            )

            logger.info(
                f"Successfully extracted metadata for: {title} (ID: {novel_id})"
            )
            return metadata

        except Exception as e:
            logger.error(f"Error extracting novel metadata from {novel_url}: {e}")
            return None

    def _extract_cover_image(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """
        Extract cover image URL, handling lazy-loaded images.

        Args:
            soup: BeautifulSoup object
            selector: CSS selector for cover image

        Returns:
            Cover image URL or None if not found
        """
        try:
            img_elem = soup.select_one(selector)
            if not img_elem:
                return None

            # Check for lazy-loaded image (data-src)
            cover_url = img_elem.get("data-src")
            if cover_url:
                return cover_url

            # Fallback to regular src
            cover_url = img_elem.get("src")
            return cover_url

        except Exception as e:
            logger.error(f"Error extracting cover image: {e}")
            return None

    async def get_chapter_list(
        self, novel_url: str, novel_metadata: NovelMetadata = None
    ) -> List[Dict[str, str]]:
        """
        Get list of chapters using AJAX API.

        Args:
            novel_url: URL of the novel page
            novel_metadata: Optional novel metadata containing novel_id

        Returns:
            List of ChapterData objects
        """
        try:
            # Get novel ID from metadata or extract it
            novel_id = None
            if novel_metadata and hasattr(novel_metadata, "novel_id"):
                novel_id = novel_metadata.novel_id

            if not novel_id:
                novel_id = await self.extract_novel_id(novel_url)

            if not novel_id:
                logger.error(f"Could not get novel ID for chapter list: {novel_url}")
                return []

            # Build AJAX endpoint URL
            discovery_config = self.config.get("chapter_discovery", {})
            ajax_endpoint = discovery_config.get(
                "ajax_endpoint", "/api/manga/{novel_id}/chapters?source=detail"
            )
            ajax_url = ajax_endpoint.format(novel_id=novel_id)

            base_url = self.config.get("provider", {}).get(
                "base_url", "https://novelbuddy.com"
            )
            full_ajax_url = urljoin(base_url, ajax_url)

            logger.info(f"Fetching chapter list from: {full_ajax_url}")

            # Get expected response type from config
            discovery_config = self.config.get("chapter_discovery", {})
            expected_response_type = discovery_config.get("ajax_response_type", "json")

            # Make AJAX request
            response_data = await self._make_ajax_request(
                full_ajax_url, expected_type=expected_response_type
            )
            if not response_data:
                logger.error(f"Failed to get chapter list from AJAX: {full_ajax_url}")
                return []

            # Parse chapter list from response
            chapters = self._parse_ajax_chapter_list(response_data, novel_url)

            logger.info(f"Found {len(chapters)} chapters for novel ID {novel_id}")
            return chapters

        except Exception as e:
            logger.error(f"Error getting chapter list for {novel_url}: {e}")
            return []

    def _parse_ajax_chapter_list(
        self, response_data: Dict[str, Any], novel_url: str
    ) -> List[Dict[str, str]]:
        """
        Parse chapter list from AJAX response.

        Args:
            response_data: JSON response from AJAX request
            novel_url: Base novel URL for building chapter URLs

        Returns:
            List of dictionaries containing chapter info (title, url, number)
        """
        chapters = []

        try:
            # Handle different response formats
            if "html" in response_data:
                # Response contains HTML content
                html_content = response_data["html"]
                soup = BeautifulSoup(html_content, "html.parser")

                # Parse chapter list from HTML
                selectors = self.config.get("selectors", {})
                chapter_elements = soup.select(
                    selectors.get("chapter_list", "ul.chapter-list li")
                )

                for i, chapter_elem in enumerate(chapter_elements):
                    chapter_data = self._parse_chapter_element(
                        chapter_elem, i + 1, novel_url
                    )
                    if chapter_data:
                        chapters.append(chapter_data)

            elif "chapters" in response_data:
                # Response contains chapter data directly
                chapter_list = response_data["chapters"]
                for i, chapter_info in enumerate(chapter_list):
                    chapter_data = self._parse_chapter_json(
                        chapter_info, i + 1, novel_url
                    )
                    if chapter_data:
                        chapters.append(chapter_data)

            elif "html" in response_data:
                # Response contains HTML content - parse the chapter list
                html_content = response_data["html"]
                soup = BeautifulSoup(html_content, "html.parser")

                # Parse chapter list from HTML structure using configured selectors
                selectors = self.config.get("selectors", {})
                chapter_list_selector = selectors.get(
                    "chapter_list", "ul.chapter-list li"
                )

                chapter_elements = soup.select(chapter_list_selector)
                logger.debug(
                    f"Found {len(chapter_elements)} chapter elements using selector: {chapter_list_selector}"
                )

                for i, element in enumerate(chapter_elements):
                    chapter_data = self._parse_chapter_element(
                        element, i + 1, novel_url
                    )
                    if chapter_data:
                        chapters.append(chapter_data)

            else:
                logger.warning(
                    f"Unknown AJAX response format: {list(response_data.keys())}"
                )

        except Exception as e:
            logger.error(f"Error parsing AJAX chapter list: {e}")

        return chapters

    def _parse_chapter_element(
        self, chapter_elem, chapter_number: int, novel_url: str
    ) -> Optional[Dict[str, str]]:
        """
        Parse a single chapter element from HTML.

        Args:
            chapter_elem: BeautifulSoup element containing chapter info
            chapter_number: Chapter number
            novel_url: Base novel URL

        Returns:
            Dictionary containing chapter info or None if parsing failed
        """
        try:
            selectors = self.config.get("selectors", {})

            # Extract chapter link
            link_elem = chapter_elem.select_one(selectors.get("chapter_link", "a"))
            if not link_elem:
                return None

            chapter_url = link_elem.get("href")
            if not chapter_url:
                return None

            # Make URL absolute
            if not chapter_url.startswith("http"):
                base_url = self.config.get("provider", {}).get(
                    "base_url", "https://novelbuddy.com"
                )
                chapter_url = urljoin(base_url, chapter_url)

            # Validate chapter URL (filter out error pages)
            if not self._is_valid_chapter_url(chapter_url):
                return None

            # Extract chapter title - try specific selector first, then fallback
            title_elem = link_elem.select_one(".chapter-title")
            if not title_elem:
                title_elem = link_elem.select_one("strong.chapter-title")
            if not title_elem:
                title_elem = link_elem

            chapter_title = (
                title_elem.get_text(strip=True)
                if title_elem
                else f"Chapter {chapter_number}"
            )

            # Extract chapter number from title or URL
            extracted_number = self._extract_chapter_number(chapter_title, chapter_url)
            if extracted_number:
                chapter_number = extracted_number

            return {
                "title": chapter_title,
                "url": chapter_url,
                "number": chapter_number,
            }

        except Exception as e:
            logger.error(f"Error parsing chapter element: {e}")
            return None

    def _parse_chapter_json(
        self, chapter_info: Dict[str, Any], chapter_number: int, novel_url: str
    ) -> Optional[Dict[str, str]]:
        """
        Parse a single chapter from JSON data.

        Args:
            chapter_info: Dictionary containing chapter information
            chapter_number: Chapter number
            novel_url: Base novel URL

        Returns:
            Dictionary containing chapter info or None if parsing failed
        """
        try:
            # Extract chapter URL
            chapter_url = chapter_info.get("url") or chapter_info.get("link")
            if not chapter_url:
                return None

            # Make URL absolute
            if not chapter_url.startswith("http"):
                base_url = self.config.get("provider", {}).get(
                    "base_url", "https://novelbuddy.com"
                )
                chapter_url = urljoin(base_url, chapter_url)

            # Validate chapter URL (filter out error pages)
            if not self._is_valid_chapter_url(chapter_url):
                return None

            # Extract chapter title
            chapter_title = (
                chapter_info.get("title")
                or chapter_info.get("name")
                or f"Chapter {chapter_number}"
            )

            return {
                "title": chapter_title,
                "url": chapter_url,
                "number": chapter_number,
            }

        except Exception as e:
            logger.error(f"Error parsing chapter JSON: {e}")
            return None

    async def scrape_chapter_content(self, chapter_url: str) -> Optional[ChapterData]:
        """
        Scrape content from a NovelBuddy chapter page.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            ChapterData object or None if extraction failed
        """
        try:
            soup = await self._get_soup_cached(chapter_url)
            if not soup:
                return None
            selectors = self.config.get("selectors", {})

            # Extract chapter title
            title_selector = selectors.get(
                "chapter_title_page", "h1, .chapter-title, .entry-title"
            )
            title_elem = soup.select_one(title_selector)

            # Debug logging to see what we're finding
            if title_elem:
                chapter_title = title_elem.get_text(strip=True)
                # Clean the title - remove novel name prefix if present
                chapter_title = self._clean_chapter_title(chapter_title)
                logger.debug(
                    f"Found chapter title with selector '{title_selector}': {chapter_title}"
                )
            else:
                logger.warning(
                    f"No chapter title found with selector '{title_selector}' on {chapter_url}"
                )
                # Try fallback selectors
                fallback_selectors = ["h1", ".chapter-title", ".entry-title", "title"]
                for fallback in fallback_selectors:
                    fallback_elem = soup.select_one(fallback)
                    if fallback_elem:
                        chapter_title = fallback_elem.get_text(strip=True)
                        logger.info(
                            f"Found chapter title with fallback selector '{fallback}': {chapter_title}"
                        )
                        break
                else:
                    chapter_title = "Untitled Chapter"
                    logger.warning(
                        f"No chapter title found with any selector on {chapter_url}"
                    )

            # Extract chapter content
            content_selector = selectors.get(
                "chapter_content", "div.chapter__content div.content-inner"
            )
            content_elem = soup.select_one(content_selector)

            if not content_elem:
                # Try fallback selectors
                fallback_selectors = (
                    self.config.get("error_handling", {})
                    .get("fallback_selectors", {})
                    .get("chapter_content", [])
                )
                for fallback_selector in fallback_selectors:
                    content_elem = soup.select_one(fallback_selector)
                    if content_elem:
                        logger.info(f"Used fallback selector: {fallback_selector}")
                        break

            if not content_elem:
                logger.error(f"Could not find chapter content in: {chapter_url}")
                return None

            # Clean the chapter title first
            chapter_title = self._clean_chapter_title(chapter_title)

            # Clean the content and remove duplicate chapter title
            cleaned_content = self._clean_chapter_content(content_elem, chapter_title)

            if not cleaned_content or len(cleaned_content.strip()) < 50:
                logger.warning(f"Chapter content too short or empty: {chapter_url}")
                return None

            # Extract chapter number from title or URL
            chapter_number = self._extract_chapter_number(chapter_title, chapter_url)

            # Try to enhance title from content if it's just "Chapter X"
            enhanced_title = self._extract_title_from_content(
                cleaned_content, chapter_title, chapter_number
            )
            if enhanced_title != chapter_title:
                logger.info(
                    f"Enhanced chapter title: '{chapter_title}' -> '{enhanced_title}'"
                )
                chapter_title = enhanced_title

            # Create ChapterData object
            chapter_data = ChapterData(
                title=chapter_title,
                content=cleaned_content,
                url=chapter_url,
                chapter_number=chapter_number,
                is_cleaned=True,
            )

            # Calculate word count
            chapter_data.calculate_word_count()

            logger.debug(f"Successfully extracted content from: {chapter_url}")
            return chapter_data

        except Exception as e:
            logger.error(f"Error scraping chapter content from {chapter_url}: {e}")
            return None

    def _clean_chapter_content(self, content_elem, chapter_title: str = None) -> str:
        """
        Clean chapter content by removing unwanted elements and formatting text.

        Args:
            content_elem: BeautifulSoup element containing chapter content

        Returns:
            Cleaned content as string
        """
        try:
            # Remove unwanted elements
            cleaning_config = self.config.get("content_cleaning", {})
            remove_selectors = cleaning_config.get("remove_selectors", [])

            for selector in remove_selectors:
                for elem in content_elem.select(selector):
                    elem.decompose()

            # Use markdownify for better HTML to markdown conversion
            use_markdownify = cleaning_config.get("use_markdownify", True)

            if use_markdownify:
                text_content = self._convert_html_to_markdown(content_elem)
            else:
                # Fallback to original method
                text_content = self._extract_paragraphs_with_breaks(content_elem)

            # Apply text processing
            text_processing = cleaning_config.get("text_processing", {})

            if text_processing.get("remove_html_tags", True):
                # Remove any remaining HTML tags
                import re

                text_content = re.sub(r"<[^>]+>", "", text_content)

            if text_processing.get("normalize_whitespace", True):
                # Normalize whitespace within lines only, preserve line breaks
                lines = text_content.split("\n")
                normalized_lines = []
                for line in lines:
                    # Only normalize spaces/tabs within each line, not newlines
                    normalized_line = re.sub(r"[ \t]+", " ", line)
                    normalized_lines.append(normalized_line)
                text_content = "\n".join(normalized_lines)

            if text_processing.get("remove_empty_lines", True):
                # Remove empty lines
                lines = text_content.split("\n")
                lines = [line.strip() for line in lines if line.strip()]
                text_content = "\n".join(lines)

            if text_processing.get("convert_html_entities", True):
                # Convert HTML entities
                import html

                text_content = html.unescape(text_content)

            if text_processing.get("remove_extra_spaces", True):
                # Remove extra spaces
                text_content = re.sub(r" +", " ", text_content)

            # Preserve paragraph breaks if configured
            if text_processing.get("preserve_paragraph_breaks", True):
                # Add double newlines between paragraphs
                text_content = re.sub(r"\n", "\n\n", text_content)
                # Remove triple+ newlines
                text_content = re.sub(r"\n{3,}", "\n\n", text_content)

            # Remove duplicate chapter title from content if present
            if chapter_title:
                text_content = self._remove_duplicate_chapter_title(
                    text_content, chapter_title
                )

            return text_content.strip()

        except Exception as e:
            logger.error(f"Error cleaning chapter content: {e}")
            return ""

    def _extract_chapter_number(
        self, chapter_title: str, chapter_url: str
    ) -> Optional[int]:
        """
        Extract chapter number from title or URL.

        Args:
            chapter_title: Chapter title text
            chapter_url: Chapter URL

        Returns:
            Chapter number as integer or None if not found
        """
        import re

        try:
            # Try to extract from title first
            title_patterns = [
                r"chapter\s*(\d+)",
                r"ch\s*(\d+)",
                r"c\s*(\d+)",
                r"episode\s*(\d+)",
                r"part\s*(\d+)",
                r"(\d+)",  # Just a number
            ]

            for pattern in title_patterns:
                match = re.search(pattern, chapter_title.lower())
                if match:
                    return int(match.group(1))

            # Try to extract from URL
            url_patterns = [
                r"/chapter-(\d+)",
                r"/ch-(\d+)",
                r"/c-(\d+)",
                r"/(\d+)/?$",
                r"chapter=(\d+)",
                r"ch=(\d+)",
            ]

            for pattern in url_patterns:
                match = re.search(pattern, chapter_url.lower())
                if match:
                    return int(match.group(1))

            return None

        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not extract chapter number: {e}")
            return None

    def _clean_chapter_title(self, title: str) -> str:
        """
        Clean chapter title by removing novel name prefix and other unwanted parts.
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
        pattern1 = r"^.+?(?:–|-)\s*(Chapter\s+\d+.*?)$"
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

        # Check if title is just "Chapter X" without additional text
        chapter_only_match = re.match(r"^Chapter\s+(\d+)$", title, re.IGNORECASE)
        if chapter_only_match:
            # Keep as is - this is a clean chapter title
            pass

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

    def _extract_paragraphs_with_breaks(self, content_elem) -> str:
        """
        Extract text content while preserving proper paragraph structure.

        Args:
            content_elem: BeautifulSoup element containing content

        Returns:
            Text with proper paragraph breaks
        """
        if not content_elem:
            return ""

        paragraphs = []

        # Find all paragraph elements
        p_tags = content_elem.find_all("p")

        if p_tags:
            # Extract text from each paragraph
            for p in p_tags:
                text = p.get_text(strip=True)
                if text and len(text) > 1:  # Skip empty or single-character paragraphs
                    paragraphs.append(text)
        else:
            # Fallback: split by common paragraph indicators
            all_text = content_elem.get_text()
            import re

            # Split by double newlines or other paragraph indicators
            potential_paragraphs = re.split(r"\n\s*\n|\r\n\s*\r\n", all_text)

            for para in potential_paragraphs:
                text = para.strip()
                if text and len(text) > 20:  # Only substantial paragraphs
                    # Clean up whitespace within the paragraph
                    text = re.sub(r"\s+", " ", text)
                    paragraphs.append(text)

        # Join paragraphs with double newlines
        return "\n\n".join(paragraphs)

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
            return self._extract_paragraphs_with_breaks(content_elem)

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
