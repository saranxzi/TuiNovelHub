"""
Markdown parser for EbookLib EPUB generator.

This module handles parsing of markdown files with YAML frontmatter,
extracting chapters, metadata, and content structure for EPUB generation.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ParsedChapter:
    """Represents a parsed chapter from markdown."""

    title: str
    content: str
    anchor: str
    chapter_number: int


@dataclass
class ParsedMarkdownData:
    """Represents parsed markdown file data."""

    metadata: Dict[str, Any]
    chapters: List[ParsedChapter]
    title_page_content: Optional[str] = None
    toc_content: Optional[str] = None


class MarkdownParser:
    """
    Parser for markdown files with YAML frontmatter and chapter structure.

    Handles the specific format used by the web novel scraper, including
    YAML metadata, title pages, table of contents, and chapter boundaries.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize markdown parser with configuration.

        Args:
            config: Parser configuration
        """
        self.config = config
        self.epub_config = config.get("epub", {})
        self.chapter_level = self.epub_config.get("chapter_level", 2)

        logger.debug(
            f"MarkdownParser initialized with chapter_level: {self.chapter_level}"
        )

    def parse_markdown_file(self, markdown_file: str) -> Optional[ParsedMarkdownData]:
        """
        Parse markdown file and extract structure.

        Args:
            markdown_file: Path to markdown file

        Returns:
            Parsed markdown data or None if failed
        """
        try:
            markdown_path = Path(markdown_file)
            if not markdown_path.exists():
                logger.error(f"Markdown file not found: {markdown_file}")
                return None

            # Read file content
            with open(markdown_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse YAML frontmatter
            metadata = self._extract_yaml_frontmatter(content)
            if not metadata:
                logger.error("Failed to extract YAML frontmatter")
                return None

            # Remove YAML frontmatter from content
            content_without_yaml = self._remove_yaml_frontmatter(content)

            # Split content into sections
            sections = self._split_content_sections(content_without_yaml)

            # Extract chapters
            chapters = self._extract_chapters(sections.get("chapters", ""))

            if not chapters:
                logger.warning("No chapters found in markdown file")

            parsed_data = ParsedMarkdownData(
                metadata=metadata,
                chapters=chapters,
                title_page_content=sections.get("title_page"),
                toc_content=sections.get("toc"),
            )

            logger.info(
                f"Successfully parsed markdown file: {len(chapters)} chapters found"
            )
            return parsed_data

        except Exception as e:
            logger.error(f"Error parsing markdown file: {e}")
            return None

    def _extract_yaml_frontmatter(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract YAML frontmatter from markdown content.

        Args:
            content: Full markdown content

        Returns:
            Parsed YAML metadata or None if failed
        """
        try:
            # Look for YAML frontmatter between --- markers
            yaml_pattern = r"^---\s*\n(.*?)\n---\s*\n"
            match = re.match(yaml_pattern, content, re.DOTALL)

            if not match:
                logger.error("No YAML frontmatter found")
                return None

            yaml_content = match.group(1)
            metadata = yaml.safe_load(yaml_content)

            if not isinstance(metadata, dict):
                logger.error("YAML frontmatter is not a dictionary")
                return None

            logger.debug(f"Extracted metadata keys: {list(metadata.keys())}")
            return metadata

        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML frontmatter: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error extracting YAML: {e}")
            return None

    def _remove_yaml_frontmatter(self, content: str) -> str:
        """
        Remove YAML frontmatter from content.

        Args:
            content: Full markdown content

        Returns:
            Content without YAML frontmatter
        """
        yaml_pattern = r"^---\s*\n.*?\n---\s*\n"
        return re.sub(yaml_pattern, "", content, flags=re.DOTALL)

    def _split_content_sections(self, content: str) -> Dict[str, str]:
        """
        Split content into title page, TOC, and chapters sections.

        Args:
            content: Markdown content without YAML frontmatter

        Returns:
            Dictionary with content sections
        """
        sections = {}

        # Look for main title (H1)
        title_match = re.search(r"^# (.+?)$", content, re.MULTILINE)
        if title_match:
            title_start = title_match.start()

            # Look for Table of Contents
            toc_match = re.search(r"^# Table of Contents\s*$", content, re.MULTILINE)
            if toc_match:
                toc_start = toc_match.start()
                sections["title_page"] = content[title_start:toc_start].strip()

                # Find where chapters start (first H2 after TOC)
                chapters_match = re.search(r"^## ", content[toc_start:], re.MULTILINE)
                if chapters_match:
                    chapters_start = toc_start + chapters_match.start()
                    sections["toc"] = content[toc_start:chapters_start].strip()
                    sections["chapters"] = content[chapters_start:].strip()
                else:
                    sections["toc"] = content[toc_start:].strip()
                    sections["chapters"] = ""
            else:
                # No TOC found, look for first chapter
                chapters_match = re.search(r"^## ", content[title_start:], re.MULTILINE)
                if chapters_match:
                    chapters_start = title_start + chapters_match.start()
                    sections["title_page"] = content[title_start:chapters_start].strip()
                    sections["chapters"] = content[chapters_start:].strip()
                else:
                    sections["title_page"] = content[title_start:].strip()
                    sections["chapters"] = ""
        else:
            # No main title found, assume everything is chapters
            sections["chapters"] = content.strip()

        return sections

    def _extract_chapters(self, chapters_content: str) -> List[ParsedChapter]:
        """
        Extract individual chapters from chapters content.

        Args:
            chapters_content: Content containing all chapters

        Returns:
            List of parsed chapters
        """
        chapters = []

        if not chapters_content.strip():
            return chapters

        # Split by chapter headings (H2) but be smarter about it
        chapter_pattern = r"^## (.+?)(?=\{#(.+?)\})?$"

        # Find all H2 headings and their positions
        import re

        h2_matches = list(
            re.finditer(r"^## (.+?)(?:\{#(.+?)\})?$", chapters_content, re.MULTILINE)
        )

        if not h2_matches:
            return chapters

        # Check if intelligent title merging is enabled
        # Support multiple config structures: content_cleaning.text_processing, content_cleaning, and content_processing
        content_cleaning = self.config.get("content_cleaning", {})
        content_processing = self.config.get(
            "content_processing", {}
        )  # NovelFull uses this
        text_processing = content_cleaning.get("text_processing", {})

        # Check all possible locations (don't use 'or' with defaults as it ignores False values)
        intelligent_merging_enabled = True  # Default value
        if "intelligent_title_merging" in text_processing:
            intelligent_merging_enabled = text_processing["intelligent_title_merging"]
        elif "intelligent_title_merging" in content_cleaning:
            intelligent_merging_enabled = content_cleaning["intelligent_title_merging"]
        elif "intelligent_title_merging" in content_processing:
            intelligent_merging_enabled = content_processing[
                "intelligent_title_merging"
            ]

        if intelligent_merging_enabled:
            # Group chapter headings by chapter number to handle merging
            chapter_groups = self._group_chapters_by_number(h2_matches)
        else:
            # Use legacy behavior - treat ALL H2 headings as separate chapters
            chapter_groups = [
                [(match.group(1).strip(), match, i)]
                for i, match in enumerate(h2_matches)
            ]

        chapter_number = 1
        for group_index, chapter_group in enumerate(chapter_groups):
            # Get the best title from the group
            best_title, content_start, _ = self._select_best_title_from_group(
                chapter_group, chapters_content
            )

            if not best_title:
                continue

            # Find content end (start of next chapter group)
            content_end = None
            if group_index + 1 < len(chapter_groups):
                next_group = chapter_groups[group_index + 1]
                if next_group:
                    # Content ends at the start of the next chapter group
                    next_title, next_match, next_index = next_group[0]
                    content_end = next_match.start()

            # Extract content for this chapter
            if content_end is not None:
                content = chapters_content[content_start:content_end].strip()
            else:
                content = chapters_content[content_start:].strip()

            # Remove redundant titles from content if enabled
            if intelligent_merging_enabled:
                # Check for remove_redundant_headings setting (don't use 'or' with defaults)
                remove_redundant = True  # Default value
                if "remove_redundant_headings" in text_processing:
                    remove_redundant = text_processing["remove_redundant_headings"]
                elif "remove_redundant_headings" in content_cleaning:
                    remove_redundant = content_cleaning["remove_redundant_headings"]
                elif "remove_redundant_headings" in content_processing:
                    remove_redundant = content_processing["remove_redundant_headings"]
                if remove_redundant:
                    content = self._remove_redundant_titles_from_group(
                        content, chapter_group, best_title
                    )
                    content = self._remove_all_redundant_headings(content, best_title)

            # Parse title and anchor
            title, anchor = self._parse_chapter_title_and_anchor(best_title)

            if not title:
                logger.warning(f"Skipping chapter with empty title: {best_title}")
                continue

            # Debug logging for problematic chapters
            if title in ["Chapter 1.1", "Chapter 9.1", "Chapter 15.2"]:
                logger.info(
                    f"DEBUG PARSER: {title} - Raw content length: {len(content)}"
                )
                logger.info(
                    f"DEBUG PARSER: {title} - Raw content (first 200 chars): {repr(content[:200])}"
                )

            # Clean up content
            content = self._clean_chapter_content(content, title)

            # Debug logging after cleaning
            if title in ["Chapter 1.1", "Chapter 9.1", "Chapter 15.2"]:
                logger.info(
                    f"DEBUG PARSER: {title} - Cleaned content length: {len(content)}"
                )
                logger.info(
                    f"DEBUG PARSER: {title} - Cleaned content (first 200 chars): {repr(content[:200])}"
                )

            chapter = ParsedChapter(
                title=title,
                content=content,
                anchor=anchor or f"chapter-{chapter_number}",
                chapter_number=chapter_number,
            )

            chapters.append(chapter)
            chapter_number += 1

        logger.debug(f"Extracted {len(chapters)} chapters")
        return chapters

    def _parse_chapter_title_and_anchor(
        self, title_line: str
    ) -> tuple[str, Optional[str]]:
        """
        Parse chapter title and anchor from title line.

        Args:
            title_line: Chapter title line (may include anchor)

        Returns:
            Tuple of (title, anchor)
        """
        # Look for anchor pattern: Title {#anchor}
        anchor_pattern = r"^(.+?)\s*\{#(.+?)\}\s*$"
        match = re.match(anchor_pattern, title_line)

        if match:
            title = match.group(1).strip()
            anchor = match.group(2).strip()
            return title, anchor
        else:
            # No anchor found, use title as-is
            return title_line.strip(), None

    def _clean_chapter_content(self, content: str, chapter_title: str = "") -> str:
        """
        Clean and format chapter content.

        Args:
            content: Raw chapter content
            chapter_title: Chapter title to remove duplicates from content

        Returns:
            Cleaned chapter content
        """
        if not content:
            return ""

        # Remove duplicate chapter titles from content
        content = self._remove_duplicate_chapter_titles(content, chapter_title)

        # Remove advertisement content
        content = self._remove_advertisement_content(content)

        # Remove Pandoc-specific markup
        content = self._remove_pandoc_markup(content)

        # Remove excessive whitespace
        content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)

        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in content.split("\n")]
        content = "\n".join(lines)

        # Remove leading/trailing whitespace
        content = content.strip()

        return content

    def _remove_duplicate_chapter_titles(self, content: str, chapter_title: str) -> str:
        """
        Remove duplicate chapter titles that appear in the content.

        Args:
            content: Chapter content that may contain duplicate titles
            chapter_title: The chapter title to look for and remove

        Returns:
            Content with duplicate chapter titles removed
        """
        if not content or not chapter_title:
            return content

        # Split content into paragraphs
        paragraphs = content.split("\n\n")
        cleaned_paragraphs = []

        # Extract the core title from the chapter title for matching
        core_title = self._extract_core_title(chapter_title)

        for paragraph in paragraphs:
            # Skip empty paragraphs
            if not paragraph.strip():
                continue

            paragraph_text = paragraph.strip()

            # Check if this paragraph is a duplicate chapter title
            if self._is_duplicate_chapter_title(
                paragraph_text, chapter_title, core_title
            ):
                logger.debug(
                    f"Removing duplicate chapter title: {paragraph_text[:50]}..."
                )
                continue  # Skip this paragraph

            cleaned_paragraphs.append(paragraph)

        return "\n\n".join(cleaned_paragraphs)

    def _extract_core_title(self, chapter_title: str) -> str:
        """
        Extract the core title from a chapter title, removing chapter numbers and prefixes.

        Args:
            chapter_title: Full chapter title

        Returns:
            Core title without chapter numbering
        """
        if not chapter_title:
            return ""

        # Remove common chapter prefixes and numbering
        import re

        # Patterns to remove:
        # - "Chapter 246: "
        # - "246. "
        # - "Chapter 246 - 246."
        patterns = [
            r"^Chapter\s+\d+\s*:\s*",  # "Chapter 246: "
            r"^Chapter\s+\d+\s*-\s*\d+\s*[.:]?\s*",  # "Chapter 246 - 246."
            r"^\d+\s*[.:]?\s*",  # "246. " or "246: "
        ]

        core_title = chapter_title
        for pattern in patterns:
            core_title = re.sub(pattern, "", core_title, flags=re.IGNORECASE).strip()

        return core_title

    def _is_duplicate_chapter_title(
        self, paragraph: str, full_title: str, core_title: str
    ) -> bool:
        """
        Check if a paragraph is a duplicate of the chapter title.

        Args:
            paragraph: Paragraph text to check
            full_title: Full chapter title
            core_title: Core title without numbering

        Returns:
            True if paragraph is a duplicate chapter title
        """
        if not paragraph or not core_title:
            return False

        paragraph_lower = paragraph.lower().strip()
        full_title_lower = full_title.lower().strip()
        core_title_lower = core_title.lower().strip()

        # Direct matches
        if paragraph_lower == full_title_lower:
            return True

        if paragraph_lower == core_title_lower:
            return True

        # Check for patterns like "246\.Are You Taking the Beast Tamer Examination?"
        import re

        # Remove escaped characters and check again
        cleaned_paragraph = re.sub(r"\\(.)", r"\1", paragraph_lower)
        if cleaned_paragraph == core_title_lower:
            return True

        # Check for numbered patterns at the start
        # Pattern: "246.Are You Taking..." or "246\.Are You Taking..."
        number_pattern = r"^\d+\\?\.\s*"
        if re.match(number_pattern, paragraph):
            # Remove the number prefix and check if it matches core title
            cleaned = re.sub(number_pattern, "", paragraph, flags=re.IGNORECASE).strip()
            if cleaned.lower() == core_title_lower:
                return True

        # Check for very similar content (high similarity)
        # If the paragraph is mostly the same as the title, it's likely a duplicate
        if len(core_title_lower) > 10:  # Only for substantial titles
            # Simple similarity check: if core title is contained in paragraph or vice versa
            if (
                core_title_lower in paragraph_lower
                or paragraph_lower in core_title_lower
            ):
                # Additional check: ensure they're similar enough in length
                len_ratio = min(len(paragraph_lower), len(core_title_lower)) / max(
                    len(paragraph_lower), len(core_title_lower)
                )
                if len_ratio > 0.7:  # 70% length similarity
                    return True

        return False

    def _remove_advertisement_content(self, content: str) -> str:
        """
        Remove advertisement and promotional content from chapter text.

        Args:
            content: Chapter content that may contain ads

        Returns:
            Content with advertisement paragraphs removed
        """
        if not content:
            return ""

        # Split content into paragraphs
        paragraphs = content.split("\n\n")
        cleaned_paragraphs = []

        for paragraph in paragraphs:
            # Skip empty paragraphs
            if not paragraph.strip():
                continue

            # Check for Unicode-based ads first (like 𝚋𝚎ｄ𝚗ｏｖ𝚎𝚕．ｃｏ𝚖)
            if self._is_unicode_advertisement(paragraph):
                logger.debug(f"Removing Unicode advertisement: {paragraph[:50]}...")
                continue

            # Convert to lowercase for pattern matching (preserve original case)
            paragraph_lower = paragraph.lower().strip()

            # Define advertisement patterns to remove
            # NOTE: These patterns should be specific to avoid false positives with story content
            ad_patterns = [
                # Report chapter/error messages (specific combinations)
                "if you find any errors",
                "ads popup",
                "ads redirect",
                "broken links",
                "non-standard content",
                "report chapter",
                "let us know",
                "fix it as soon as possible",
                # More specific combinations to avoid false positives
                "< report chapter >",
                "&lt; report chapter &gt;",
                # Common ad phrases (specific phrases only)
                "advertisement",
                "sponsored content",
                "click here to",
                "visit our website",
                "subscribe to",
                "follow us on",
                "like us on",
                "share this story",
                "download our app",
                "mobile app download",
                # Promotional content (specific phrases)
                "special offer",
                "limited time offer",
                "discount code",
                "free trial",
                "premium membership",
                "vip membership",
                "support us on patreon",
                "donate to",
                "patreon.com",
                "paypal.me",
                # Navigation elements (specific phrases only)
                "home page",
                "novel list page",
                "bookmark this",
                "add to library",
                "table of contents",
            ]

            # Check if paragraph contains advertisement content
            is_ad = False

            # High-confidence ad patterns (single match is enough)
            high_confidence_patterns = [
                "if you find any errors",
                "ads popup",
                "ads redirect",
                "< report chapter >",
                "&lt; report chapter &gt;",
                "advertisement",
                "sponsored",
                "click here",
                "visit our website",
                "download app",
                "special offer",
                "limited time",
            ]

            # Check high-confidence patterns first
            for pattern in high_confidence_patterns:
                if pattern in paragraph_lower:
                    is_ad = True
                    break

            # For other patterns, require multiple indicators
            if not is_ad:
                ad_indicators = 0
                matched_patterns = []
                for pattern in ad_patterns:
                    if pattern in paragraph_lower:
                        ad_indicators += 1
                        matched_patterns.append(pattern)
                        if ad_indicators >= 2:  # Require at least 2 indicators
                            is_ad = True
                            break

            # Additional checks for specific ad patterns
            if not is_ad:
                # Check for HTML entities that often appear in ads
                if "&lt;" in paragraph and "&gt;" in paragraph:
                    is_ad = True

                # Check for very short paragraphs that are likely navigation
                if len(paragraph.strip()) < 10:
                    is_ad = True

                # Check for paragraphs that are mostly punctuation/symbols
                text_chars = sum(1 for c in paragraph if c.isalnum())
                total_chars = len(paragraph.strip())
                if total_chars > 0 and text_chars / total_chars < 0.5:
                    is_ad = True

            # Only keep non-advertisement paragraphs
            if not is_ad:
                cleaned_paragraphs.append(paragraph)

        return "\n\n".join(cleaned_paragraphs)

    def _is_chapter_heading(self, title: str, expected_chapter_number: int) -> bool:
        """
        Determine if an H2 heading is a real chapter heading or just a content heading.

        Args:
            title: The heading text
            expected_chapter_number: The expected chapter number

        Returns:
            True if this is a real chapter heading
        """
        import re

        if not title:
            return False

        title_lower = title.lower().strip()

        # Check for explicit chapter patterns that start with "Chapter"
        chapter_start_patterns = [
            r"^chapter\s+\d+",  # "Chapter 1981"
            r"^ch\.?\s*\d+",  # "Ch. 1981" or "Ch 1981"
            r"^episode\s+\d+",  # "Episode 1981"
            r"^part\s+\d+",  # "Part 1981"
            r"^\d+\.\s+",  # "1981. Title"
            r"^volume\s+\d+",  # "Volume 1981"
            r"^book\s+\d+",  # "Book 1981"
        ]

        for pattern in chapter_start_patterns:
            if re.search(pattern, title_lower):
                return True

        # Check if it's just a number followed by text (like "2570 Requirements")
        # This is likely a content heading, not a chapter heading
        if re.match(r"^\d+\s+\w+", title):
            return False

        # Check for content headings that contain "chapter" but are not real chapters
        # These are usually in the format "Novel Name Chapter X" or similar
        content_heading_patterns = [
            r"^.+\s+chapter\s+\d+$",  # "Dimensional Descent Chapter 1981"
            r"^.+\s+ch\.?\s*\d+$",  # "Novel Name Ch. 1981"
        ]

        for pattern in content_heading_patterns:
            if re.search(pattern, title_lower):
                return False  # This is a content heading, not a chapter boundary

        # If it contains "chapter" but doesn't match content patterns, it might be a chapter
        if "chapter" in title_lower:
            return True

        # If it's the first heading and doesn't match patterns, it might be a chapter
        if expected_chapter_number == 1:
            return True

        # Default to False for ambiguous cases
        return False

    def _group_chapters_by_number(self, h2_matches: list) -> list:
        """
        Group H2 headings by chapter number to handle merging.

        Args:
            h2_matches: List of H2 regex matches

        Returns:
            List of chapter groups, each containing headings for the same chapter
        """
        chapter_groups = []
        current_group = []
        current_chapter_number = None

        for i, match in enumerate(h2_matches):
            title = match.group(1).strip()

            # Check if this is a chapter heading
            if not self._is_chapter_heading(title, i + 1):
                continue

            # Extract chapter number
            chapter_number = self._extract_chapter_number_from_title(title)

            if chapter_number is None:
                # If no chapter number, treat as separate chapter
                if current_group:
                    chapter_groups.append(current_group)
                    current_group = []
                current_group.append((title, match, i))
                chapter_groups.append(current_group)
                current_group = []
                current_chapter_number = None
            elif chapter_number == current_chapter_number:
                # Same chapter number, add to current group
                current_group.append((title, match, i))
            else:
                # Different chapter number, start new group
                if current_group:
                    chapter_groups.append(current_group)
                current_group = [(title, match, i)]
                current_chapter_number = chapter_number

        # Add the last group
        if current_group:
            chapter_groups.append(current_group)

        return chapter_groups

    def _select_best_title_from_group(
        self, chapter_group: list, chapters_content: str
    ) -> tuple:
        """
        Select the best title from a group of chapter headings.

        Args:
            chapter_group: List of (title, match, index) tuples for the same chapter
            chapters_content: Full chapters content

        Returns:
            Tuple of (best_title, content_start, content_end)
        """
        if not chapter_group:
            return None, None, None

        if len(chapter_group) == 1:
            # Only one title, use it
            title, match, index = chapter_group[0]
            content_start = match.end()
            return title, content_start, None

        # Multiple titles for the same chapter, find the best one
        best_title = chapter_group[0][0]  # Start with first title

        # Check if descriptive title preference is enabled
        # Support multiple config structures
        content_cleaning_config = self.config.get("content_cleaning", {})
        content_processing_config = self.config.get("content_processing", {})
        text_processing_config = content_cleaning_config.get("text_processing", {})
        # Check for prefer_descriptive_titles setting (don't use 'or' with defaults)
        prefer_descriptive = True  # Default value
        if "prefer_descriptive_titles" in text_processing_config:
            prefer_descriptive = text_processing_config["prefer_descriptive_titles"]
        elif "prefer_descriptive_titles" in content_cleaning_config:
            prefer_descriptive = content_cleaning_config["prefer_descriptive_titles"]
        elif "prefer_descriptive_titles" in content_processing_config:
            prefer_descriptive = content_processing_config["prefer_descriptive_titles"]

        if prefer_descriptive:
            for title, match, index in chapter_group[1:]:
                if self._is_better_title(best_title, title):
                    best_title = title
        # If not preferring descriptive titles, just use the first title

        # Find content boundaries
        first_match = chapter_group[0][1]
        content_start = first_match.end()

        # Content ends at the start of the next chapter group (if any)
        content_end = None
        # This will be handled by the calling code

        return best_title, content_start, content_end

    def _remove_redundant_titles_from_group(
        self, content: str, chapter_group: list, best_title: str
    ) -> str:
        """
        Remove redundant titles from content based on the chapter group.

        Args:
            content: Chapter content
            chapter_group: List of (title, match, index) tuples for the same chapter
            best_title: The selected best title

        Returns:
            Cleaned content with redundant titles removed
        """
        titles_to_remove = []

        for title, match, index in chapter_group:
            if title != best_title and self._is_redundant_title(best_title, title):
                titles_to_remove.append(title)

        return self._remove_redundant_titles_from_content(content, titles_to_remove)

    def _remove_all_redundant_headings(self, content: str, main_title: str) -> str:
        """
        Remove all redundant H2 headings from content that are related to the main title.

        Args:
            content: Chapter content
            main_title: The main chapter title

        Returns:
            Cleaned content with redundant headings removed
        """
        import re

        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Check if this line is an H2 heading
            h2_match = re.match(r"^## (.+)$", line_stripped)
            if h2_match:
                heading_text = h2_match.group(1).strip()

                # Check if this heading is redundant with the main title
                if self._is_redundant_title(main_title, heading_text):
                    continue  # Skip this redundant heading

                # Check for content-style headings that should be removed
                if self._is_content_style_heading(heading_text, main_title):
                    continue  # Skip this content-style heading

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _is_content_style_heading(self, heading: str, main_title: str) -> bool:
        """
        Check if a heading is a content-style heading that should be removed.

        Args:
            heading: The heading text to check
            main_title: The main chapter title

        Returns:
            True if this is a content-style heading that should be removed
        """
        import re

        # Extract chapter number from main title
        main_chapter_number = self._extract_chapter_number_from_title(main_title)

        if main_chapter_number is None:
            return False

        # Check for patterns like "2570 Requirements" (number + text)
        if re.match(rf"^{main_chapter_number}\s+\w+", heading):
            return True

        # Check for patterns like "Dimensional Descent Chapter 1981"
        if re.search(rf"chapter\s+{main_chapter_number}$", heading.lower()):
            return True

        return False

    def _merge_chapter_titles(
        self, main_title: str, content: str, h2_matches: list, current_index: int
    ) -> tuple[str, str]:
        """
        Merge chapter titles intelligently by choosing the most complete title
        and removing redundant titles from content.

        Args:
            main_title: The main chapter title from the heading
            content: The chapter content
            h2_matches: List of all H2 matches found
            current_index: Index of the current chapter in h2_matches

        Returns:
            Tuple of (best_title, cleaned_content)
        """
        import re

        # Find all H2 headings within this chapter's content
        content_h2_matches = []
        for j in range(current_index + 1, len(h2_matches)):
            match = h2_matches[j]
            heading_text = match.group(1).strip()

            # Stop if we hit another real chapter heading
            if self._is_chapter_heading(heading_text, j + 1):
                break

            # This is a content heading within our chapter
            content_h2_matches.append((heading_text, match))

        # Find the best title among main title and content titles
        best_title = main_title
        titles_to_remove = []

        for content_title, match in content_h2_matches:
            # Check if this content title is a better version of the main title
            if self._is_better_title(main_title, content_title):
                best_title = content_title
                titles_to_remove.append(content_title)
            elif self._is_redundant_title(main_title, content_title):
                # This is a redundant title that should be removed
                titles_to_remove.append(content_title)

        # Remove redundant titles from content
        cleaned_content = self._remove_redundant_titles_from_content(
            content, titles_to_remove
        )

        return best_title, cleaned_content

    def _is_better_title(self, main_title: str, content_title: str) -> bool:
        """
        Determine if a content title is better than the main title.

        Args:
            main_title: The main chapter title
            content_title: A title found in the content

        Returns:
            True if content_title is better than main_title
        """
        # Extract chapter numbers for comparison
        main_number = self._extract_chapter_number_from_title(main_title)
        content_number = self._extract_chapter_number_from_title(content_title)

        # Must have the same chapter number to be considered
        if main_number != content_number:
            return False

        # Don't consider content titles that are in "Novel Name Chapter X" format as better
        # These are usually content headings, not better chapter titles
        if self._is_content_heading_format(content_title):
            return False

        # Prefer longer, more descriptive titles that start with "Chapter"
        if content_title.lower().startswith("chapter") and len(content_title) > len(
            main_title
        ):
            # Check if content title has more descriptive text after the chapter number
            main_desc = self._extract_title_description(main_title)
            content_desc = self._extract_title_description(content_title)

            if len(content_desc) > len(main_desc):
                return True

        return False

    def _is_content_heading_format(self, title: str) -> bool:
        """
        Check if a title is in the format of a content heading (e.g., "Novel Name Chapter X").

        Args:
            title: Title to check

        Returns:
            True if this looks like a content heading format
        """
        import re

        title_lower = title.lower().strip()

        # Check for "Novel Name Chapter X" pattern
        if re.search(r"^.+\s+chapter\s+\d+$", title_lower):
            return True

        return False

    def _is_redundant_title(self, main_title: str, content_title: str) -> bool:
        """
        Determine if a content title is redundant with the main title.

        Args:
            main_title: The main chapter title
            content_title: A title found in the content

        Returns:
            True if content_title is redundant and should be removed
        """
        # Extract chapter numbers
        main_number = self._extract_chapter_number_from_title(main_title)
        content_number = self._extract_chapter_number_from_title(content_title)

        # If they have the same chapter number, the content title is likely redundant
        if main_number and content_number and main_number == content_number:
            return True

        # Check for similar titles (case-insensitive)
        main_lower = main_title.lower().strip()
        content_lower = content_title.lower().strip()

        # If one title is contained in the other, it's likely redundant
        if main_lower in content_lower or content_lower in main_lower:
            return True

        return False

    def _extract_title_description(self, title: str) -> str:
        """
        Extract the descriptive part of a title (after chapter number).

        Args:
            title: Chapter title

        Returns:
            Descriptive part of the title
        """
        import re

        # Remove chapter number patterns to get the description
        patterns = [
            r"^chapter\s+\d+\s*:?\s*",
            r"^ch\.?\s*\d+\s*:?\s*",
            r"^\d+\s*[.:]?\s*",
        ]

        description = title
        for pattern in patterns:
            description = re.sub(pattern, "", description, flags=re.IGNORECASE).strip()

        return description

    def _extract_chapter_number_from_title(self, title: str) -> Optional[int]:
        """
        Extract chapter number from a title.

        Args:
            title: Chapter title

        Returns:
            Chapter number if found, None otherwise
        """
        import re

        if not title:
            return None

        # Patterns to extract chapter numbers
        patterns = [
            r"^chapter\s+(\d+)",  # "Chapter 1981"
            r"^ch\.?\s*(\d+)",  # "Ch. 1981" or "Ch 1981"
            r"^episode\s+(\d+)",  # "Episode 1981"
            r"^part\s+(\d+)",  # "Part 1981"
            r"^(\d+)\.",  # "1981."
            r"^volume\s+(\d+)",  # "Volume 1981"
            r"^book\s+(\d+)",  # "Book 1981"
            r"chapter\s+(\d+)",  # "Something Chapter 1981"
        ]

        title_lower = title.lower().strip()

        for pattern in patterns:
            match = re.search(pattern, title_lower)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue

        return None

    def _remove_redundant_titles_from_content(
        self, content: str, titles_to_remove: list
    ) -> str:
        """
        Remove redundant titles from chapter content.

        Args:
            content: Chapter content
            titles_to_remove: List of titles to remove

        Returns:
            Cleaned content with redundant titles removed
        """
        if not titles_to_remove:
            return content

        import re

        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line_stripped = line.strip()

            # Check if this line contains a redundant title
            should_remove = False
            for title in titles_to_remove:
                # Check for exact match or H2 heading format
                if (
                    line_stripped == title
                    or line_stripped == f"## {title}"
                    or line_stripped.startswith(f"## {title}")
                ):
                    should_remove = True
                    break

            if not should_remove:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _is_unicode_advertisement(self, text: str) -> bool:
        """
        Detect Unicode-based advertisements that use special characters to bypass detection.

        Examples:
        - 𝚋𝚎ｄ𝚗ｏｖ𝚎𝚕．ｃｏ𝚖 (mathematical alphanumeric symbols + fullwidth)
        - ｂｅｄｎｏｖｅｌ．ｃｏｍ (fullwidth characters)
        - 𝒃𝒆𝒅𝒏𝒐𝒗𝒆𝒍.𝒄𝒐𝒎 (mathematical script)

        Args:
            text: Text to check for Unicode-based ads

        Returns:
            True if text appears to be a Unicode-based advertisement
        """
        import re
        import unicodedata

        if not text or len(text.strip()) > 200:  # Ads are usually short
            return False

        text = text.strip()

        # Check for high concentration of special Unicode characters
        special_unicode_count = 0
        total_chars = len(text)

        # Count characters from suspicious Unicode blocks
        for char in text:
            category = unicodedata.category(char)
            name = unicodedata.name(char, "")

            # Mathematical Alphanumeric Symbols (U+1D400–U+1D7FF)
            if "\U0001d400" <= char <= "\U0001d7ff":
                special_unicode_count += 1
            # Fullwidth forms (U+FF00–U+FFEF)
            elif "\uff00" <= char <= "\uffef":
                special_unicode_count += 1
            # Mathematical operators and symbols
            elif category.startswith("Sm") or category.startswith("So"):
                special_unicode_count += 1
            # Other suspicious patterns
            elif any(
                keyword in name.lower()
                for keyword in [
                    "mathematical",
                    "fullwidth",
                    "circled",
                    "squared",
                    "negative",
                ]
            ):
                special_unicode_count += 1

        # If more than 30% of characters are special Unicode, likely an ad
        if total_chars > 0 and (special_unicode_count / total_chars) > 0.3:
            return True

        # Convert Unicode to ASCII equivalent for pattern matching
        ascii_equivalent = self._unicode_to_ascii(text)

        # Check if ASCII equivalent matches known website patterns
        website_patterns = [
            r"bed?novel\.com?",
            r"novel.*\.com?",
            r"read.*\.com?",
            r"chapter.*\.com?",
            r"manga.*\.com?",
            r"light.*novel.*\.com?",
            r"web.*novel.*\.com?",
            r"[a-z]+novel[a-z]*\.com?",
            r"[a-z]*\.com?/novel",
        ]

        for pattern in website_patterns:
            if re.search(pattern, ascii_equivalent, re.IGNORECASE):
                return True

        # Check for common ad phrases in ASCII equivalent
        # Only check for phrases that are likely to be ads when combined with website patterns
        ad_phrases_with_sites = [
            "read at",
            r"visit.*\.com",
            r"go to.*\.com",
            r"check out.*\.com",
            r"latest chapter.*\.com",
            r"free reading.*\.com",
            "official site",
            "original source",
        ]

        ascii_lower = ascii_equivalent.lower()
        for phrase in ad_phrases_with_sites:
            if re.search(phrase, ascii_lower):
                return True

        # Additional check: if text contains "visit" and a website pattern, it's likely an ad
        if "visit" in ascii_lower and re.search(r"\w+\.\w+", ascii_lower):
            return True

        return False

    def _unicode_to_ascii(self, text: str) -> str:
        """
        Convert Unicode characters to their ASCII equivalents for pattern matching.

        Args:
            text: Text with potential Unicode characters

        Returns:
            ASCII equivalent text
        """
        import unicodedata

        result = []

        for char in text:
            # Try to get the ASCII equivalent
            try:
                # First try Unicode normalization
                normalized = unicodedata.normalize("NFKD", char)
                ascii_char = normalized.encode("ascii", "ignore").decode("ascii")

                if ascii_char:
                    result.append(ascii_char)
                else:
                    # Manual mapping for common Unicode ad characters
                    char_mappings = {
                        # Mathematical Alphanumeric Symbols (bold)
                        "𝐚": "a",
                        "𝐛": "b",
                        "𝐜": "c",
                        "𝐝": "d",
                        "𝐞": "e",
                        "𝐟": "f",
                        "𝐠": "g",
                        "𝐡": "h",
                        "𝐢": "i",
                        "𝐣": "j",
                        "𝐤": "k",
                        "𝐥": "l",
                        "𝐦": "m",
                        "𝐧": "n",
                        "𝐨": "o",
                        "𝐩": "p",
                        "𝐪": "q",
                        "𝐫": "r",
                        "𝐬": "s",
                        "𝐭": "t",
                        "𝐮": "u",
                        "𝐯": "v",
                        "𝐰": "w",
                        "𝐱": "x",
                        "𝐲": "y",
                        "𝐳": "z",
                        # Mathematical Alphanumeric Symbols (monospace)
                        "𝚊": "a",
                        "𝚋": "b",
                        "𝚌": "c",
                        "𝚍": "d",
                        "𝚎": "e",
                        "𝚏": "f",
                        "𝚐": "g",
                        "𝚑": "h",
                        "𝚒": "i",
                        "𝚓": "j",
                        "𝚔": "k",
                        "𝚕": "l",
                        "𝚖": "m",
                        "𝚗": "n",
                        "𝚘": "o",
                        "𝚙": "p",
                        "𝚚": "q",
                        "𝚛": "r",
                        "𝚜": "s",
                        "𝚝": "t",
                        "𝚞": "u",
                        "𝚟": "v",
                        "𝚠": "w",
                        "𝚡": "x",
                        "𝚢": "y",
                        "𝚣": "z",
                        # Fullwidth characters
                        "ａ": "a",
                        "ｂ": "b",
                        "ｃ": "c",
                        "ｄ": "d",
                        "ｅ": "e",
                        "ｆ": "f",
                        "ｇ": "g",
                        "ｈ": "h",
                        "ｉ": "i",
                        "ｊ": "j",
                        "ｋ": "k",
                        "ｌ": "l",
                        "ｍ": "m",
                        "ｎ": "n",
                        "ｏ": "o",
                        "ｐ": "p",
                        "ｑ": "q",
                        "ｒ": "r",
                        "ｓ": "s",
                        "ｔ": "t",
                        "ｕ": "u",
                        "ｖ": "v",
                        "ｗ": "w",
                        "ｘ": "x",
                        "ｙ": "y",
                        "ｚ": "z",
                        "．": ".",
                        "，": ",",
                        "：": ":",
                        "；": ";",
                        "？": "?",
                        "！": "!",
                        "（": "(",
                        "）": ")",
                        "［": "[",
                        "］": "]",
                        "｛": "{",
                        "｝": "}",
                        # Mathematical script
                        "𝒂": "a",
                        "𝒃": "b",
                        "𝒄": "c",
                        "𝒅": "d",
                        "𝒆": "e",
                        "𝒇": "f",
                        "𝒈": "g",
                        "𝒉": "h",
                        "𝒊": "i",
                        "𝒋": "j",
                        "𝒌": "k",
                        "𝒍": "l",
                        "𝒎": "m",
                        "𝒏": "n",
                        "𝒐": "o",
                        "𝒑": "p",
                        "𝒒": "q",
                        "𝒓": "r",
                        "𝒔": "s",
                        "𝒕": "t",
                        "𝒖": "u",
                        "𝒗": "v",
                        "𝒘": "w",
                        "𝒙": "x",
                        "𝒚": "y",
                        "𝒛": "z",
                    }

                    if char in char_mappings:
                        result.append(char_mappings[char])
                    else:
                        # Keep the original character if no mapping found
                        result.append(char)

            except Exception:
                # If all else fails, keep the original character
                result.append(char)

        return "".join(result)

    def _remove_pandoc_markup(self, content: str) -> str:
        """
        Remove Pandoc-specific markup that shouldn't appear in EbookLib EPUB.

        Args:
            content: Content with potential Pandoc markup

        Returns:
            Cleaned content without Pandoc markup
        """
        # Remove Pandoc div blocks: ::: {.class} and :::
        content = re.sub(r":::\s*\{[^}]*\}\s*\n?", "", content)
        content = re.sub(r":::\s*\n?", "", content)

        # Remove \newpage commands (both single and double backslash variants)
        content = re.sub(r"\\\\?newpage\s*\n?", "", content)

        # Remove Pandoc-style page breaks
        content = re.sub(r"\\\\?pagebreak\s*\n?", "", content)

        # Remove Pandoc-style line breaks
        content = re.sub(r"\\\\\\\\\s*\n?", "\n", content)

        # Remove Pandoc metadata blocks that might have leaked through
        content = re.sub(
            r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.MULTILINE | re.DOTALL
        )

        # Remove empty lines that might have been left behind
        content = re.sub(r"\n\s*\n\s*\n", "\n\n", content)

        return content
