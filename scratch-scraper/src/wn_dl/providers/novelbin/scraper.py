"""
NovelBin scraper implementation.

This module provides a concrete scraper for NovelBin (novelbin.com).
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ...core.base_scraper import BaseNovelScraper
from ...core.models import ChapterData, NovelMetadata, NovelStatus

logger = logging.getLogger(__name__)


class NovelBinScraper(BaseNovelScraper):
    """
    Scraper implementation for NovelBin (novelbin.com).

    Handles extraction of novel metadata and chapter content from NovelBin pages.
    """

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "NovelBin"

    def get_max_concurrent_requests(self) -> int:
        """
        Get maximum concurrent requests for NovelBin.

        NovelBin is very restrictive with rate limiting, so we use
        much lower concurrency than other providers.

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
        Extract novel metadata from NovelBin novel page.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            NovelMetadata object or None if extraction failed
        """
        if not self._validate_url(novel_url):
            logger.error(f"Invalid URL for NovelBin: {novel_url}")
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
            rating, rating_count = self._extract_rating(soup)

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
                provider="novelbin",
                provider_id=self._extract_novel_id(novel_url),
            )

            logger.info(f"Successfully extracted metadata for: {title}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata from {novel_url}: {e}")
            return None

    async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Get list of all available chapters from NovelBin using AJAX endpoint.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            List of dictionaries containing chapter info
        """
        try:
            # Extract novel ID from URL
            novel_id = self._extract_novel_id(novel_url)
            if not novel_id:
                logger.error(f"Could not extract novel ID from URL: {novel_url}")
                return []

            # Use AJAX endpoint to get chapter list
            ajax_url = f"{self.base_url}/ajax/chapter-archive?novelId={novel_id}"

            logger.debug(f"Fetching chapter list from AJAX endpoint: {ajax_url}")

            # Make AJAX request with proper headers
            await self._rate_limit()

            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": novel_url,
                "Accept": "*/*",
            }

            response = self.cloudscraper_session.get(
                ajax_url, headers=headers, timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f"AJAX request failed with status {response.status_code}")
                return await self._fallback_chapter_list(novel_url)

            # Parse the AJAX response
            soup = BeautifulSoup(response.text, "lxml")
            chapters = []

            # Extract chapters from the AJAX response
            # The response contains multiple columns with ul.list-chapter
            chapter_links = soup.select("ul.list-chapter li a")

            for i, link in enumerate(chapter_links):
                chapter_url = link.get("href")
                chapter_title = link.get("title") or link.get_text(strip=True)

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
                            "title": chapter_title.strip(),
                            "url": chapter_url,
                            "number": chapter_number or (i + 1),
                        }
                    )

            logger.info(
                f"Found {len(chapters)} chapters via AJAX for novel: {novel_id}"
            )
            return chapters

        except Exception as e:
            logger.error(f"Error fetching chapter list via AJAX: {e}")
            # Fallback to regular page scraping
            return await self._fallback_chapter_list(novel_url)

    async def _fallback_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Fallback method to get chapter list from main page.

        Args:
            novel_url: URL of the novel's main page

        Returns:
            List of dictionaries containing chapter info
        """
        logger.info("Using fallback method for chapter list extraction")

        soup = await self._get_soup_cached(novel_url)
        if soup is None:
            logger.error(f"Failed to fetch novel page for chapter list: {novel_url}")
            return []

        chapters = []

        try:
            # Try primary selector for chapter list
            selectors = self.config.get("selectors", {})
            chapter_selector = selectors.get("chapter_list")

            if chapter_selector:
                chapter_links = soup.select(chapter_selector)

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

            logger.info(f"Found {len(chapters)} chapters via fallback method")
            return chapters

        except Exception as e:
            logger.error(f"Error in fallback chapter list extraction: {e}")
            return []

    async def scrape_chapter_content(self, chapter_url: str) -> Optional[ChapterData]:
        """
        Extract content from a single NovelBin chapter with enhanced robustness.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            ChapterData object or None if extraction failed
        """
        logger.debug(f"Starting robust chapter extraction for: {chapter_url}")

        soup = await self._get_soup_cached(chapter_url)
        if soup is None:
            logger.error(f"Failed to fetch chapter page: {chapter_url}")
            return None

        try:
            # Validate page structure
            page_title = soup.select_one("title")
            if page_title:
                page_title_text = page_title.get_text().lower()
                if any(
                    error_indicator in page_title_text
                    for error_indicator in [
                        "404",
                        "not found",
                        "error",
                        "access denied",
                    ]
                ):
                    logger.error(
                        f"Chapter page appears to be an error page: {chapter_url}"
                    )
                    return None

            # Extract chapter title with enhanced fallback
            title = self._extract_chapter_title(soup)
            if not title:
                logger.warning(f"Could not extract chapter title from: {chapter_url}")
                title = f"Chapter from {chapter_url.split('/')[-1]}"

            # Extract chapter content with robust strategies
            content = self._extract_chapter_content(soup, title)

            if not content:
                # Provide detailed error context
                self._log_extraction_failure_context(soup, chapter_url)
                logger.error(
                    f"All content extraction strategies failed for: {chapter_url}"
                )
                return None

            # Extract chapter number
            chapter_number = self._extract_chapter_number(title, chapter_url)

            # Try to enhance title from content if it's just "Chapter X"
            enhanced_title = self._extract_title_from_content(
                content, title, chapter_number
            )
            if enhanced_title != title:
                logger.info(f"Enhanced chapter title: '{title}' -> '{enhanced_title}'")
                title = enhanced_title

            # Create chapter data
            chapter_data = ChapterData(
                title=title,
                content=content,
                url=chapter_url,
                chapter_number=chapter_number,
                is_cleaned=True,
            )

            # Calculate word count and validate
            chapter_data.calculate_word_count()

            # Final validation
            if chapter_data.word_count < 10:
                logger.warning(
                    f"Chapter has very low word count ({chapter_data.word_count}): {chapter_url}"
                )

            logger.info(
                f"Successfully extracted chapter: {title} ({chapter_data.word_count} words)"
            )
            return chapter_data

        except Exception as e:
            logger.error(
                f"Unexpected error extracting chapter content from {chapter_url}: {e}",
                exc_info=True,
            )
            return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract novel title."""
        selectors = self.config.get("selectors", {})
        title_selector = selectors.get("title")

        if title_selector:
            title = self._extract_text_by_selector(soup, title_selector)
            if title:
                return title.strip()

        # Fallback selectors
        fallback_selectors = ["h1.title", "h1", ".novel-title", "[itemprop='name']"]
        for selector in fallback_selectors:
            title = self._extract_text_by_selector(soup, selector)
            if title:
                return title.strip()

        return None

    def _extract_author(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract author name."""
        selectors = self.config.get("selectors", {})
        author_selector = selectors.get("author")

        if author_selector:
            author = self._extract_text_by_selector(soup, author_selector)
            if author:
                return author.strip()

        # Fallback selectors
        fallback_selectors = [".author", "[itemprop='author']", "a[href*='/a/']"]
        for selector in fallback_selectors:
            author = self._extract_text_by_selector(soup, selector)
            if author:
                return author.strip()

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract novel description."""
        selectors = self.config.get("selectors", {})
        desc_selector = selectors.get("description")

        if desc_selector:
            desc = self._extract_text_by_selector(soup, desc_selector)
            if desc:
                return desc.strip()

        # Fallback selectors
        fallback_selectors = [".description", ".summary", "[itemprop='description']"]
        for selector in fallback_selectors:
            desc = self._extract_text_by_selector(soup, selector)
            if desc:
                return desc.strip()

        return None

    def _extract_cover_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract cover image URL."""
        selectors = self.config.get("selectors", {})
        cover_selector = selectors.get("cover_image")

        if cover_selector:
            cover_url = self._extract_text_by_selector(soup, cover_selector, "content")
            if cover_url:
                return cover_url

        # Fallback selectors
        fallback_selectors = [
            ("meta[property='og:image']", "content"),
            (".book img", "src"),
            (".cover img", "src"),
            ("img[data-src]", "data-src"),
        ]

        for selector, attr in fallback_selectors:
            cover_url = self._extract_text_by_selector(soup, selector, attr)
            if cover_url:
                return cover_url

        return None

    def _extract_genres(self, soup: BeautifulSoup) -> List[str]:
        """Extract genre list."""
        selectors = self.config.get("selectors", {})
        genre_selector = selectors.get("genres")

        if genre_selector:
            return self._extract_list_by_selector(soup, genre_selector)

        return []

    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract tag list."""
        selectors = self.config.get("selectors", {})
        tag_selector = selectors.get("tags")

        if tag_selector:
            return self._extract_list_by_selector(soup, tag_selector)

        return []

    def _extract_status(self, soup: BeautifulSoup) -> NovelStatus:
        """Extract novel status."""
        selectors = self.config.get("selectors", {})
        status_selector = selectors.get("status")

        if status_selector:
            status_text = self._extract_text_by_selector(soup, status_selector)
            if status_text:
                status_lower = status_text.lower()
                if "completed" in status_lower or "complete" in status_lower:
                    return NovelStatus.COMPLETED
                elif "ongoing" in status_lower or "updating" in status_lower:
                    return NovelStatus.ONGOING
                elif "hiatus" in status_lower or "pause" in status_lower:
                    return NovelStatus.HIATUS
                elif "dropped" in status_lower:
                    return NovelStatus.DROPPED

        return NovelStatus.UNKNOWN

    def _extract_alternative_names(self, soup: BeautifulSoup) -> List[str]:
        """Extract alternative names."""
        import re

        # Look for alternative names in info section
        alt_names = []

        # Try to find alternative names section
        for element in soup.find_all(text=re.compile(r"Alternative\s+names?", re.I)):
            parent = element.parent
            if parent:
                # Get text after the label
                text = parent.get_text()
                # Split by common separators
                names = re.split(r"[,;]", text)
                for name in names:
                    name = name.strip()
                    if name and "alternative" not in name.lower():
                        alt_names.append(name)

        return alt_names

    def _extract_rating(
        self, soup: BeautifulSoup
    ) -> tuple[Optional[float], Optional[int]]:
        """Extract rating and rating count."""
        selectors = self.config.get("selectors", {})

        rating = None
        rating_count = None

        # Extract rating
        rating_selector = selectors.get("rating")
        if rating_selector:
            rating_text = self._extract_text_by_selector(soup, rating_selector)
            if rating_text:
                try:
                    rating = float(rating_text)
                except ValueError:
                    pass

        # Extract rating count
        rating_count_selector = selectors.get("rating_count")
        if rating_count_selector:
            count_text = self._extract_text_by_selector(soup, rating_count_selector)
            if count_text:
                try:
                    rating_count = int(count_text)
                except ValueError:
                    pass

        return rating, rating_count

    def _extract_novel_id(self, novel_url: str) -> Optional[str]:
        """Extract novel ID from URL."""
        import re

        # NovelBin URLs typically have format: /b/novel-slug
        match = re.search(r"/b/([^/]+)", novel_url)
        if match:
            return match.group(1)
        return None

    def _extract_chapter_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract chapter title with fallback strategies."""
        selectors = self.config.get("selectors", {})
        title_selector = selectors.get("chapter_title")

        # Try primary selector first
        if title_selector:
            title = self._extract_text_by_selector(soup, title_selector, "title")
            if not title:
                title = self._extract_text_by_selector(soup, title_selector)
            if title:
                return self._clean_chapter_title(title.strip())

        # Try fallback selectors
        fallback_selectors = (
            self.config.get("error_handling", {})
            .get("fallback_selectors", {})
            .get("chapter_title", [])
        )
        for selector in fallback_selectors:
            title = self._extract_text_by_selector(soup, selector)
            if title and len(title.strip()) > 0:
                logger.debug(
                    f"Chapter title extracted using fallback selector: {selector}"
                )
                return self._clean_chapter_title(title.strip())

        # Last resort: try to extract from page title
        page_title = soup.select_one("title")
        if page_title:
            title_text = page_title.get_text().strip()
            # Look for chapter patterns in page title
            import re

            chapter_match = re.search(r"(chapter\s*\d+[^|]*)", title_text, re.I)
            if chapter_match:
                logger.debug("Chapter title extracted from page title")
                return self._clean_chapter_title(chapter_match.group(1).strip())

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
    ) -> Optional[str]:
        """Extract and clean chapter content with robust fallback strategies."""
        extraction_strategies = self.config.get("error_handling", {}).get(
            "extraction_strategies", {}
        )

        # Strategy 1: Primary selector with cleaning
        if extraction_strategies.get("primary", {}).get("enabled", True):
            content = self._extract_content_primary(soup, chapter_title)
            if self._validate_content_quality(content):
                logger.debug("Content extracted using primary strategy")
                return content

        # Strategy 2: Fallback selectors
        if extraction_strategies.get("fallback", {}).get("enabled", True):
            content = self._extract_content_fallback(soup, chapter_title)
            if self._validate_content_quality(content):
                logger.debug("Content extracted using fallback strategy")
                return content

        # Strategy 3: Text-based extraction
        if extraction_strategies.get("text_based", {}).get("enabled", True):
            content = self._extract_content_text_based(soup, chapter_title)
            if self._validate_content_quality(content):
                logger.debug("Content extracted using text-based strategy")
                return content

        # Strategy 4: Partial content recovery
        if extraction_strategies.get("partial_recovery", {}).get("enabled", True):
            content = self._extract_content_partial(soup, chapter_title)
            if self._validate_content_quality(content, allow_partial=True):
                logger.warning("Only partial content could be extracted")
                return content

        logger.error("All content extraction strategies failed")
        return None

    def _extract_novel_id(self, novel_url: str) -> Optional[str]:
        """
        Extract novel ID from NovelBin URL.

        Args:
            novel_url: URL of the novel page

        Returns:
            Novel ID or None if not found
        """
        try:
            # NovelBin URLs are in format: https://novelbin.com/b/{novel-id}
            # Extract the novel ID from the URL path
            from urllib.parse import urlparse

            parsed = urlparse(novel_url)
            path_parts = parsed.path.strip("/").split("/")

            if len(path_parts) >= 2 and path_parts[0] == "b":
                return path_parts[1]

            logger.error(f"Could not extract novel ID from URL: {novel_url}")
            return None

        except Exception as e:
            logger.error(f"Error extracting novel ID from URL {novel_url}: {e}")
            return None

    def _extract_chapter_number(self, title: str, url: str) -> Optional[int]:
        """Extract chapter number from title or URL."""
        import re

        # Try to extract from title first
        if title:
            match = re.search(r"chapter\s*(\d+)", title, re.I)
            if match:
                return int(match.group(1))

        # Try to extract from URL
        match = re.search(r"chapter-(\d+)", url)
        if match:
            return int(match.group(1))

        return None

    def _extract_content_primary(
        self, soup: BeautifulSoup, chapter_title: str = None
    ) -> Optional[str]:
        """Extract content using primary selector."""
        selectors = self.config.get("selectors", {})
        content_selector = selectors.get("chapter_content")

        if content_selector:
            content_element = soup.select_one(content_selector)
            if content_element:
                # Clean the content
                cleaned_content = self._clean_content(content_element, chapter_title)
                return cleaned_content

        return None

    def _extract_content_fallback(
        self, soup: BeautifulSoup, chapter_title: str = None
    ) -> Optional[str]:
        """Extract content using fallback selectors."""
        fallback_selectors = (
            self.config.get("error_handling", {})
            .get("fallback_selectors", {})
            .get("chapter_content", [])
        )

        for selector in fallback_selectors:
            try:
                content_element = soup.select_one(selector)
                if content_element:
                    cleaned_content = self._clean_content(
                        content_element, chapter_title
                    )
                    if cleaned_content and len(cleaned_content.strip()) > 50:
                        logger.debug(
                            f"Content found using fallback selector: {selector}"
                        )
                        return cleaned_content
            except Exception as e:
                logger.debug(f"Fallback selector {selector} failed: {e}")
                continue

        return None

    def _extract_content_text_based(
        self, soup: BeautifulSoup, chapter_title: str = None
    ) -> Optional[str]:
        """Extract content using text-based analysis."""
        try:
            # Remove unwanted elements first
            for unwanted in soup.select(
                "script, style, nav, header, footer, aside, .advertisement, [class*='ad-'], [id*='ad-']"
            ):
                unwanted.decompose()

            # Find all text blocks that could be content
            potential_content = []

            # Look for paragraphs with substantial text
            for p in soup.find_all(["p", "div"]):
                text = p.get_text(strip=True)
                if len(text) > 50 and not self._is_navigation_text(text):
                    potential_content.append(text)

            if potential_content:
                # Join paragraphs with double newlines
                content = "\n\n".join(potential_content)
                return content

        except Exception as e:
            logger.debug(f"Text-based extraction failed: {e}")

        return None

    def _extract_content_partial(
        self, soup: BeautifulSoup, chapter_title: str = None
    ) -> Optional[str]:
        """Extract partial content when full extraction fails."""
        try:
            # Try to find any substantial text blocks
            text_blocks = []

            # Look for any elements with substantial text
            for element in soup.find_all(["p", "div", "span", "article", "section"]):
                text = element.get_text(strip=True)
                if (
                    len(text) > 100
                    and not self._is_navigation_text(text)
                    and not self._is_advertisement_text(text)
                ):
                    text_blocks.append(text)

            if text_blocks:
                # Take the longest text blocks (likely to be content)
                text_blocks.sort(key=len, reverse=True)
                content = "\n\n".join(text_blocks[:5])  # Take top 5 longest blocks
                return content

        except Exception as e:
            logger.debug(f"Partial content extraction failed: {e}")

        return None

    def _validate_content_quality(
        self, content: Optional[str], allow_partial: bool = False
    ) -> bool:
        """Validate if extracted content meets quality standards."""
        if not content:
            return False

        content = content.strip()
        if not content:
            return False

        validation_config = self.config.get("error_handling", {}).get(
            "content_validation", {}
        )

        # Check minimum length
        min_length = validation_config.get("min_content_length", 100)
        if allow_partial:
            min_length = validation_config.get("min_partial_length", 50)

        if len(content) < min_length:
            logger.debug(f"Content too short: {len(content)} < {min_length}")
            return False

        # Check maximum length (prevent memory issues)
        max_length = validation_config.get("max_content_length", 500000)
        if len(content) > max_length:
            logger.warning(f"Content very long: {len(content)} > {max_length}")
            # Don't reject, but warn

        # Check word count
        word_count = len(content.split())
        min_words = validation_config.get("min_word_count", 20)
        if word_count < min_words:
            logger.debug(f"Too few words: {word_count} < {min_words}")
            return False

        # Check for forbidden patterns (error pages, etc.)
        forbidden_patterns = validation_config.get("forbidden_patterns", [])
        import re

        for pattern in forbidden_patterns:
            if re.search(pattern, content, re.I):
                logger.debug(f"Content matches forbidden pattern: {pattern}")
                return False

        # Check for required patterns (if any)
        required_patterns = validation_config.get("required_patterns", [])
        for pattern in required_patterns:
            if not re.search(pattern, content, re.I):
                logger.debug(f"Content missing required pattern: {pattern}")
                return False

        return True

    def _is_navigation_text(self, text: str) -> bool:
        """Check if text appears to be navigation/menu content."""
        text_lower = text.lower()
        nav_indicators = [
            "next chapter",
            "previous chapter",
            "table of contents",
            "home",
            "menu",
            "navigation",
            "breadcrumb",
            "login",
            "register",
            "search",
            "categories",
            "bookmark",
            "share",
            "subscribe",
            "follow",
            "like",
            "comment",
        ]

        # Short text that contains navigation keywords
        if len(text) < 100:
            for indicator in nav_indicators:
                if indicator in text_lower:
                    return True

        return False

    def _is_advertisement_text(self, text: str) -> bool:
        """Check if text appears to be advertisement content."""
        text_lower = text.lower()
        ad_indicators = [
            "advertisement",
            "sponsored",
            "click here",
            "buy now",
            "discount",
            "offer",
            "deal",
            "promotion",
            "affiliate",
            "banner",
            "popup",
        ]

        for indicator in ad_indicators:
            if indicator in text_lower:
                return True

        return False

    def _clean_content(self, content_element, chapter_title: str = None) -> str:
        """Clean and format chapter content using markdownify or fallback to text extraction."""
        if not content_element:
            return ""

        # Get cleaning configuration
        cleaning_config = self.config.get("content_cleaning", {})
        remove_selectors = cleaning_config.get("remove_selectors", [])

        # Remove unwanted elements
        for selector in remove_selectors:
            for element in content_element.select(selector):
                element.decompose()

        # Use markdownify for better HTML to markdown conversion if enabled
        use_markdownify = cleaning_config.get("use_markdownify", True)

        if use_markdownify:
            content_text = self._convert_html_to_markdown(content_element)
        else:
            # Fallback to text extraction
            content_text = content_element.get_text(separator="\n", strip=True)

        # Apply text processing
        text_processing = cleaning_config.get("text_processing", {})

        if text_processing.get("convert_html_entities", True):
            import html

            content_text = html.unescape(content_text)

        if text_processing.get("normalize_whitespace", True):
            import re

            # Normalize whitespace within lines only, preserve line breaks
            lines = content_text.split("\n")
            normalized_lines = []
            for line in lines:
                # Only normalize spaces/tabs within each line, not newlines
                normalized_line = re.sub(r"[ \t]+", " ", line)
                normalized_lines.append(normalized_line)
            content_text = "\n".join(normalized_lines)

        if text_processing.get("remove_empty_lines", True):
            lines = content_text.split("\n")
            lines = [line.strip() for line in lines if line.strip()]
            content_text = "\n".join(lines)

        if text_processing.get("preserve_paragraph_breaks", True):
            import re

            content_text = re.sub(r"\n+", "\n\n", content_text)

        if text_processing.get("remove_extra_spaces", True):
            import re

            content_text = re.sub(r" +", " ", content_text)

        # Remove duplicate chapter title from content if present
        if chapter_title:
            content_text = self._remove_duplicate_chapter_title(
                content_text, chapter_title
            )

        return content_text.strip()

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

    def _log_extraction_failure_context(
        self, soup: BeautifulSoup, chapter_url: str
    ) -> None:
        """Log detailed context about why content extraction failed."""
        logger.debug("=== Content Extraction Failure Analysis ===")
        logger.debug(f"URL: {chapter_url}")

        # Check page title
        page_title = soup.select_one("title")
        if page_title:
            logger.debug(f"Page title: {page_title.get_text().strip()}")

        # Check if primary selector exists
        selectors = self.config.get("selectors", {})
        primary_selector = selectors.get("chapter_content")
        if primary_selector:
            primary_element = soup.select_one(primary_selector)
            if primary_element:
                logger.debug(
                    f"Primary selector '{primary_selector}' found but content invalid"
                )
                logger.debug(f"Element text length: {len(primary_element.get_text())}")
            else:
                logger.debug(f"Primary selector '{primary_selector}' not found")

        # Check fallback selectors
        fallback_selectors = (
            self.config.get("error_handling", {})
            .get("fallback_selectors", {})
            .get("chapter_content", [])
        )

        found_selectors = []
        for selector in fallback_selectors:
            if soup.select_one(selector):
                found_selectors.append(selector)

        if found_selectors:
            logger.debug(f"Available fallback selectors: {found_selectors}")
        else:
            logger.debug("No fallback selectors found")

        # Check for common content indicators
        content_indicators = ["p", "div", "article", "section"]
        for indicator in content_indicators:
            elements = soup.find_all(indicator)
            if elements:
                total_text = sum(len(el.get_text()) for el in elements)
                logger.debug(
                    f"Found {len(elements)} '{indicator}' elements with {total_text} total characters"
                )

        # Check for error indicators
        error_indicators = soup.select(
            "[class*='error'], [class*='404'], [class*='not-found']"
        )
        if error_indicators:
            logger.debug(f"Found {len(error_indicators)} error indicator elements")

        logger.debug("=== End Failure Analysis ===")

    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get statistics about extraction attempts (for monitoring)."""
        # This could be enhanced to track extraction success rates
        return {
            "provider": "novelbin",
            "extraction_strategies": len(
                self.config.get("error_handling", {}).get("extraction_strategies", {})
            ),
            "fallback_selectors": len(
                self.config.get("error_handling", {})
                .get("fallback_selectors", {})
                .get("chapter_content", [])
            ),
            "validation_enabled": bool(
                self.config.get("error_handling", {}).get("content_validation", {})
            ),
        }
