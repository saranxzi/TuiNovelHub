"""
Novel Discovery Service for finding and managing scraped novels.

This module provides functionality to scan output directories and identify
scraped novels, extract their metadata, and manage novel collections.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import NovelMetadata
from .novel_database_service import NovelDatabaseService
from .user_config import get_user_preferences


@dataclass
class NovelInfo:
    """Information about a discovered novel."""

    # Basic information
    title: str
    author: str
    directory: Path
    markdown_file: Path

    # File information
    markdown_size: int
    epub_file: Optional[Path] = None
    epub_size: Optional[int] = None
    cover_file: Optional[Path] = None

    # Metadata
    description: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    status: Optional[str] = None
    chapter_count: Optional[int] = None

    # Timestamps
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    epub_created_at: Optional[datetime] = None

    # Status flags
    has_epub: bool = False
    is_complete: bool = False
    has_cover: bool = False


class NovelDiscoveryService:
    """Service for discovering and managing scraped novels."""

    def __init__(self, output_directory: Optional[str] = None):
        """
        Initialize the novel discovery service.

        Args:
            output_directory: Base output directory to scan for novels
        """
        self.output_directory = (
            Path(output_directory) if output_directory else Path.cwd()
        )

        # Initialize database service if enabled
        self.user_preferences = get_user_preferences()
        self.db_service = None
        if self.user_preferences.enable_database:
            try:
                self.db_service = NovelDatabaseService(
                    self.user_preferences.database_path
                )
            except Exception as e:
                # Fallback to filesystem-only mode
                self.db_service = None

    def discover_novels(
        self, directory: Optional[Path] = None, progress_callback=None
    ) -> List[NovelInfo]:
        """
        Discover all novels using database as primary source with filesystem fallback.

        Args:
            directory: Directory to scan (uses default if not provided)
            progress_callback: Optional callback function to report progress

        Returns:
            List of discovered novels
        """
        scan_dir = directory or self.output_directory

        # Try database first if available
        if self.db_service:
            try:
                if progress_callback:
                    progress_callback("Loading novels from database...")
                return self._discover_novels_from_database(scan_dir)
            except Exception:
                # Fallback to filesystem scan
                if progress_callback:
                    progress_callback("Database unavailable, scanning filesystem...")

        # Fallback to filesystem scan
        return self._discover_novels_from_filesystem(scan_dir, progress_callback)

    def _discover_novels_from_database(self, scan_dir: Path) -> List[NovelInfo]:
        """
        Discover novels from database records.

        Args:
            scan_dir: Directory to filter by (optional)

        Returns:
            List of discovered novels from database
        """
        novels = []

        # Get all novels from database
        novel_records = self.db_service.list_novels()

        for record in novel_records:
            # Filter by directory if specified
            if scan_dir and record.directory_path:
                record_dir = Path(record.directory_path)
                try:
                    if (
                        not record_dir.is_relative_to(scan_dir)
                        and record_dir != scan_dir
                    ):
                        continue
                except ValueError:
                    # Handle case where paths are not related
                    continue

            # Convert database record to NovelInfo
            novel_info = self._convert_record_to_novel_info(record)
            if novel_info:
                novels.append(novel_info)

        return sorted(novels, key=lambda x: x.title.lower())

    def _discover_novels_from_filesystem(
        self, scan_dir: Path, progress_callback=None
    ) -> List[NovelInfo]:
        """
        Discover novels by scanning filesystem (fallback method).

        Args:
            scan_dir: Directory to scan
            progress_callback: Optional callback function to report progress

        Returns:
            List of discovered novels from filesystem
        """
        if not scan_dir.exists() or not scan_dir.is_dir():
            return []

        novels = []

        # Get list of directories first to show progress
        directories = [
            item
            for item in scan_dir.iterdir()
            if item.is_dir() and not item.name.startswith(".")
        ]

        if progress_callback:
            progress_callback(f"Found {len(directories)} directories to scan...")

        # Scan for novel directories
        for i, item in enumerate(directories, 1):
            if progress_callback:
                progress_callback(
                    f"Scanning directory {i}/{len(directories)}: {item.name}"
                )

            novel_info = self._analyze_novel_directory(item, progress_callback)
            if novel_info:
                novels.append(novel_info)
                if progress_callback:
                    progress_callback(f"Found novel: {novel_info.title}")

        if progress_callback:
            progress_callback(f"Discovered {len(novels)} novels total")

        return sorted(novels, key=lambda x: x.title.lower())

    def find_novel_by_name(
        self, name: str, directory: Optional[Path] = None
    ) -> Optional[NovelInfo]:
        """
        Find a specific novel by name.

        Args:
            name: Novel name to search for
            directory: Directory to search in

        Returns:
            NovelInfo if found, None otherwise
        """
        novels = self.discover_novels(directory)

        # Try exact match first
        for novel in novels:
            if novel.title.lower() == name.lower():
                return novel

        # Try partial match
        for novel in novels:
            if name.lower() in novel.title.lower():
                return novel

        return None

    def get_novels_without_epub(
        self, directory: Optional[Path] = None
    ) -> List[NovelInfo]:
        """
        Get all novels that don't have EPUB files.

        Args:
            directory: Directory to scan

        Returns:
            List of novels without EPUB files
        """
        novels = self.discover_novels(directory)
        return [novel for novel in novels if not novel.has_epub]

    def get_novels_modified_after(
        self, date: datetime, directory: Optional[Path] = None
    ) -> List[NovelInfo]:
        """
        Get novels modified after a specific date.

        Args:
            date: Cutoff date
            directory: Directory to scan

        Returns:
            List of novels modified after the date
        """
        novels = self.discover_novels(directory)
        return [
            novel for novel in novels if novel.modified_at and novel.modified_at > date
        ]

    def _analyze_novel_directory(
        self, directory: Path, progress_callback=None
    ) -> Optional[NovelInfo]:
        """
        Analyze a directory to determine if it contains a novel.

        Args:
            directory: Directory to analyze
            progress_callback: Optional callback function to report progress

        Returns:
            NovelInfo if valid novel directory, None otherwise
        """
        # Look for markdown files
        markdown_files = list(directory.glob("*.md"))
        if not markdown_files:
            return None

        # Use the first markdown file found (typically novel.md)
        markdown_file = markdown_files[0]

        if progress_callback:
            progress_callback(f"Reading markdown file: {markdown_file.name}")

        # Extract metadata from markdown file
        metadata = self._extract_metadata_from_markdown(markdown_file)
        if not metadata:
            return None

        # Get file information
        markdown_stat = markdown_file.stat()

        # Look for EPUB file
        if progress_callback:
            progress_callback(f"Checking for EPUB files...")
        epub_files = list(directory.glob("*.epub"))
        epub_file = epub_files[0] if epub_files else None
        epub_size = epub_file.stat().st_size if epub_file else None
        epub_created_at = (
            datetime.fromtimestamp(epub_file.stat().st_ctime) if epub_file else None
        )

        # Look for cover image
        if progress_callback:
            progress_callback(f"Checking for cover images...")
        cover_patterns = ["cover.*", "*.jpg", "*.jpeg", "*.png", "*.webp"]
        cover_file = None
        for pattern in cover_patterns:
            covers = list(directory.glob(pattern))
            if covers:
                cover_file = covers[0]
                break

        return NovelInfo(
            title=metadata.get("title", directory.name),
            author=metadata.get("author", "Unknown"),
            directory=directory,
            markdown_file=markdown_file,
            markdown_size=markdown_stat.st_size,
            epub_file=epub_file,
            epub_size=epub_size,
            cover_file=cover_file,
            description=metadata.get("description"),
            genres=metadata.get("genres", []),
            status=metadata.get("status"),
            chapter_count=metadata.get("chapter_count"),
            created_at=datetime.fromtimestamp(markdown_stat.st_ctime),
            modified_at=datetime.fromtimestamp(markdown_stat.st_mtime),
            epub_created_at=epub_created_at,
            has_epub=epub_file is not None,
            has_cover=cover_file is not None,
            is_complete=metadata.get("status", "").lower() in ["completed", "complete"],
        )

    def _extract_metadata_from_markdown(
        self, markdown_file: Path
    ) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from markdown file's YAML frontmatter.

        Args:
            markdown_file: Path to markdown file

        Returns:
            Dictionary of metadata or None if extraction failed
        """
        try:
            # Read only the first part of the file to extract YAML frontmatter
            # This avoids loading huge files entirely into memory
            with open(markdown_file, "r", encoding="utf-8") as f:
                # Read first 10KB to find YAML frontmatter
                header_content = f.read(10240)

                # Look for YAML frontmatter
                if not header_content.startswith("---"):
                    return None

                # Find the end of frontmatter in the header
                end_match = re.search(r"\n---\n", header_content)
                if not end_match:
                    # If not found in first 10KB, read a bit more
                    f.seek(0)
                    header_content = f.read(50000)  # Read up to 50KB
                    end_match = re.search(r"\n---\n", header_content)
                    if not end_match:
                        return None

                # Extract and parse YAML
                yaml_content = header_content[3 : end_match.start()]
                metadata = yaml.safe_load(yaml_content)

                if not metadata:
                    metadata = {}

                # Extract status information from content after YAML frontmatter
                content_after_yaml = header_content[end_match.end() :]
                status_info = self._extract_status_from_content(content_after_yaml)
                if status_info:
                    # Update metadata with status from content if not already present
                    if "status" not in metadata and status_info.get("status"):
                        metadata["status"] = status_info["status"]
                    if "total_chapters" not in metadata and status_info.get(
                        "total_chapters"
                    ):
                        metadata["total_chapters"] = status_info["total_chapters"]

                # For chapter counting, read the entire file to ensure accurate pattern matching
                f.seek(0)
                chapter_count = 0

                try:
                    # Read entire file content for accurate chapter counting
                    content = f.read()
                    if isinstance(content, str):
                        content_bytes = content.encode("utf-8")
                    else:
                        content_bytes = content

                    # Use patterns that match the actual chapter format in markdown files
                    # The anchor pattern {#chapter-\d+} is the most reliable indicator
                    chapter_patterns = [
                        rb"{#chapter-\d+",  # Chapter anchors (most reliable, works for all formats)
                        rb"^##.*{#chapter-\d+",  # Level 2 headers with chapter anchors
                        rb"^#.*{#chapter-\d+",  # Level 1 headers with chapter anchors
                        rb"^## Chapter \d+",  # Level 2 headers starting with "Chapter" (fallback)
                        rb"^# Chapter \d+",  # Level 1 headers starting with "Chapter" (fallback)
                    ]

                    for pattern in chapter_patterns:
                        matches = re.findall(pattern, content_bytes, re.MULTILINE)
                        count = len(matches)
                        if count > chapter_count:
                            chapter_count = count

                except MemoryError:
                    # Fallback to chunk-based reading for very large files
                    f.seek(0)
                    chunk_size = 1024 * 1024  # 1MB chunks
                    chapter_patterns = [
                        rb"^##.*{#chapter-\d+",  # Level 2 headers with chapter anchors
                        rb"^#.*{#chapter-\d+",  # Level 1 headers with chapter anchors
                        rb"^## Chapter \d+",  # Level 2 headers starting with "Chapter"
                        rb"^# Chapter \d+",  # Level 1 headers starting with "Chapter"
                    ]

                    for pattern in chapter_patterns:
                        f.seek(0)
                        count = 0
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            chunk_bytes = (
                                chunk.encode("utf-8")
                                if isinstance(chunk, str)
                                else chunk
                            )
                            matches = re.findall(pattern, chunk_bytes, re.MULTILINE)
                            count += len(matches)

                        if count > chapter_count:
                            chapter_count = count

                # Use content-extracted chapter count if available, otherwise use regex count
                if chapter_count > 0 and "total_chapters" not in metadata:
                    metadata["chapter_count"] = chapter_count
                elif "total_chapters" in metadata:
                    metadata["chapter_count"] = metadata["total_chapters"]

                # For word count, estimate based on file size to avoid reading entire file
                file_size = markdown_file.stat().st_size
                # Rough estimate: 5 characters per word average
                estimated_words = file_size // 5
                metadata["word_count"] = estimated_words

                return metadata

        except Exception:
            # Return basic metadata even if processing fails
            try:
                return {
                    "title": markdown_file.stem.replace("_", " "),
                    "author": "Unknown",
                    "word_count": markdown_file.stat().st_size // 5,
                }
            except:
                return None

    def _convert_record_to_novel_info(self, record) -> Optional[NovelInfo]:
        """
        Convert a database record to NovelInfo object.

        Args:
            record: NovelRecord from database

        Returns:
            NovelInfo object or None if conversion failed
        """
        try:
            # Don't require directory to exist - show all database records
            if not record.directory_path:
                return None

            directory_path = Path(record.directory_path)

            # Check for markdown file
            markdown_file = None
            if record.markdown_file_path:
                markdown_path = Path(record.markdown_file_path)
                if markdown_path.exists():
                    markdown_file = markdown_path
                else:
                    # Try to find markdown file in directory
                    if directory_path.exists():
                        # Look for any .md file in the directory
                        md_files = list(directory_path.glob("*.md"))
                        if md_files:
                            markdown_file = md_files[0]

            # If no markdown file found, skip this record
            if not markdown_file:
                return None

            # Check for EPUB file
            epub_file = None
            if record.epub_file_path:
                epub_path = Path(record.epub_file_path)
                if epub_path.exists():
                    epub_file = epub_path
                else:
                    # Try to find EPUB file in directory
                    if directory_path.exists():
                        epub_files = list(directory_path.glob("*.epub"))
                        if epub_files:
                            epub_file = epub_files[0]

            # Check for cover file
            cover_file = None
            if record.cover_file_path:
                cover_path = Path(record.cover_file_path)
                if cover_path.exists():
                    cover_file = cover_path
                else:
                    # Try to find cover file in directory
                    if directory_path.exists():
                        for ext in ["jpg", "jpeg", "png", "webp"]:
                            cover_files = list(directory_path.glob(f"*.{ext}"))
                            if cover_files:
                                cover_file = cover_files[0]
                                break

            # Calculate file sizes if not stored
            markdown_size = record.markdown_file_size or 0
            if markdown_file and markdown_file.exists() and not markdown_size:
                markdown_size = markdown_file.stat().st_size

            epub_size = record.epub_file_size
            if epub_file and epub_file.exists() and not epub_size:
                epub_size = epub_file.stat().st_size

            return NovelInfo(
                title=record.title or "Unknown Title",
                author=record.author or "Unknown Author",
                directory=directory_path,
                markdown_file=markdown_file,
                markdown_size=markdown_size,
                epub_file=epub_file,
                epub_size=epub_size,
                cover_file=cover_file,
                description=record.description or "",
                genres=record.genres or [],
                status=record.novel_status or "Unknown",
                chapter_count=record.total_chapters,
                created_at=record.created_at,
                modified_at=record.updated_at,
                epub_created_at=record.scraping_end_time,
                has_epub=bool(epub_file),
                is_complete=record.novel_status in ["completed", "complete"],
                has_cover=bool(cover_file),
            )
        except Exception as e:
            # Log the error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to convert record to NovelInfo: {e}")
            return None

    def _extract_status_from_content(self, content: str) -> Dict[str, Any]:
        """
        Extract status and other metadata from markdown content.

        This looks for status information that appears after YAML frontmatter
        but before the chapter listings.

        Args:
            content: Markdown content after YAML frontmatter

        Returns:
            Dictionary with extracted status information
        """
        status_info = {}

        try:
            # Look for status patterns in the first few lines after YAML
            lines = content.split("\n")[:20]  # Check first 20 lines

            for line in lines:
                line = line.strip().lower()

                # Look for status indicators
                if "status:" in line or "novel status:" in line:
                    # Extract status value
                    if ":" in line:
                        status_part = line.split(":", 1)[1].strip()
                        # Clean up common status values
                        if "complet" in status_part:
                            status_info["status"] = "completed"
                        elif "ongoing" in status_part or "progress" in status_part:
                            status_info["status"] = "ongoing"
                        elif "hiatus" in status_part or "pause" in status_part:
                            status_info["status"] = "hiatus"
                        elif "dropped" in status_part or "abandon" in status_part:
                            status_info["status"] = "dropped"
                        else:
                            status_info["status"] = status_part

                # Look for chapter count indicators
                elif "chapters:" in line or "total chapters:" in line:
                    if ":" in line:
                        chapter_part = line.split(":", 1)[1].strip()
                        # Extract number from the text
                        import re

                        numbers = re.findall(r"\d+", chapter_part)
                        if numbers:
                            status_info["total_chapters"] = int(numbers[0])

                # Look for other common patterns
                elif line.startswith("**status"):
                    # Handle **Status: Completed** format
                    if ":" in line:
                        status_part = (
                            line.split(":", 1)[1].strip().replace("*", "").lower()
                        )
                        if "complet" in status_part:
                            status_info["status"] = "completed"
                        elif "ongoing" in status_part:
                            status_info["status"] = "ongoing"

                # Stop at chapter headings
                elif line.startswith("#") and ("chapter" in line or "prologue" in line):
                    break

        except Exception as e:
            logger.debug(f"Error extracting status from content: {e}")

        return status_info
