"""
Chapter processor for EbookLib EPUB generator.

This module handles conversion of markdown chapters to EPUB chapters,
including HTML conversion, styling, and proper chapter structure.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional

import markdown
from ebooklib import epub

from .markdown_parser import ParsedChapter

logger = logging.getLogger(__name__)


class ChapterProcessor:
    """
    Handles chapter processing for EPUB generation using ebooklib.

    Converts markdown chapters to HTML, applies styling, and creates
    proper EPUB chapter structure with navigation support.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize chapter processor with configuration.

        Args:
            config: Chapter processing configuration
        """
        self.config = config
        self.epub_config = config.get("epub", {})
        self.chapter_level = self.epub_config.get("chapter_level", 2)

        # Initialize markdown processor
        self.markdown_processor = markdown.Markdown(
            extensions=[
                "extra",  # Tables, footnotes, etc.
                "codehilite",  # Code highlighting
                "toc",  # Table of contents
            ],
            extension_configs={
                "codehilite": {
                    "css_class": "highlight",
                    "use_pygments": False,  # Use CSS classes only
                },
                "toc": {
                    "anchorlink": True,
                },
            },
        )

        logger.debug(
            f"ChapterProcessor initialized with chapter_level: {self.chapter_level}"
        )

    def create_epub_chapters(
        self,
        chapters: List[ParsedChapter],
        css_item: Optional[epub.EpubItem] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[epub.EpubHtml]:
        """
        Create EPUB chapters from parsed chapter data.

        Args:
            chapters: List of parsed chapters
            css_item: Optional CSS item to link to chapters
            progress_callback: Optional progress callback

        Returns:
            List of EPUB HTML chapters
        """
        epub_chapters = []
        total_chapters = len(chapters)

        logger.info(f"Processing {total_chapters} chapters")

        for i, chapter in enumerate(chapters):
            if progress_callback:
                progress_callback(
                    f"Processing chapter {i + 1}/{total_chapters}: {chapter.title}"
                )

            epub_chapter = self._create_single_chapter(chapter, css_item)
            if epub_chapter:
                epub_chapters.append(epub_chapter)
            else:
                logger.warning(f"Failed to create EPUB chapter: {chapter.title}")

        logger.info(f"Successfully created {len(epub_chapters)} EPUB chapters")
        return epub_chapters

    def _create_single_chapter(
        self,
        chapter: ParsedChapter,
        css_item: Optional[epub.EpubItem] = None,
    ) -> Optional[epub.EpubHtml]:
        """
        Create a single EPUB chapter from parsed chapter data.

        Args:
            chapter: Parsed chapter data
            css_item: Optional CSS item to link

        Returns:
            EPUB HTML chapter or None if failed
        """
        try:
            # Convert markdown to HTML
            html_content = self._convert_markdown_to_html(chapter.content)

            if not html_content.strip():
                logger.warning(f"Chapter '{chapter.title}' has no HTML content")
                # Provide minimal content
                html_content = "<p>This chapter appears to be empty.</p>"

            # Create complete HTML document
            full_html = self._create_chapter_html(
                chapter.title, html_content, chapter.anchor
            )

            logger.debug(
                f"Generated HTML for '{chapter.title}': {len(full_html)} characters"
            )

            # Create EPUB chapter
            epub_chapter = epub.EpubHtml(
                title=chapter.title,
                file_name=f"chapters/chapter_{chapter.chapter_number:03d}.xhtml",
                lang="en",
            )

            # Set content (convert to bytes if needed)
            if isinstance(full_html, str):
                epub_chapter.set_content(full_html.encode("utf-8"))
            else:
                epub_chapter.set_content(full_html)

            # Link CSS if available
            if css_item:
                epub_chapter.add_item(css_item)

            logger.debug(f"Created EPUB chapter: {chapter.title}")
            return epub_chapter

        except Exception as e:
            logger.error(f"Error creating EPUB chapter '{chapter.title}': {e}")
            return None

    def _convert_markdown_to_html(self, markdown_content: str) -> str:
        """
        Convert markdown content to HTML.

        Args:
            markdown_content: Markdown content

        Returns:
            HTML content
        """
        try:
            # Reset markdown processor
            self.markdown_processor.reset()

            # Convert to HTML
            html_content = self.markdown_processor.convert(markdown_content)

            # Post-process HTML
            html_content = self._post_process_html(html_content)

            return html_content

        except Exception as e:
            logger.error(f"Error converting markdown to HTML: {e}")
            # Return escaped content as fallback
            return self._escape_html(markdown_content)

    def _post_process_html(self, html_content: str) -> str:
        """
        Post-process HTML content for EPUB compatibility.

        Args:
            html_content: Raw HTML content

        Returns:
            Processed HTML content
        """
        # Add CSS classes for styling
        html_content = self._add_paragraph_classes(html_content)

        # Process scene breaks
        html_content = self._process_scene_breaks(html_content)

        # Clean up HTML
        html_content = self._clean_html(html_content)

        return html_content

    def _add_paragraph_classes(self, html_content: str) -> str:
        """
        Add CSS classes to paragraphs for styling.

        Args:
            html_content: HTML content

        Returns:
            HTML with paragraph classes
        """
        # Add first-paragraph class to first paragraph
        html_content = re.sub(
            r"<p>", '<p class="first-paragraph">', html_content, count=1
        )

        return html_content

    def _process_scene_breaks(self, html_content: str) -> str:
        """
        Process scene breaks in HTML content.

        Args:
            html_content: HTML content

        Returns:
            HTML with processed scene breaks
        """
        # Common scene break patterns
        scene_break_patterns = [
            r"<p>\s*\*\s*\*\s*\*\s*</p>",
            r"<p>\s*---\s*</p>",
            r"<p>\s*~~~\s*</p>",
            r"<p>\s*•\s*•\s*•\s*</p>",
        ]

        for pattern in scene_break_patterns:
            html_content = re.sub(
                pattern,
                '<div class="scene-break">* * *</div>',
                html_content,
                flags=re.IGNORECASE,
            )

        return html_content

    def _clean_html(self, html_content: str) -> str:
        """
        Clean HTML content for EPUB compatibility.

        Args:
            html_content: HTML content

        Returns:
            Cleaned HTML content
        """
        # Remove empty paragraphs
        html_content = re.sub(r"<p>\s*</p>", "", html_content)

        # Remove excessive whitespace
        html_content = re.sub(r"\s+", " ", html_content)

        # Ensure proper line breaks
        html_content = re.sub(r">\s*<", "><", html_content)

        return html_content.strip()

    def _create_chapter_html(self, title: str, content: str, anchor: str) -> str:
        """
        Create complete HTML document for chapter.

        Args:
            title: Chapter title
            content: HTML content
            anchor: Chapter anchor

        Returns:
            Complete HTML document
        """
        html_template = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{self._escape_html(title)}</title>
    <link rel="stylesheet" type="text/css" href="../styles/novel.css"/>
</head>
<body>
    <div class="chapter" id="{anchor}">
        <h2>{self._escape_html(title)}</h2>
        {content}
    </div>
</body>
</html>"""

        return html_template

    def _escape_html(self, text: str) -> str:
        """
        Escape HTML special characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text
        """
        if not text:
            return ""

        # Basic HTML escaping
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&#x27;")

        return text

    def validate_chapter_html(self, html_content: str) -> bool:
        """
        Validate chapter HTML for EPUB compatibility.

        Args:
            html_content: HTML content to validate

        Returns:
            True if HTML is valid
        """
        try:
            # Basic validation checks
            if not html_content.strip():
                return False

            # Check for balanced tags
            open_tags = re.findall(r"<(\w+)[^>]*>", html_content)
            close_tags = re.findall(r"</(\w+)>", html_content)

            # Self-closing tags don't need closing tags
            self_closing = {"br", "hr", "img", "input", "meta", "link"}
            open_tags = [tag for tag in open_tags if tag not in self_closing]

            if len(open_tags) != len(close_tags):
                logger.warning("HTML has unbalanced tags")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating HTML: {e}")
            return False

    def get_chapter_info(self, chapters: List[ParsedChapter]) -> Dict[str, Any]:
        """
        Get information about chapters for logging/debugging.

        Args:
            chapters: List of parsed chapters

        Returns:
            Chapter information dictionary
        """
        if not chapters:
            return {"total_chapters": 0}

        total_content_length = sum(len(chapter.content) for chapter in chapters)
        avg_content_length = total_content_length / len(chapters)

        info = {
            "total_chapters": len(chapters),
            "total_content_length": total_content_length,
            "average_content_length": int(avg_content_length),
            "longest_chapter": max(chapters, key=lambda c: len(c.content)).title,
            "shortest_chapter": min(chapters, key=lambda c: len(c.content)).title,
        }

        return info
