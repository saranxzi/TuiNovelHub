"""
Markdown generation module for EPUB creation.

This module generates EPUB-optimized markdown with proper metadata and formatting.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..utils import (
    clean_filename,
    create_safe_directory,
    sanitize_markdown_content,
    validate_markdown_content,
)
from .models import ChapterData, NovelMetadata

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """
    Generates EPUB-optimized markdown from novel data.

    Creates markdown files with YAML front matter suitable for Pandoc EPUB generation.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize markdown generator with configuration.

        Args:
            config: Markdown generation configuration
        """
        self.config = config
        self.epub_config = config.get("epub", {})
        self.chapter_level = self.epub_config.get("chapter_level", 2)
        self.include_toc = self.epub_config.get("include_toc", True)
        self.add_page_breaks = config.get("output", {}).get("add_page_breaks", True)

        # Chapter title formatting options
        self.chapter_title_format = self.epub_config.get(
            "chapter_title_format", "title_only"
        )
        self.chapter_number_format = self.epub_config.get(
            "chapter_number_format", "arabic"
        )

        logger.debug(
            f"MarkdownGenerator initialized with chapter_level: {self.chapter_level}, "
            f"title_format: {self.chapter_title_format}"
        )

    def generate_markdown(
        self,
        metadata: NovelMetadata,
        chapters: List[ChapterData],
        output_dir: Path,
        cover_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate complete markdown file for the novel.

        Args:
            metadata: Novel metadata
            chapters: List of chapter data
            output_dir: Directory to save markdown file
            cover_path: Optional path to cover image

        Returns:
            Path to generated markdown file or None if failed
        """
        try:
            # Create output directory
            if not create_safe_directory(output_dir):
                logger.error(f"Failed to create output directory: {output_dir}")
                return None

            # Generate filename
            filename = self._generate_filename(metadata.title)
            output_path = output_dir / filename

            # Generate markdown content
            content = self._build_markdown_content(metadata, chapters, cover_path)

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Generated markdown file: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error generating markdown: {e}")
            return None

    def save_individual_chapter(
        self,
        chapter: ChapterData,
        output_dir: Path,
        sequence_number: int,
    ) -> Optional[str]:
        """
        Save a single chapter as an individual markdown file.

        Args:
            chapter: Chapter data to save
            output_dir: Directory to save chapter file
            sequence_number: Sequential chapter number

        Returns:
            Path to saved chapter file or None if failed
        """
        try:
            # Create chapters subdirectory
            chapters_dir = output_dir / "chapters"
            if not create_safe_directory(chapters_dir):
                logger.error(f"Failed to create chapters directory: {chapters_dir}")
                return None

            # Generate chapter filename
            chapter_filename = f"chapter_{sequence_number:03d}.md"
            chapter_path = chapters_dir / chapter_filename

            # Generate chapter markdown
            chapter_markdown = self._generate_chapter_markdown(chapter, sequence_number)

            # Write chapter file
            with open(chapter_path, "w", encoding="utf-8") as f:
                f.write(chapter_markdown)

            logger.debug(f"Saved chapter file: {chapter_path}")
            return str(chapter_path)

        except Exception as e:
            logger.error(f"Error saving individual chapter: {e}")
            return None

    def compile_from_individual_chapters(
        self,
        metadata: NovelMetadata,
        output_dir: Path,
        cover_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Compile a complete markdown file from individual chapter files.

        Args:
            metadata: Novel metadata
            output_dir: Directory containing chapter files
            cover_path: Optional path to cover image

        Returns:
            Path to compiled markdown file or None if failed
        """
        try:
            chapters_dir = output_dir / "chapters"
            if not chapters_dir.exists():
                logger.error(f"Chapters directory not found: {chapters_dir}")
                return None

            # Find all chapter files
            chapter_files = sorted(chapters_dir.glob("chapter_*.md"))
            if not chapter_files:
                logger.error(f"No chapter files found in: {chapters_dir}")
                return None

            # Generate main filename
            filename = self._generate_filename(metadata.title)
            output_path = output_dir / filename

            # Build content parts
            content_parts = []

            # Add YAML front matter
            content_parts.append(self._generate_yaml_frontmatter(metadata, cover_path))

            # Add title page
            content_parts.append(self._generate_title_page(metadata))

            # Add table of contents placeholder (will be updated with actual chapters)
            if self.include_toc:
                content_parts.append("# Table of Contents\n")

            # Read and append all chapter files
            for chapter_file in chapter_files:
                try:
                    with open(chapter_file, "r", encoding="utf-8") as f:
                        chapter_content = f.read().strip()
                        content_parts.append(chapter_content)
                except Exception as e:
                    logger.warning(f"Failed to read chapter file {chapter_file}: {e}")
                    continue

            # Combine all content
            complete_content = "\n\n".join(content_parts)

            # Write compiled file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(complete_content)

            logger.info(
                f"Compiled markdown from {len(chapter_files)} chapter files: {output_path}"
            )
            return str(output_path)

        except Exception as e:
            logger.error(f"Error compiling from individual chapters: {e}")
            return None

    def get_existing_chapter_files(self, output_dir: Path) -> List[int]:
        """
        Get list of existing chapter sequence numbers.

        Args:
            output_dir: Directory to check for chapter files

        Returns:
            List of sequence numbers for existing chapter files
        """
        try:
            chapters_dir = output_dir / "chapters"
            if not chapters_dir.exists():
                return []

            existing_chapters = []
            for chapter_file in chapters_dir.glob("chapter_*.md"):
                try:
                    # Extract sequence number from filename
                    filename = chapter_file.stem  # Remove .md extension
                    sequence_str = filename.split("_")[1]  # Get number part
                    sequence_num = int(sequence_str)
                    existing_chapters.append(sequence_num)
                except (IndexError, ValueError):
                    logger.warning(f"Invalid chapter filename format: {chapter_file}")
                    continue

            return sorted(existing_chapters)

        except Exception as e:
            logger.error(f"Error checking existing chapter files: {e}")
            return []

    def chapter_file_exists(self, output_dir: Path, sequence_number: int) -> bool:
        """
        Check if a specific chapter file already exists.

        Args:
            output_dir: Directory to check
            sequence_number: Chapter sequence number

        Returns:
            True if chapter file exists
        """
        chapters_dir = output_dir / "chapters"
        chapter_filename = f"chapter_{sequence_number:03d}.md"
        chapter_path = chapters_dir / chapter_filename
        return chapter_path.exists()

    def _build_markdown_content(
        self,
        metadata: NovelMetadata,
        chapters: List[ChapterData],
        cover_path: Optional[str] = None,
    ) -> str:
        """
        Build complete markdown content.

        Args:
            metadata: Novel metadata
            chapters: List of chapter data
            cover_path: Optional path to cover image

        Returns:
            Complete markdown content
        """
        content_parts = []

        # Add YAML front matter
        content_parts.append(self._generate_yaml_frontmatter(metadata, cover_path))

        # Add title page
        content_parts.append(self._generate_title_page(metadata))

        # Add table of contents if enabled
        if self.include_toc:
            content_parts.append(self._generate_toc(chapters))

        # Add chapters
        for i, chapter in enumerate(chapters):
            content_parts.append(self._generate_chapter_markdown(chapter, i + 1))

        return "\n\n".join(content_parts)

    def _generate_yaml_frontmatter(
        self, metadata: NovelMetadata, cover_path: Optional[str] = None
    ) -> str:
        """
        Generate YAML front matter for Pandoc.

        Args:
            metadata: Novel metadata
            cover_path: Optional path to cover image

        Returns:
            YAML front matter string
        """
        # Build metadata dictionary
        yaml_data = {
            "title": metadata.title,
            "author": metadata.author,
            "description": metadata.description,
            "language": "en",
            "rights": f"© {metadata.author}",
            "publisher": metadata.provider or "Web Novel Scraper",
        }

        # Add optional metadata
        if metadata.genres:
            yaml_data["subject"] = ", ".join(metadata.genres)

        if metadata.publication_date:
            yaml_data["date"] = metadata.publication_date.strftime("%Y-%m-%d")
        else:
            yaml_data["date"] = datetime.now().strftime("%Y-%m-%d")

        # Add cover image if available (use absolute path)
        if cover_path:
            # Convert to absolute path for better compatibility
            cover_abs_path = Path(cover_path).resolve()
            yaml_data["cover-image"] = str(cover_abs_path)

        # Add EPUB-specific settings
        yaml_data.update(
            {
                "epub-chapter-level": self.chapter_level,
                "toc-depth": 2,
                "epub-css": "novel.css",
            }
        )

        # Convert to YAML string
        yaml_str = yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True)

        return f"---\n{yaml_str}---"

    def _generate_title_page(self, metadata: NovelMetadata) -> str:
        """
        Generate title page content with markdown-safe formatting.

        Args:
            metadata: Novel metadata

        Returns:
            Title page markdown with safe content
        """
        parts = []

        # Main title (sanitize for markdown safety, preserve title characters)
        # Disable sanitize for title but if not found return Untitled
        if metadata.title:
            parts.append(f"# {metadata.title}")
        else:
            parts.append("# Untitled")

        # safe_title = (
        #     sanitize_markdown_content(metadata.title, preserve_title_chars=True)
        #     if metadata.title
        #     else "Untitled"
        # )
        # parts.append(f"# {safe_title}")

        parts.append("")

        # Author (sanitize for markdown safety, preserve title characters)
        safe_author = (
            sanitize_markdown_content(metadata.author, preserve_title_chars=True)
            if metadata.author
            else "Unknown Author"
        )
        parts.append(f"**Author:** {safe_author}")
        parts.append("")

        # Status
        if metadata.status:
            status_text = metadata.status.value.title()
            parts.append(f"**Status:** {status_text}")
            parts.append("")

        # Genres (sanitize for markdown safety)
        if metadata.genres:
            safe_genres = [
                sanitize_markdown_content(genre) for genre in metadata.genres
            ]
            genres_text = ", ".join(safe_genres)
            parts.append(f"**Genres:** {genres_text}")
            parts.append("")

        # Rating
        if metadata.rating:
            rating_text = f"{metadata.rating}/10"
            if metadata.rating_count:
                rating_text += f" ({metadata.rating_count:,} ratings)"
            parts.append(f"**Rating:** {rating_text}")
            parts.append("")

        # Description
        if metadata.description:
            parts.append("## Description")
            parts.append("")
            formatted_description = self._format_description(metadata.description)
            parts.append(formatted_description)
            parts.append("")

        # Tags (sanitize for markdown safety)
        if metadata.tags:
            parts.append("## Tags")
            parts.append("")
            safe_tags = [sanitize_markdown_content(tag) for tag in metadata.tags]
            tags_text = ", ".join(safe_tags)
            parts.append(tags_text)
            parts.append("")

        # Alternative names (sanitize for markdown safety)
        if metadata.alternative_names:
            parts.append("## Alternative Names")
            parts.append("")
            safe_alt_names = [
                sanitize_markdown_content(name) for name in metadata.alternative_names
            ]
            alt_names_text = ", ".join(safe_alt_names)
            parts.append(alt_names_text)
            parts.append("")

        # Source
        parts.append(f"**Source:** [{metadata.provider}]({metadata.source_url})")
        parts.append("")

        # Page break
        if self.add_page_breaks:
            parts.append("\\newpage")

        return "\n".join(parts)

    def _generate_toc(self, chapters: List[ChapterData]) -> str:
        """
        Generate table of contents.

        Args:
            chapters: List of chapter data

        Returns:
            Table of contents markdown
        """
        parts = []

        parts.append("# Table of Contents")
        parts.append("")

        for i, chapter in enumerate(chapters):
            chapter_num = chapter.chapter_number or (i + 1)
            # Create anchor link using cleaned title and chapter number for uniqueness
            cleaned_title = self._clean_chapter_title(chapter.title, chapter_num)
            anchor = self._create_unique_anchor(cleaned_title, chapter_num)

            # For TOC, use appropriate format based on cleaned title
            if cleaned_title.lower().startswith("chapter"):
                # Title already has "Chapter" prefix, use as-is
                toc_title = cleaned_title
            elif cleaned_title.isdigit():
                # Title is just a number, format as "Chapter X"
                toc_title = f"Chapter {cleaned_title}"
            else:
                # Title has content, format as "Chapter X - Title"
                toc_title = f"Chapter {chapter_num} - {cleaned_title}"
            parts.append(f"{i + 1}. [{toc_title}](#{anchor})")

        parts.append("")

        # Page break
        if self.add_page_breaks:
            parts.append("\\newpage")

        return "\n".join(parts)

    def _generate_chapter_markdown(
        self, chapter: ChapterData, sequence_number: int
    ) -> str:
        """
        Generate markdown for a single chapter.

        Args:
            chapter: Chapter data
            sequence_number: Sequential chapter number

        Returns:
            Chapter markdown
        """
        parts = []

        # Add chapter div using Pandoc fenced div syntax for CSS styling
        parts.append("::: {.chapter}")
        parts.append("")

        # Chapter heading
        chapter_num = chapter.chapter_number or sequence_number
        heading_level = "#" * self.chapter_level

        # Format chapter title based on configuration
        chapter_title = self._format_chapter_title(chapter.title, chapter_num)

        # Create heading with anchor using cleaned title and chapter number for uniqueness
        cleaned_title = self._clean_chapter_title(chapter.title, chapter_num)
        anchor = self._create_unique_anchor(cleaned_title, chapter_num)
        parts.append(f"{heading_level} {chapter_title} {{#{anchor}}}")
        parts.append("")

        # Chapter content
        content = self._format_chapter_content(chapter.content)
        parts.append(content)
        parts.append("")

        # Close chapter div
        parts.append(":::")
        parts.append("")

        # Page break (except for last chapter)
        if self.add_page_breaks:
            parts.append("\\newpage")

        return "\n".join(parts)

    def _format_chapter_title(self, title: str, chapter_num: int) -> str:
        """
        Format chapter title based on configuration with markdown safety.

        Args:
            title: Chapter title
            chapter_num: Chapter number

        Returns:
            Formatted chapter title safe for markdown
        """
        if self.chapter_title_format == "title_only":
            clean_title = self._clean_chapter_title(title, chapter_num)
            return clean_title
        elif self.chapter_title_format == "number_title":
            clean_title = self._clean_chapter_title(title, chapter_num)
            return f"{chapter_num}. {clean_title}"
        elif self.chapter_title_format == "chapter_number_title":
            clean_title = self._clean_chapter_title(title, chapter_num)
            return f"Chapter {chapter_num}: {clean_title}"
        elif self.chapter_title_format == "number_only":
            return str(chapter_num)
        else:
            # Default to title only
            clean_title = self._clean_chapter_title(title, chapter_num)
            return clean_title

    def _clean_chapter_title(self, title: str, chapter_num: int) -> str:
        """
        Clean chapter title by removing redundant numbering and extracting the actual title.

        Handles cases like:
        - "Chapter 2 - 1 - A Portrait Of My Future" -> "A Portrait Of My Future"
        - "Chapter 1: Prolog - Hero's System" -> "Prolog - Hero's System"
        - "Chapter 5 - 4 - At Least I've Given Him a Chance" -> "At Least I've Given Him a Chance"
        - "Chapter 10 - 9 -Does She Have Yandere Traits?" -> "Does She Have Yandere Traits?"

        Args:
            title: Original chapter title
            chapter_num: Chapter sequence number

        Returns:
            Cleaned title or chapter number if no meaningful title found
        """
        if not title:
            return str(chapter_num)

        # Remove leading/trailing whitespace
        cleaned = title.strip()

        # Pattern 1: "Chapter X - Y - Title" (NovelBin common pattern)
        import re

        # Match "Chapter X - Y - Title" pattern
        pattern1 = r"^Chapter\s+\d+\s*-\s*\d+\s*-\s*(.+)$"
        match1 = re.match(pattern1, cleaned, re.IGNORECASE)
        if match1:
            extracted_title = match1.group(1).strip()
            if extracted_title and len(extracted_title) > 1:
                return extracted_title

        # Pattern 2: "Chapter X: Title" pattern
        pattern2 = r"^Chapter\s+\d+\s*:\s*(.+)$"
        match2 = re.match(pattern2, cleaned, re.IGNORECASE)
        if match2:
            extracted_title = match2.group(1).strip()
            if extracted_title and len(extracted_title) > 1:
                return extracted_title

        # Pattern 3: "Chapter X - Title" pattern
        pattern3 = r"^Chapter\s+\d+\s*-\s*(.+)$"
        match3 = re.match(pattern3, cleaned, re.IGNORECASE)
        if match3:
            extracted_title = match3.group(1).strip()
            if extracted_title and len(extracted_title) > 1:
                return extracted_title

        # Pattern 4: Just "Chapter X" with no title - return as-is since it's already properly formatted
        pattern4 = r"^Chapter\s+\d+\s*$"
        if re.match(pattern4, cleaned, re.IGNORECASE):
            return cleaned

        # Pattern 5: "X - Title" (number dash title)
        pattern5 = r"^\d+\s*-\s*(.+)$"
        match5 = re.match(pattern5, cleaned)
        if match5:
            extracted_title = match5.group(1).strip()
            if extracted_title and len(extracted_title) > 1:
                return extracted_title

        # If no patterns match but we have a title, return it as-is
        if len(cleaned) > 1:
            return cleaned

        # Fallback to chapter number
        return str(chapter_num)

    def _format_description(self, description: str) -> str:
        """
        Format novel description with proper paragraph breaks and markdown validation.

        Args:
            description: Raw description text

        Returns:
            Formatted description with proper paragraphs and markdown safety
        """
        if not description:
            return ""

        # Validate and sanitize description for markdown safety
        if not validate_markdown_content(description):
            logger.warning(
                "Description contains potentially problematic markdown patterns, sanitizing..."
            )
            description = sanitize_markdown_content(description)

        # Split by common paragraph separators
        # Handle various line break patterns
        paragraphs = []

        # First, normalize line breaks
        normalized = description.replace("\r\n", "\n").replace("\r", "\n")

        # Split by double line breaks (common paragraph separator)
        potential_paragraphs = normalized.split("\n\n")

        for para in potential_paragraphs:
            # Clean up the paragraph
            para = para.strip()
            if not para:
                continue

            # If paragraph contains single line breaks, they might be sentence breaks
            # Replace single line breaks with spaces, but preserve intentional breaks
            lines = para.split("\n")
            if len(lines) > 1:
                # Check if lines look like separate sentences/paragraphs
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line:
                        cleaned_lines.append(line)

                # If we have multiple substantial lines, treat as separate paragraphs
                if len(cleaned_lines) > 1 and all(
                    len(line) > 20 for line in cleaned_lines
                ):
                    paragraphs.extend(cleaned_lines)
                else:
                    # Join with spaces for a single paragraph
                    paragraphs.append(" ".join(cleaned_lines))
            else:
                paragraphs.append(para)

        # Join paragraphs with double line breaks for proper markdown formatting
        return "\n\n".join(paragraphs)

    def _format_chapter_content(self, content: str) -> str:
        """
        Format chapter content for enhanced EPUB markdown with validation.

        Args:
            content: Raw chapter content

        Returns:
            Formatted content with enhanced structure and markdown safety
        """
        # Validate content for markdown safety
        if not validate_markdown_content(content):
            logger.warning(
                "Content contains potentially problematic markdown patterns, sanitizing..."
            )
            content = sanitize_markdown_content(content)

        # Split into paragraphs
        paragraphs = content.split("\n\n")

        formatted_paragraphs = []

        for paragraph in paragraphs:
            # Clean up paragraph
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            # Handle special formatting
            paragraph = self._apply_text_formatting(paragraph)

            # Handle scene breaks
            if self._is_scene_break(paragraph):
                formatted_paragraphs.append("---")
                continue

            # Use pure markdown paragraphs - Pandoc will handle CSS styling
            formatted_paragraphs.append(paragraph)

        return "\n\n".join(formatted_paragraphs)

    def _is_scene_break(self, paragraph: str) -> bool:
        """
        Check if paragraph represents a scene break.

        Args:
            paragraph: Paragraph text to check

        Returns:
            True if paragraph is a scene break
        """
        # Common scene break patterns
        scene_break_patterns = [
            "***",
            "* * *",
            "---",
            "- - -",
            "~~~",
            "~ ~ ~",
            "◊ ◊ ◊",
            "◆ ◆ ◆",
            "▪ ▪ ▪",
            "■ ■ ■",
        ]

        stripped = paragraph.strip()
        return stripped in scene_break_patterns or (
            len(stripped) <= 10
            and all(c in "*-~◊◆▪■ " for c in stripped)
            and len(set(stripped.replace(" ", ""))) <= 2
        )

    def _apply_text_formatting(self, text: str) -> str:
        """
        Apply enhanced text formatting for EPUB.

        Args:
            text: Text to format

        Returns:
            Formatted text with enhanced typography
        """
        # Handle dialogue formatting
        text = self._format_dialogue(text)

        # Handle emphasis and strong text
        text = self._format_emphasis(text)

        # Handle special characters and typography
        text = self._format_typography(text)

        return text

    def _format_dialogue(self, text: str) -> str:
        """
        Format dialogue with proper quotation marks.

        Args:
            text: Text to format

        Returns:
            Text with formatted dialogue
        """
        # Replace straight quotes with curly quotes for better typography
        # This is a simple implementation - could be enhanced
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace("'", "'").replace("'", "'")

        return text

    def _format_emphasis(self, text: str) -> str:
        """
        Format emphasis and strong text.

        Args:
            text: Text to format

        Returns:
            Text with formatted emphasis
        """
        # Keep markdown-style emphasis instead of converting to HTML
        # This prevents HTML tags from interfering with EbookLib processing
        import re

        # Normalize emphasis markers to consistent markdown format
        # Bold text (**text** or __text__) -> **text**
        text = re.sub(r"__(.*?)__", r"**\1**", text)

        # Italic text (*text* or _text_) -> *text*
        text = re.sub(r"_(.*?)_", r"*\1*", text)

        return text

    def _format_typography(self, text: str) -> str:
        """
        Apply typographic enhancements.

        Args:
            text: Text to format

        Returns:
            Text with enhanced typography
        """
        # Em dashes
        text = text.replace("--", "—")

        # Ellipsis
        text = text.replace("...", "…")

        # Non-breaking spaces before certain punctuation
        text = text.replace(" !", " !")
        text = text.replace(" ?", " ?")
        text = text.replace(" :", " :")
        text = text.replace(" ;", " ;")

        return text

    def _create_anchor(self, title: str) -> str:
        """
        Create anchor link from title.

        Args:
            title: Chapter title

        Returns:
            Anchor string
        """
        # Convert to lowercase and replace spaces with hyphens
        anchor = title.lower()
        anchor = "".join(c if c.isalnum() or c.isspace() else "" for c in anchor)
        anchor = anchor.replace(" ", "-")

        # Remove multiple hyphens
        while "--" in anchor:
            anchor = anchor.replace("--", "-")

        return anchor.strip("-")

    def _create_unique_anchor(self, title: str, chapter_num: int) -> str:
        """
        Create unique anchor link from title and chapter number to prevent duplicates.

        This solves the Pandoc duplicate identifier issue by ensuring each chapter
        has a unique anchor even if titles are the same.

        Args:
            title: Chapter title
            chapter_num: Chapter number for uniqueness

        Returns:
            Unique anchor string in format: "chapter-{num}-{title-slug}"
        """
        # Create base anchor from title
        title_anchor = self._create_anchor(title)

        # If title anchor is empty, use a generic name
        # But allow single characters (like "A", "B") to be preserved
        if not title_anchor:
            title_anchor = "untitled"

        # Create unique anchor with chapter number prefix
        # Format: "chapter-{num}-{title-slug}"
        unique_anchor = f"chapter-{chapter_num}-{title_anchor}"

        # Ensure it doesn't exceed reasonable length (Pandoc handles long IDs but keep it clean)
        if len(unique_anchor) > 100:
            # Truncate title part but keep chapter number for uniqueness
            max_title_length = 100 - len(f"chapter-{chapter_num}-")
            title_anchor = title_anchor[:max_title_length].rstrip("-")
            unique_anchor = f"chapter-{chapter_num}-{title_anchor}"

        return unique_anchor

    def _generate_filename(self, title: str) -> str:
        """
        Generate Unix-safe filename for markdown file using underscores.

        Args:
            title: Novel title

        Returns:
            Generated filename with Unix-safe naming
        """
        base_name = clean_filename(title, use_underscores=True)
        return f"{base_name}.md"

    def generate_statistics(self, chapters: List[ChapterData]) -> Dict[str, Any]:
        """
        Generate statistics about the novel.

        Args:
            chapters: List of chapter data

        Returns:
            Statistics dictionary
        """
        total_words = sum(chapter.word_count or 0 for chapter in chapters)
        total_chars = sum(chapter.character_count or 0 for chapter in chapters)

        # Calculate average chapter length
        chapter_word_counts = [
            chapter.word_count for chapter in chapters if chapter.word_count
        ]
        avg_words_per_chapter = (
            sum(chapter_word_counts) / len(chapter_word_counts)
            if chapter_word_counts
            else 0
        )

        # Estimate reading time (average 200 words per minute)
        reading_time_minutes = total_words / 200 if total_words > 0 else 0
        reading_time_hours = reading_time_minutes / 60

        return {
            "total_chapters": len(chapters),
            "total_words": total_words,
            "total_characters": total_chars,
            "average_words_per_chapter": round(avg_words_per_chapter),
            "estimated_reading_time_minutes": round(reading_time_minutes),
            "estimated_reading_time_hours": round(reading_time_hours, 1),
        }
