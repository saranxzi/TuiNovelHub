"""
EPUB generation module using Pandoc.

This module handles the conversion of markdown to EPUB format using Pandoc.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..utils import clean_filename, create_safe_directory

logger = logging.getLogger(__name__)


class EPUBGenerator:
    """
    Generates EPUB files from markdown using Pandoc.

    Handles Pandoc integration, CSS styling, and EPUB validation.
    """

    def __init__(self, config: Dict[str, Any], silent: bool = False):
        """
        Initialize EPUB generator with configuration.

        Args:
            config: EPUB generation configuration
            silent: If True, suppress verbose output
        """
        self.config = config
        self.epub_config = config.get("epub", {})
        self.silent = silent
        self.chapter_level = self.epub_config.get("chapter_level", 2)
        self.include_toc = self.epub_config.get("include_toc", True)
        self.custom_css = self.epub_config.get("custom_css", True)
        self.pandoc_args = self.epub_config.get("pandoc_args", [])

        # EbookLib fallback settings
        self.ebooklib_fallback = self.epub_config.get("ebooklib_fallback", True)
        self.force_ebooklib = self.epub_config.get("use_ebooklib", False)

        # Check if Pandoc is available
        self.pandoc_available = self._check_pandoc()

        if not self.silent:
            logger.debug(
                f"EPUBGenerator initialized, Pandoc available: {self.pandoc_available}, "
                f"EbookLib fallback: {self.ebooklib_fallback}, Force EbookLib: {self.force_ebooklib}"
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
        Generate EPUB file from markdown with enhanced metadata.

        Args:
            markdown_file: Path to markdown file
            output_dir: Directory to save EPUB file
            novel_title: Title of the novel
            css_file: Optional custom CSS file
            metadata: Optional novel metadata for EPUB

        Returns:
            Path to generated EPUB file or None if failed
        """
        # Check if we should force ebooklib usage
        if self.force_ebooklib:
            logger.info("Forcing EbookLib EPUB generation")
            return self._generate_epub_with_ebooklib(
                markdown_file, output_dir, novel_title, css_file, metadata
            )

        # Check if pandoc is available
        if not self.pandoc_available:
            if self.ebooklib_fallback:
                logger.warning("Pandoc not available, falling back to EbookLib")
                return self._generate_epub_with_ebooklib(
                    markdown_file, output_dir, novel_title, css_file, metadata
                )
            else:
                logger.error("Pandoc is not available. Cannot generate EPUB.")
                return None

        try:
            # Create output directory
            if not create_safe_directory(output_dir):
                logger.error(f"Failed to create output directory: {output_dir}")
                return None

            # Generate output filename
            epub_filename = self._generate_epub_filename(novel_title)
            epub_path = output_dir / epub_filename

            # Create CSS file if needed
            if self.custom_css and not css_file:
                css_file = self._create_default_css(output_dir)

            # Build Pandoc command with metadata (fonts will be embedded automatically)
            pandoc_cmd = self._build_pandoc_command(
                markdown_file, str(epub_path), css_file, metadata
            )

            # Calculate timeout based on file size
            timeout = self._calculate_timeout(markdown_file)
            logger.info(f"Using timeout of {timeout} seconds for EPUB generation")

            # Run Pandoc with dynamic timeout
            result = subprocess.run(
                pandoc_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                logger.info(f"Successfully generated EPUB: {epub_path}")
                return str(epub_path)
            else:
                logger.error(f"Pandoc failed with return code {result.returncode}")
                logger.error(f"Pandoc stderr: {result.stderr}")

                # Provide specific guidance for large file failures
                if result.returncode == -9:
                    self._handle_large_file_failure(markdown_file)

                # Try fallback to ebooklib if enabled
                if self.ebooklib_fallback:
                    logger.warning("Pandoc failed, attempting fallback to EbookLib")
                    return self._generate_epub_with_ebooklib(
                        markdown_file, output_dir, novel_title, css_file, metadata
                    )

                return None

        except subprocess.TimeoutExpired:
            logger.error("Pandoc process timed out")
            # Try fallback to ebooklib if enabled
            if self.ebooklib_fallback:
                logger.warning("Pandoc timed out, attempting fallback to EbookLib")
                return self._generate_epub_with_ebooklib(
                    markdown_file, output_dir, novel_title, css_file, metadata
                )
            return None
        except Exception as e:
            logger.error(f"Error generating EPUB: {e}")
            # Try fallback to ebooklib if enabled
            if self.ebooklib_fallback:
                logger.warning("Pandoc error, attempting fallback to EbookLib")
                return self._generate_epub_with_ebooklib(
                    markdown_file, output_dir, novel_title, css_file, metadata
                )
            return None

    def generate_epub_with_progress(
        self,
        markdown_file: str,
        output_dir: Path,
        novel_title: str,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> Optional[str]:
        """
        Generate EPUB file with progress tracking.

        Args:
            markdown_file: Path to markdown file
            output_dir: Directory to save EPUB file
            novel_title: Title of the novel
            css_file: Optional custom CSS file
            metadata: Optional novel metadata for EPUB
            progress_callback: Optional callback for progress updates

        Returns:
            Path to generated EPUB file or None if failed
        """
        # Check if we should force ebooklib usage
        if self.force_ebooklib:
            if progress_callback:
                progress_callback("Using EbookLib EPUB generation...")
            return self._generate_epub_with_ebooklib_progress(
                markdown_file,
                output_dir,
                novel_title,
                css_file,
                metadata,
                progress_callback,
            )

        # Check if pandoc is available
        if not self.pandoc_available:
            if self.ebooklib_fallback:
                if progress_callback:
                    progress_callback(
                        "Pandoc not available, falling back to EbookLib..."
                    )
                return self._generate_epub_with_ebooklib_progress(
                    markdown_file,
                    output_dir,
                    novel_title,
                    css_file,
                    metadata,
                    progress_callback,
                )
            else:
                logger.error("Pandoc is not available. Cannot generate EPUB.")
                return None

        try:
            if progress_callback:
                progress_callback("Preparing EPUB generation...")

            # Create output directory
            if not create_safe_directory(output_dir):
                logger.error(f"Failed to create output directory: {output_dir}")
                return None

            # Generate output filename
            epub_filename = self._generate_epub_filename(novel_title)
            epub_path = output_dir / epub_filename

            if progress_callback:
                progress_callback("Creating CSS styles...")

            # Create CSS file if needed
            if self.custom_css and not css_file:
                css_file = self._create_default_css(output_dir)

            if progress_callback:
                progress_callback("Building Pandoc command...")

            # Build Pandoc command with metadata
            pandoc_cmd = self._build_pandoc_command(
                markdown_file, str(epub_path), css_file, metadata
            )

            if progress_callback:
                progress_callback("Running Pandoc conversion...")

            # Calculate timeout based on file size
            timeout = self._calculate_timeout(markdown_file)
            logger.info(f"Using timeout of {timeout} seconds for EPUB generation")

            # Run Pandoc with progress monitoring and dynamic timeout
            result = self._run_pandoc_with_progress(
                pandoc_cmd, progress_callback, timeout
            )

            if result.returncode == 0:
                if progress_callback:
                    progress_callback("EPUB generation completed successfully!")
                logger.info(f"Successfully generated EPUB: {epub_path}")
                return str(epub_path)
            else:
                if progress_callback:
                    progress_callback("EPUB generation failed!")
                logger.error(f"Pandoc failed with return code {result.returncode}")
                logger.error(f"Pandoc stderr: {result.stderr}")

                # Provide specific guidance for large file failures
                if result.returncode == -9:
                    self._handle_large_file_failure(markdown_file)

                # Try fallback to ebooklib if enabled
                if self.ebooklib_fallback:
                    if progress_callback:
                        progress_callback("Pandoc failed, trying EbookLib fallback...")
                    return self._generate_epub_with_ebooklib_progress(
                        markdown_file,
                        output_dir,
                        novel_title,
                        css_file,
                        metadata,
                        progress_callback,
                    )

                return None

        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback("EPUB generation timed out!")
            logger.error("Pandoc process timed out")
            # Try fallback to ebooklib if enabled
            if self.ebooklib_fallback:
                if progress_callback:
                    progress_callback("Pandoc timed out, trying EbookLib fallback...")
                return self._generate_epub_with_ebooklib_progress(
                    markdown_file,
                    output_dir,
                    novel_title,
                    css_file,
                    metadata,
                    progress_callback,
                )
            return None
        except Exception as e:
            if progress_callback:
                progress_callback(f"EPUB generation error: {e}")
            logger.error(f"Error generating EPUB: {e}")
            # Try fallback to ebooklib if enabled
            if self.ebooklib_fallback:
                if progress_callback:
                    progress_callback("Pandoc error, trying EbookLib fallback...")
                return self._generate_epub_with_ebooklib_progress(
                    markdown_file,
                    output_dir,
                    novel_title,
                    css_file,
                    metadata,
                    progress_callback,
                )
            return None

    def _run_pandoc_with_progress(
        self,
        pandoc_cmd: List[str],
        progress_callback: Optional[Callable[[str], None]] = None,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        """
        Run Pandoc with progress monitoring.

        Args:
            pandoc_cmd: Pandoc command to execute
            progress_callback: Optional callback for progress updates
            timeout: Timeout in seconds for the process

        Returns:
            CompletedProcess result
        """
        import threading
        import time

        # Start the process
        process = subprocess.Popen(
            pandoc_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Progress monitoring thread
        def monitor_progress():
            start_time = time.time()
            while process.poll() is None:
                elapsed = time.time() - start_time
                if progress_callback:
                    progress_callback(f"Converting to EPUB... ({elapsed:.1f}s elapsed)")
                time.sleep(2.0)  # Update every 2 seconds

        # Start monitoring thread
        if progress_callback:
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()

        # Wait for completion with timeout
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return subprocess.CompletedProcess(
                pandoc_cmd, process.returncode, stdout, stderr
            )
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(pandoc_cmd, timeout, stdout, stderr)

    def _calculate_timeout(self, markdown_file: str) -> int:
        """
        Calculate appropriate timeout based on file size.

        Args:
            markdown_file: Path to markdown file

        Returns:
            Timeout in seconds
        """
        try:
            file_size_mb = Path(markdown_file).stat().st_size / (1024 * 1024)

            # Base timeout of 5 minutes
            base_timeout = 300

            # Add 2 minutes per MB for large files
            if file_size_mb > 10:  # Files larger than 10MB
                additional_timeout = int((file_size_mb - 10) * 120)  # 2 minutes per MB
                timeout = base_timeout + additional_timeout

                # Cap at 30 minutes for very large files
                timeout = min(timeout, 1800)

                logger.info(
                    f"Large file detected ({file_size_mb:.1f}MB), using extended timeout"
                )
                return timeout
            else:
                return base_timeout

        except Exception as e:
            logger.warning(
                f"Could not determine file size for timeout calculation: {e}"
            )
            return 300  # Default 5 minutes

    def _handle_large_file_failure(self, markdown_file: str) -> None:
        """
        Handle failures specific to large files and provide guidance.

        Args:
            markdown_file: Path to the markdown file that failed
        """
        try:
            file_size_mb = Path(markdown_file).stat().st_size / (1024 * 1024)

            logger.error("=" * 60)
            logger.error("LARGE FILE PROCESSING FAILURE")
            logger.error("=" * 60)
            logger.error(f"File size: {file_size_mb:.1f}MB")
            logger.error(
                "Pandoc was killed (return code -9), likely due to memory constraints."
            )
            logger.error("")
            logger.error("POSSIBLE SOLUTIONS:")
            logger.error("1. Try splitting the novel into smaller volumes")
            logger.error("2. Increase system memory or swap space")
            logger.error("3. Close other applications to free memory")
            logger.error("4. Try processing on a machine with more RAM")
            logger.error("")
            logger.error(
                "For novels with 1000+ chapters, consider splitting into volumes"
            )
            logger.error("of 200-500 chapters each for better EPUB compatibility.")
            logger.error("=" * 60)

        except Exception:
            logger.error(f"Large file processing failed. File: {markdown_file}")
            logger.error("Consider splitting large novels into smaller volumes.")

    def _check_pandoc(self) -> bool:
        """
        Check if Pandoc is available.

        Returns:
            True if Pandoc is available
        """
        try:
            result = subprocess.run(
                ["pandoc", "--version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _build_pandoc_command(
        self,
        input_file: str,
        output_file: str,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Build Pandoc command line arguments with enhanced metadata.

        Args:
            input_file: Input markdown file
            output_file: Output EPUB file
            css_file: Optional CSS file
            metadata: Optional novel metadata

        Returns:
            List of command line arguments
        """
        cmd = [
            "pandoc",
            input_file,
            "-o",
            output_file,
            "--from",
            "markdown",
            "--to",
            "epub3",
            "--standalone",
        ]

        # Add optimization options for large files
        try:
            file_size_mb = Path(input_file).stat().st_size / (1024 * 1024)
            if file_size_mb > 10:  # Files larger than 10MB
                logger.info(
                    f"Adding optimization options for large file ({file_size_mb:.1f}MB)"
                )
                # Reduce memory usage for large files
                cmd.extend(
                    [
                        "--resource-path",
                        str(Path(input_file).parent),  # Optimize resource loading
                    ]
                )
        except Exception as e:
            logger.debug(f"Could not determine file size for optimization: {e}")

        # Add table of contents
        if self.include_toc:
            cmd.extend(["--toc", "--toc-depth=2"])

        # Add CSS file
        if css_file and Path(css_file).exists():
            cmd.extend(["--css", css_file])

        # Add metadata if provided
        if metadata:
            self._add_metadata_to_command(cmd, metadata)

        # Add font embedding for EPUB
        self._add_font_embedding_to_command(cmd)

        # Add custom Pandoc arguments
        if self.pandoc_args:
            cmd.extend(self.pandoc_args)

        return cmd

    def _add_metadata_to_command(
        self, cmd: List[str], metadata: Dict[str, Any]
    ) -> None:
        """
        Add metadata arguments to Pandoc command.

        Args:
            cmd: Pandoc command list to modify
            metadata: Novel metadata dictionary
        """
        # Add title
        if metadata.get("title"):
            cmd.extend(["--metadata", f"title={metadata['title']}"])

        # Add author
        if metadata.get("author"):
            cmd.extend(["--metadata", f"author={metadata['author']}"])

        # Add description/summary
        if metadata.get("description"):
            cmd.extend(["--metadata", f"description={metadata['description']}"])

        # Add language (default to English if not specified)
        language = metadata.get("language", "en")
        cmd.extend(["--metadata", f"lang={language}"])

        # Add publication date
        if metadata.get("publication_date"):
            pub_date = metadata["publication_date"]
            if hasattr(pub_date, "isoformat"):
                cmd.extend(["--metadata", f"date={pub_date.isoformat()[:10]}"])
            else:
                cmd.extend(["--metadata", f"date={str(pub_date)}"])

        # Add genres as subjects
        if metadata.get("genres"):
            for genre in metadata["genres"]:
                cmd.extend(["--metadata", f"subject={genre}"])

        # Add tags as keywords
        if metadata.get("tags"):
            keywords = ", ".join(metadata["tags"])
            cmd.extend(["--metadata", f"keywords={keywords}"])

        # Add source URL as identifier
        if metadata.get("source_url"):
            cmd.extend(["--metadata", f"identifier={metadata['source_url']}"])

        # Add publisher (if available)
        if metadata.get("publisher"):
            cmd.extend(["--metadata", f"publisher={metadata['publisher']}"])

        # Add cover image if available
        if metadata.get("cover_path") and Path(metadata["cover_path"]).exists():
            cmd.extend(["--epub-cover-image", metadata["cover_path"]])

    def _add_font_embedding_to_command(self, cmd: List[str]) -> None:
        """
        Add font embedding arguments to Pandoc command for EPUB.

        Args:
            cmd: Pandoc command list to modify
        """
        # Get font files from templates directory
        template_fonts_dir = Path(__file__).parent.parent / "templates" / "fonts"

        if template_fonts_dir.exists():
            # Add each font file for embedding
            for font_file in template_fonts_dir.glob("*.ttf"):
                cmd.extend(["--epub-embed-font", str(font_file)])
                logger.debug(f"Added font for embedding: {font_file.name}")
        else:
            logger.warning(
                "Template fonts directory not found, skipping font embedding"
            )

    def _create_default_css(self, output_dir: Path) -> Optional[str]:
        """
        Create enhanced CSS file for EPUB with custom fonts.

        Args:
            output_dir: Directory to save CSS file

        Returns:
            Path to CSS file or None if failed
        """
        try:
            # Get selected font from config
            selected_font = self.epub_config.get("font_family")

            # Generate dynamic CSS based on selected font
            try:
                from .css_generator import generate_css_for_font

                css_content = generate_css_for_font(selected_font)
                logger.debug(f"Generated dynamic CSS for font: {selected_font}")
            except Exception as e:
                logger.warning(
                    f"Error generating dynamic CSS: {e}, falling back to template"
                )

                # Fallback to static template
                template_css_path = (
                    Path(__file__).parent.parent / "templates" / "novel.css"
                )
                if template_css_path.exists():
                    with open(template_css_path, "r", encoding="utf-8") as src:
                        css_content = src.read()
                    logger.debug(f"Using static CSS template: {template_css_path}")
                else:
                    # Last resort fallback
                    css_content = self._get_default_css_content()
                    logger.warning("Using minimal fallback CSS")

            # Write CSS file
            css_path = output_dir / "novel.css"
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(css_content)

            logger.debug(f"Created CSS file: {css_path}")
            return str(css_path)

        except Exception as e:
            logger.error(f"Error creating CSS file: {e}")
            return None

    def _copy_font_files(self, output_dir: Path) -> bool:
        """
        Copy selected font family files to EPUB structure for embedding.

        Args:
            output_dir: Directory to copy fonts to

        Returns:
            True if fonts copied successfully
        """
        try:
            # Create fonts directory in output
            fonts_dir = output_dir / "fonts"
            fonts_dir.mkdir(exist_ok=True)

            # Get selected font from config
            from .font_manager import get_font_manager

            font_manager = get_font_manager()
            selected_font = self.epub_config.get("font_family")
            resolved_font = font_manager.resolve_font(selected_font)
            font_family = font_manager.get_font_family(resolved_font)

            if not font_family:
                logger.warning(
                    f"Font family not found: {resolved_font}, skipping font embedding"
                )
                return False

            # Copy only the selected font family files
            copied_count = 0
            for variant in font_family.variants.values():
                if variant.file_path.exists():
                    dest_file = fonts_dir / variant.file_path.name
                    shutil.copy2(variant.file_path, dest_file)
                    logger.debug(f"Copied font file: {variant.file_path.name}")
                    copied_count += 1
                else:
                    logger.warning(f"Font file not found: {variant.file_path}")

            if copied_count > 0:
                logger.info(
                    f"Copied {copied_count} font files for '{font_family.display_name}' family to EPUB"
                )
                return True
            else:
                logger.warning("No font files copied")
                return False

        except Exception as e:
            logger.error(f"Error copying font files: {e}")
            return False

    def _get_default_css_content(self) -> str:
        """
        Get default CSS content for EPUB styling.

        Returns:
            CSS content string
        """
        return """
/* Novel EPUB Styling */

/* Body and general styling */
body {
    font-family: "Bitter", serif;
    font-size: 1.1em;
    line-height: 1.6;
    margin: 0;
    padding: 1em;
    color: #333;
    text-align: justify;
}

/* Headings */
h1, h2, h3, h4, h5, h6 {
    font-family: "Georgia", "Times New Roman", serif;
    font-weight: bold;
    margin-top: 2em;
    margin-bottom: 1em;
    text-align: center;
    color: #1a1a1a;
}

h1 {
    font-size: 2.2em;
    border-bottom: 3px solid #3498db;
    padding-bottom: 0.5em;
}

h2 {
    font-size: 1.8em;
    border-bottom: 2px solid #3498db;
    padding-bottom: 0.3em;
}

h3 {
    font-size: 1.5em;
}

/* Paragraphs */
p {
    margin: 1em 0;
    text-indent: 1.5em;
}

/* First paragraph after heading should not be indented */
h1 + p, h2 + p, h3 + p, h4 + p, h5 + p, h6 + p {
    text-indent: 0;
}

/* Emphasis */
em, i {
    font-style: italic;
}

strong, b {
    font-weight: bold;
    color: #2c3e50;
}

/* Links */
a {
    color: #3498db;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* Table of Contents */
nav#TOC {
    border: 1px solid #ddd;
    padding: 1em;
    margin: 2em 0;
    background-color: #f9f9f9;
}

nav#TOC ul {
    list-style-type: none;
    padding-left: 0;
}

nav#TOC li {
    margin: 0.5em 0;
    padding-left: 1em;
}

nav#TOC a {
    color: #2c3e50;
    font-weight: normal;
}

/* Chapter breaks */
.chapter {
    page-break-before: always;
}

/* Blockquotes */
blockquote {
    margin: 1.5em 2em;
    padding: 1em;
    border-left: 4px solid #3498db;
    background-color: #f8f9fa;
    font-style: italic;
}

/* Code blocks (if any) */
pre, code {
    font-family: "FiraCode Nerd Font Mono", "Courier New", monospace;
    background-color: #f4f4f4;
    padding: 0.2em 0.4em;
    border-radius: 3px;
}

pre {
    padding: 1em;
    overflow-x: auto;
    border: 1px solid #ddd;
}

/* Lists */
ul, ol {
    margin: 1em 0;
    padding-left: 2em;
}

li {
    margin: 0.5em 0;
}

/* Horizontal rules */
hr {
    border: none;
    border-top: 2px solid #3498db;
    margin: 2em 0;
    text-align: center;
}

/* Page breaks */
.page-break {
    page-break-after: always;
}

/* Title page styling */
.title-page {
    text-align: center;
    page-break-after: always;
}

.title-page h1 {
    font-size: 3em;
    margin-top: 2em;
    margin-bottom: 1em;
    border: none;
}

.title-page .author {
    font-size: 1.5em;
    font-style: italic;
    color: #7f8c8d;
    margin-bottom: 2em;
}

.title-page .description {
    text-align: left;
    margin: 2em auto;
    max-width: 80%;
    font-size: 1.1em;
    line-height: 1.8;
}

/* Responsive design for different screen sizes */
@media screen and (max-width: 600px) {
    body {
        font-size: 1em;
        padding: 0.5em;
    }
    
    h1 {
        font-size: 1.8em;
    }
    
    h2 {
        font-size: 1.5em;
    }
    
    p {
        text-indent: 1em;
    }
}

/* Print styles */
@media print {
    body {
        font-size: 12pt;
        line-height: 1.4;
    }
    
    h1, h2, h3 {
        page-break-after: avoid;
    }
    
    p {
        orphans: 3;
        widows: 3;
    }
}
"""

    def _generate_epub_filename(self, title: str) -> str:
        """
        Generate filename for EPUB file.

        Args:
            title: Novel title

        Returns:
            Generated filename
        """
        base_name = clean_filename(title)
        return f"{base_name}.epub"

    def validate_epub(self, epub_path: str) -> bool:
        """
        Validate EPUB file using epubcheck if available.

        Args:
            epub_path: Path to EPUB file

        Returns:
            True if EPUB is valid or validation tool not available
        """
        try:
            # Check if epubcheck is available
            result = subprocess.run(
                ["epubcheck", "--version"], capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                logger.debug("epubcheck not available, skipping validation")
                return True

            # Run validation
            result = subprocess.run(
                ["epubcheck", epub_path], capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                logger.info(f"EPUB validation passed: {epub_path}")
                return True
            else:
                logger.warning(f"EPUB validation failed: {result.stderr}")
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.debug("epubcheck not available or timed out, skipping validation")
            return True
        except Exception as e:
            logger.error(f"Error during EPUB validation: {e}")
            return True  # Don't fail the process due to validation errors

    def get_pandoc_version(self) -> Optional[str]:
        """
        Get Pandoc version string.

        Returns:
            Pandoc version or None if not available
        """
        try:
            result = subprocess.run(
                ["pandoc", "--version"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                # Extract version from first line
                first_line = result.stdout.split("\n")[0]
                return first_line.strip()

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def _generate_epub_with_ebooklib(
        self,
        markdown_file: str,
        output_dir: Path,
        novel_title: str,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate EPUB using EbookLib as fallback.

        Args:
            markdown_file: Path to markdown file
            output_dir: Directory to save EPUB file
            novel_title: Title of the novel
            css_file: Optional custom CSS file
            metadata: Optional novel metadata for EPUB

        Returns:
            Path to generated EPUB file or None if failed
        """
        try:
            from .ebooklib_epub_generator import EbookLibEPUBGenerator

            ebooklib_generator = EbookLibEPUBGenerator(self.config, silent=self.silent)
            return ebooklib_generator.generate_epub(
                markdown_file, output_dir, novel_title, css_file, metadata
            )
        except Exception as e:
            logger.error(f"EbookLib fallback failed: {e}")
            return None

    def _generate_epub_with_ebooklib_progress(
        self,
        markdown_file: str,
        output_dir: Path,
        novel_title: str,
        css_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
    ) -> Optional[str]:
        """
        Generate EPUB using EbookLib with progress tracking.

        Args:
            markdown_file: Path to markdown file
            output_dir: Directory to save EPUB file
            novel_title: Title of the novel
            css_file: Optional custom CSS file
            metadata: Optional novel metadata for EPUB
            progress_callback: Optional callback for progress updates

        Returns:
            Path to generated EPUB file or None if failed
        """
        try:
            from .ebooklib_epub_generator import EbookLibEPUBGenerator

            ebooklib_generator = EbookLibEPUBGenerator(self.config, silent=self.silent)
            return ebooklib_generator.generate_epub_with_progress(
                markdown_file,
                output_dir,
                novel_title,
                progress_callback,
                css_file,
                metadata,
            )
        except Exception as e:
            logger.error(f"EbookLib fallback with progress failed: {e}")
            if progress_callback:
                progress_callback(f"EbookLib fallback failed: {e}")
            return None
