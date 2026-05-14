"""
EbookLib-based EPUB generator as a backup for pandoc failures.

This module provides an alternative EPUB generation method using the ebooklib
library, designed to handle large novels that cause pandoc to fail due to
memory constraints or timeouts.
"""

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ebooklib import epub
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ..utils import create_safe_directory

logger = logging.getLogger(__name__)


class EbookLibEPUBGenerator:
    """
    EPUB generator using ebooklib as a backup for pandoc failures.

    This generator maintains the same interface as EPUBGenerator but uses
    ebooklib internally to handle large novels more efficiently.
    """

    def __init__(self, config: Dict[str, Any], silent: bool = False):
        """
        Initialize EbookLib EPUB generator with configuration.

        Args:
            config: EPUB generation configuration
            silent: If True, suppress all logging except progress bar
        """
        self.config = config
        self.epub_config = config.get("epub", {})
        self.silent = silent
        self.chapter_level = self.epub_config.get("chapter_level", 2)
        self.include_toc = self.epub_config.get(
            "include_toc", True
        )  # Default to True - TOC is essential for novels
        self.custom_css = self.epub_config.get("custom_css", True)

        # EbookLib-specific settings
        self.compression = self.epub_config.get("ebooklib_compression", True)
        self.validation = self.epub_config.get("ebooklib_validation", True)

        # Flag to prevent duplicate success messages
        self._success_printed = False

        if not self.silent:
            logger.debug(
                f"EbookLibEPUBGenerator initialized with chapter_level: {self.chapter_level}, include_toc: {self.include_toc}"
            )

    def generate_epub(
        self,
        markdown_file: str,
        output_dir: Path,
        novel_title: str,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate EPUB file from markdown using ebooklib.

        Args:
            markdown_file: Path to markdown file
            output_dir: Directory to save EPUB file
            novel_title: Title of the novel
            css_file: Optional custom CSS file
            metadata: Optional novel metadata for EPUB

        Returns:
            Path to generated EPUB file or None if failed
        """
        if self.silent:
            # Silent mode - minimal progress bar
            return self._generate_epub_silent(
                markdown_file, output_dir, novel_title, css_file, metadata
            )
        else:
            # Verbose mode - full progress bar with detailed messages
            return self._generate_epub_verbose(
                markdown_file, output_dir, novel_title, css_file, metadata
            )

    def _generate_epub_verbose(
        self,
        markdown_file: str,
        output_dir: Path,
        novel_title: str,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate EPUB with verbose progress bar."""
        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=None,  # Use default console
        ) as progress:

            # Create main task
            main_task = progress.add_task("Generating EPUB...", total=100)

            # Progress callback to update the progress bar
            def update_progress(message: str, step: int = None):
                if step is not None:
                    progress.update(main_task, completed=step, description=message)
                else:
                    progress.update(main_task, description=message)

            # Call the progress method with our callback
            return self.generate_epub_with_progress(
                markdown_file,
                output_dir,
                novel_title,
                update_progress,
                css_file,
                metadata,
            )

    def _generate_epub_silent(
        self,
        markdown_file: str,
        output_dir: Path,
        novel_title: str,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate EPUB with minimal progress bar (silent mode)."""
        from rich.console import Console

        # Create a minimal progress bar
        with Progress(
            SpinnerColumn(),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=Console(
                stderr=True
            ),  # Use stderr to avoid mixing with other output
            transient=False,  # Keep progress bar visible
        ) as progress:

            # Create main task with simple description
            main_task = progress.add_task("Generating EPUB", total=100)

            # Minimal progress callback - only update percentage
            def update_progress(message: str, step: int = None):
                if step is not None:
                    progress.update(main_task, completed=step)

            # Suppress logging temporarily
            original_level = logger.level
            logger.setLevel(logging.CRITICAL)

            try:
                # Call the progress method with minimal callback
                result = self.generate_epub_with_progress(
                    markdown_file,
                    output_dir,
                    novel_title,
                    update_progress,
                    css_file,
                    metadata,
                )

                # Don't print success message here - let the CLI handle it
                # to avoid duplicate messages
                return result

            finally:
                # Restore original logging level
                logger.setLevel(original_level)

    def generate_epub_with_progress(
        self,
        markdown_file: str,
        output_dir: Path,
        novel_title: str,
        progress_callback: Optional[Callable[..., None]] = None,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate EPUB file with progress reporting.

        Args:
            markdown_file: Path to markdown file
            output_dir: Directory to save EPUB file
            novel_title: Title of the novel
            progress_callback: Optional callback for progress updates
            css_file: Optional custom CSS file
            metadata: Optional novel metadata for EPUB

        Returns:
            Path to generated EPUB file or None if failed
        """
        try:
            # Suppress logging for component classes if in silent mode
            if self.silent:
                # Suppress all logging from component modules
                component_loggers = [
                    "wn_dl.core.ebooklib_components.markdown_parser",
                    "wn_dl.core.ebooklib_components.metadata_handler",
                    "wn_dl.core.ebooklib_components.font_embedder",
                    "wn_dl.core.ebooklib_components.css_processor",
                    "wn_dl.core.ebooklib_components.chapter_processor",
                ]
                original_levels = {}
                for logger_name in component_loggers:
                    component_logger = logging.getLogger(logger_name)
                    original_levels[logger_name] = component_logger.level
                    component_logger.setLevel(logging.CRITICAL)

            if progress_callback:
                progress_callback("Preparing EPUB generation with ebooklib...", 5)

            # Create output directory
            if not create_safe_directory(output_dir):
                logger.error(f"Failed to create output directory: {output_dir}")
                return None

            # Generate output filename
            epub_filename = self._generate_epub_filename(novel_title)
            epub_path = output_dir / epub_filename

            if progress_callback:
                progress_callback("Parsing markdown content...", 10)

            # Parse markdown file
            from .ebooklib_components.markdown_parser import MarkdownParser

            parser = MarkdownParser(self.config)
            parsed_data = parser.parse_markdown_file(markdown_file)

            if not parsed_data:
                logger.error("Failed to parse markdown file")
                return None

            if progress_callback:
                progress_callback(
                    f"Creating EPUB structure ({len(parsed_data.chapters)} chapters)...",
                    20,
                )

            # Create EPUB book
            book = epub.EpubBook()

            # Set metadata
            from .ebooklib_components.metadata_handler import MetadataHandler

            metadata_handler = MetadataHandler(self.config)
            metadata_handler.set_book_metadata(book, parsed_data.metadata, metadata)

            if progress_callback:
                progress_callback("Embedding fonts and resources...", 30)

            # Process and embed fonts
            from .ebooklib_components.font_embedder import FontEmbedder

            # Get selected font from config
            selected_font = self.epub_config.get("font_family")
            font_embedder = FontEmbedder(self.config, selected_font)
            font_embedder.embed_fonts(book)

            # Process CSS
            from .ebooklib_components.css_processor import CSSProcessor

            css_processor = CSSProcessor(self.config, selected_font)
            css_item = css_processor.create_css_item(css_file)
            if css_item:
                book.add_item(css_item)

            # Process cover image - check multiple possible keys
            cover_path = None
            cover_keys = ["cover_path", "cover-image", "cover_image", "cover"]
            for key in cover_keys:
                if parsed_data.metadata.get(key):
                    cover_path = parsed_data.metadata[key]
                    break

            if cover_path:
                cover_item = self._process_cover_image(book, cover_path)
                if cover_item:
                    book.add_item(cover_item)
                else:
                    logger.warning(f"Failed to process cover image: {cover_path}")
            else:
                logger.info("No cover image found in metadata")

            if progress_callback:
                progress_callback("Converting chapters to HTML...", 40)

            # Create chapters
            from .ebooklib_components.chapter_processor import ChapterProcessor

            chapter_processor = ChapterProcessor(self.config)

            # Create a wrapper callback for chapter progress (40-70% range)
            def chapter_progress_callback(message: str):
                if progress_callback:
                    # Extract chapter number from message if possible
                    if "Processing chapter" in message and "/" in message:
                        try:
                            # Extract current/total from "Processing chapter X/Y: Title"
                            parts = message.split("Processing chapter ")[1].split("/")
                            current = int(parts[0])
                            total = int(parts[1].split(":")[0])
                            # Map to 40-70% range
                            progress = 40 + (current / total) * 30
                            progress_callback(message, int(progress))
                        except:
                            progress_callback(message, 50)
                    else:
                        progress_callback(message, 50)

            chapters = chapter_processor.create_epub_chapters(
                parsed_data.chapters, css_item, chapter_progress_callback
            )

            if progress_callback:
                progress_callback(f"Adding {len(chapters)} chapters to EPUB...", 70)

            for chapter in chapters:
                book.add_item(chapter)

            if progress_callback:
                progress_callback("Building navigation and table of contents...", 80)

            # Create table of contents
            if self.include_toc:
                if not self.silent:
                    logger.info(f"Creating TOC for {len(chapters)} chapters")
                book.toc = self._create_table_of_contents(chapters)
                if not self.silent:
                    logger.info(f"TOC created with {len(book.toc)} entries")
            else:
                if not self.silent:
                    logger.info("TOC generation disabled")

            # Add navigation files
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            # Set spine (order of reading)
            book.spine = ["nav"] + chapters

            if progress_callback:
                progress_callback("Writing EPUB file to disk...", 90)

            # Write EPUB file
            write_options = {}
            if not self.compression:
                write_options["epub3_pages"] = False

            epub.write_epub(str(epub_path), book, write_options)

            # Validate if enabled
            if self.validation:
                if progress_callback:
                    progress_callback("Validating EPUB structure...", 95)
                self._validate_epub(epub_path)

            if progress_callback:
                progress_callback("EPUB generation completed successfully!", 100)

            if not self.silent:
                logger.info(f"Successfully generated EPUB with ebooklib: {epub_path}")
            return str(epub_path)

        except Exception as e:
            if progress_callback:
                progress_callback(f"EPUB generation failed: {e}")
            if not self.silent:
                logger.error(f"Error generating EPUB with ebooklib: {e}")
            return None

        finally:
            # Restore original logging levels if they were suppressed
            if self.silent and "original_levels" in locals():
                for logger_name, level in original_levels.items():
                    component_logger = logging.getLogger(logger_name)
                    component_logger.setLevel(level)

    def _generate_epub_filename(self, novel_title: str) -> str:
        """
        Generate safe EPUB filename from novel title.

        Args:
            novel_title: Title of the novel

        Returns:
            Safe filename for EPUB
        """
        # Remove or replace unsafe characters
        safe_title = "".join(
            c for c in novel_title if c.isalnum() or c in (" ", "-", "_")
        ).strip()

        # Replace spaces with underscores and limit length
        safe_title = safe_title.replace(" ", "_")[:50]

        return f"{safe_title}.epub"

    def _create_table_of_contents(self, chapters: List[epub.EpubHtml]) -> List:
        """
        Create table of contents from chapters.

        Args:
            chapters: List of EPUB chapters

        Returns:
            Table of contents structure
        """
        toc_items = []
        for i, chapter in enumerate(chapters):
            try:
                link = epub.Link(chapter.get_name(), chapter.title, chapter.get_id())
                toc_items.append(link)
                if not self.silent and i < 3:  # Log first 3 for debugging
                    logger.debug(
                        f"TOC entry {i+1}: {chapter.title} -> {chapter.get_name()}"
                    )
            except Exception as e:
                if not self.silent:
                    logger.error(f"Error creating TOC entry for chapter {i+1}: {e}")

        if not self.silent:
            logger.info(f"Created {len(toc_items)} TOC entries")
        return toc_items

    def _process_cover_image(
        self, book: epub.EpubBook, cover_path: str
    ) -> Optional[epub.EpubImage]:
        """
        Process and add cover image to EPUB with quality optimization.

        Args:
            book: EPUB book object
            cover_path: Path to cover image

        Returns:
            Cover image item or None if failed
        """
        try:
            cover_path_obj = Path(cover_path)

            # If path is not absolute, try to resolve it relative to common locations
            if not cover_path_obj.is_absolute():
                # Try current working directory first
                if not cover_path_obj.exists():
                    # Try relative to the markdown file directory if available
                    # This is a fallback for when cover paths are relative
                    logger.debug(f"Trying to resolve relative cover path: {cover_path}")

            if not cover_path_obj.exists():
                logger.warning(f"Cover image not found: {cover_path}")
                return None

            # Process image with quality optimization
            processed_content = self._optimize_cover_image(cover_path_obj)
            if not processed_content:
                logger.error("Failed to optimize cover image")
                return None

            # Determine output format and media type
            output_format = self._get_cover_output_format(cover_path_obj)
            media_type = self._get_media_type(output_format)

            # Create cover image item
            cover_item = epub.EpubImage(
                uid="cover_image",
                file_name=f"images/cover.{output_format.lower()}",
                media_type=media_type,
                content=processed_content,
            )

            # Set as cover image in EPUB
            book.set_cover("images/cover.jpg", processed_content)

            logger.info(f"Successfully processed and embedded cover image")
            return cover_item

        except Exception as e:
            logger.error(f"Error processing cover image: {e}")
            return None

    def _optimize_cover_image(self, cover_path: Path) -> Optional[bytes]:
        """
        Optimize cover image for EPUB with resizing and quality adjustment.

        Args:
            cover_path: Path to original cover image

        Returns:
            Optimized image content as bytes or None if failed
        """
        try:
            import io

            from PIL import Image

            # Read and open image
            with open(cover_path, "rb") as f:
                image_data = f.read()

            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary (for JPEG output)
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Get cover processing configuration
            cover_config = self.config.get("cover_processing", {})
            target_size = tuple(cover_config.get("target_size", (600, 800)))
            quality = cover_config.get("quality", 85)

            # Resize image maintaining aspect ratio
            image = self._resize_cover_image(image, target_size)

            # Save optimized image to bytes
            output_buffer = io.BytesIO()
            image.save(output_buffer, format="JPEG", quality=quality, optimize=True)

            optimized_content = output_buffer.getvalue()

            # Log optimization results
            original_size = len(image_data)
            optimized_size = len(optimized_content)
            compression_ratio = (1 - optimized_size / original_size) * 100

            logger.debug(
                f"Cover image optimized: {original_size:,} → {optimized_size:,} bytes "
                f"({compression_ratio:.1f}% reduction)"
            )

            return optimized_content

        except Exception as e:
            logger.error(f"Error optimizing cover image: {e}")
            return None

    def _resize_cover_image(self, image, target_size: tuple):
        """
        Resize cover image maintaining aspect ratio.

        Args:
            image: PIL Image object
            target_size: Target size tuple (width, height)

        Returns:
            Resized PIL Image
        """
        from PIL import Image

        # Calculate aspect ratios
        original_ratio = image.width / image.height
        target_ratio = target_size[0] / target_size[1]

        if original_ratio > target_ratio:
            # Image is wider than target ratio
            new_width = target_size[0]
            new_height = int(target_size[0] / original_ratio)
        else:
            # Image is taller than target ratio
            new_height = target_size[1]
            new_width = int(target_size[1] * original_ratio)

        # Resize image with high-quality resampling
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create final image with target size and center the resized image
        final_image = Image.new("RGB", target_size, (255, 255, 255))

        # Calculate position to center the image
        x = (target_size[0] - new_width) // 2
        y = (target_size[1] - new_height) // 2

        final_image.paste(resized, (x, y))

        return final_image

    def _get_cover_output_format(self, cover_path: Path) -> str:
        """
        Determine output format for cover image.

        Args:
            cover_path: Path to original cover image (unused, always returns JPEG)

        Returns:
            Output format string
        """
        # Always use JPEG for EPUB covers for better compatibility and smaller size
        return "JPEG"

    def _get_media_type(self, format_str: str) -> str:
        """
        Get media type for image format.

        Args:
            format_str: Image format string

        Returns:
            MIME media type
        """
        format_map = {
            "JPEG": "image/jpeg",
            "JPG": "image/jpeg",
            "PNG": "image/png",
            "GIF": "image/gif",
            "WEBP": "image/webp",
        }
        return format_map.get(format_str.upper(), "image/jpeg")

    def _validate_epub(self, epub_path: Path) -> bool:
        """
        Validate EPUB structure (comprehensive validation).

        Args:
            epub_path: Path to EPUB file

        Returns:
            True if validation passes
        """
        try:
            # Basic validation - check if file exists and has content
            if not epub_path.exists():
                logger.error("EPUB file does not exist")
                return False

            file_size = epub_path.stat().st_size
            if file_size == 0:
                logger.error("EPUB file is empty")
                return False

            # Check minimum file size (EPUB should be at least a few KB)
            min_size = 1024  # 1KB minimum
            if file_size < min_size:
                logger.warning(
                    f"EPUB file is very small ({file_size} bytes), may be corrupted"
                )

            # Try to open as ZIP file (EPUB is a ZIP archive)
            import zipfile

            try:
                with zipfile.ZipFile(epub_path, "r") as zip_file:
                    # Check for required EPUB files
                    required_files = ["META-INF/container.xml", "mimetype"]
                    missing_files = []

                    file_list = zip_file.namelist()
                    for required_file in required_files:
                        if required_file not in file_list:
                            missing_files.append(required_file)

                    if missing_files:
                        logger.error(f"EPUB missing required files: {missing_files}")
                        return False

                    # Check mimetype content
                    try:
                        mimetype_content = (
                            zip_file.read("mimetype").decode("utf-8").strip()
                        )
                        if mimetype_content != "application/epub+zip":
                            logger.warning(f"Incorrect mimetype: {mimetype_content}")
                    except Exception as e:
                        logger.warning(f"Could not validate mimetype: {e}")

                    logger.debug(f"EPUB contains {len(file_list)} files")

            except zipfile.BadZipFile:
                logger.error("EPUB file is not a valid ZIP archive")
                return False

            logger.info(f"EPUB validation passed. File size: {file_size:,} bytes")
            return True

        except Exception as e:
            logger.error(f"Error during EPUB validation: {e}")
            return False

    def validate_input_data(
        self, markdown_file: str, output_dir: Path, novel_title: str
    ) -> bool:
        """
        Validate input parameters before EPUB generation.

        Args:
            markdown_file: Path to markdown file
            output_dir: Output directory
            novel_title: Novel title

        Returns:
            True if all inputs are valid
        """
        try:
            # Validate markdown file
            markdown_path = Path(markdown_file)
            if not markdown_path.exists():
                logger.error(f"Markdown file does not exist: {markdown_file}")
                return False

            if not markdown_path.is_file():
                logger.error(f"Markdown path is not a file: {markdown_file}")
                return False

            # Check file size
            file_size = markdown_path.stat().st_size
            if file_size == 0:
                logger.error("Markdown file is empty")
                return False

            # Check if file is too large (>100MB might cause issues)
            max_size = 100 * 1024 * 1024  # 100MB
            if file_size > max_size:
                logger.warning(
                    f"Markdown file is very large ({file_size:,} bytes), may cause performance issues"
                )

            # Validate output directory
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.error(f"Cannot create output directory: {e}")
                    return False

            if not output_dir.is_dir():
                logger.error(f"Output path is not a directory: {output_dir}")
                return False

            # Check write permissions
            if not os.access(output_dir, os.W_OK):
                logger.error(f"No write permission for output directory: {output_dir}")
                return False

            # Validate novel title
            if not novel_title or not novel_title.strip():
                logger.error("Novel title is empty")
                return False

            if len(novel_title) > 255:
                logger.warning(
                    f"Novel title is very long ({len(novel_title)} characters)"
                )

            logger.debug("Input validation passed")
            return True

        except Exception as e:
            logger.error(f"Error during input validation: {e}")
            return False

    def get_generation_info(self) -> Dict[str, Any]:
        """
        Get information about the generator configuration and capabilities.

        Returns:
            Dictionary with generator information
        """
        return {
            "generator": "EbookLibEPUBGenerator",
            "version": "1.0.0",
            "chapter_level": self.chapter_level,
            "include_toc": self.include_toc,
            "custom_css": self.custom_css,
            "compression": self.compression,
            "validation": self.validation,
            "dependencies": {
                "ebooklib": True,
                "markdown": True,
                "pillow": True,
            },
        }
