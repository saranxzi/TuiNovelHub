"""
Main processing module for web novel scraping.

This module orchestrates the entire scraping workflow with concurrent processing.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..config import get_config, get_provider_config
from ..providers import get_scraper_for_url
from ..utils import create_safe_directory
from .base_scraper import BaseNovelScraper
from .epub_generator import EPUBGenerator
from .image_processor import ImageProcessor
from .markdown_generator import MarkdownGenerator
from .models import ChapterData, NovelMetadata, ScrapingProgress, ScrapingStatus
from .novel_database_service import NovelDatabaseService
from .user_config import get_user_preferences

logger = logging.getLogger(__name__)


class NovelProcessor:
    """
    Main processor for web novel scraping operations.

    Orchestrates the entire workflow from URL to EPUB with concurrent processing.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the novel processor.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or get_config()
        self.max_workers = self.config.get("processing", {}).get("max_workers", 10)
        self.chunk_size = self.config.get("processing", {}).get("chunk_size", 50)

        # Initialize processors
        self.image_processor = ImageProcessor(self.config)
        self.markdown_generator = MarkdownGenerator(self.config)
        self.epub_generator = EPUBGenerator(self.config)

        # Progress tracking
        self.progress: Optional[ScrapingProgress] = None
        self.progress_callbacks: List[Callable[[ScrapingProgress], None]] = []

        # Initialize database service if enabled
        self.user_preferences = get_user_preferences()
        self.db_service = None
        if self.user_preferences.enable_database:
            try:
                self.db_service = NovelDatabaseService(
                    self.user_preferences.database_path
                )
                logger.info("Database service initialized for persistent storage")
            except Exception as e:
                logger.warning(f"Failed to initialize database service: {e}")
                self.db_service = None

        logger.info(f"NovelProcessor initialized with max_workers: {self.max_workers}")

    async def process_novel_enhanced(
        self,
        novel_url: str,
        output_dir: Optional[str] = None,
        formats: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[ScrapingProgress], None]] = None,
        save_individual_chapters: bool = True,
        resume_existing: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a novel with enhanced chapter-by-chapter processing.

        Args:
            novel_url: URL of the novel to process
            output_dir: Output directory (uses config default if not provided)
            formats: List of output formats ['markdown', 'epub']
            progress_callback: Optional callback for progress updates
            save_individual_chapters: Save each chapter as individual file
            resume_existing: Skip chapters that already exist

        Returns:
            Dictionary with processing results
        """
        start_time = time.time()

        # Set up parameters
        if output_dir is None:
            output_dir = self.config.get("output", {}).get("directory", "./output")

        if formats is None:
            formats = self.config.get("output", {}).get("formats", ["markdown", "epub"])

        if progress_callback:
            self.add_progress_callback(progress_callback)

        output_path = Path(output_dir)

        try:
            # Step 1: Get scraper for URL
            logger.info(f"Starting enhanced novel processing: {novel_url}")
            scraper = await self._get_scraper(novel_url)
            if not scraper:
                return {"success": False, "error": "No suitable scraper found for URL"}

            # Step 2: Extract metadata
            logger.info("Extracting novel metadata...")
            async with scraper:
                metadata = await scraper.get_novel_metadata(novel_url)
                if not metadata:
                    return {
                        "success": False,
                        "error": "Failed to extract novel metadata",
                    }

                # Step 3: Get chapter list
                logger.info("Getting chapter list...")
                chapter_list = await scraper.get_chapter_list(novel_url)
                if not chapter_list:
                    return {"success": False, "error": "No chapters found"}

                # Step 4: Create novel-specific output directory
                novel_dir = output_path / self._sanitize_filename(metadata.title)
                if not create_safe_directory(novel_dir):
                    return {
                        "success": False,
                        "error": f"Failed to create directory: {novel_dir}",
                    }

                # Step 4.5: Save/update novel in database
                if self.db_service:
                    try:
                        novel_record = self.db_service.create_or_update_novel(
                            metadata, str(novel_dir)
                        )
                        self.db_service.mark_scraping_started(metadata.source_url)
                        logger.info(
                            f"Novel record created/updated in database: {metadata.title}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save novel to database: {e}")

                # Step 5: Check for existing chapters if resuming
                existing_chapters = []
                if resume_existing and save_individual_chapters:
                    existing_chapters = (
                        self.markdown_generator.get_existing_chapter_files(novel_dir)
                    )
                    if existing_chapters:
                        logger.info(
                            f"Found {len(existing_chapters)} existing chapter files"
                        )

                # Initialize progress tracking
                self.progress = ScrapingProgress(
                    novel_url=novel_url,
                    total_chapters=len(chapter_list),
                    output_directory=str(output_path),
                )
                self.progress.completed_chapters = len(existing_chapters)

                # Store novel URL for database updates
                self._current_novel_url = novel_url
                self.progress.start_scraping()
                self._notify_progress()

                # Step 6: Download cover image
                cover_path = None
                if self.config.get("images", {}).get("download_covers", True):
                    logger.info("Processing cover image...")
                    cover_path = await self.image_processor.download_and_process_cover(
                        metadata.cover_url or "", novel_dir, metadata.title
                    )

                # Step 7: Process chapters with enhanced logic
                if save_individual_chapters:
                    logger.info("Processing chapters individually...")
                    await self._process_chapters_individually(
                        scraper, chapter_list, novel_dir, existing_chapters
                    )
                else:
                    logger.info("Processing chapters in memory...")
                    chapters = await self._scrape_chapters_concurrent(
                        scraper, chapter_list
                    )
                    if not chapters:
                        return {
                            "success": False,
                            "error": "Failed to scrape any chapters",
                        }

                # Step 8: Generate output files
                generated_files = []

                if "markdown" in formats:
                    logger.info("Generating markdown...")
                    if save_individual_chapters:
                        # Compile from individual chapter files
                        markdown_path = (
                            self.markdown_generator.compile_from_individual_chapters(
                                metadata, novel_dir, cover_path
                            )
                        )
                    else:
                        # Use traditional method
                        markdown_path = self.markdown_generator.generate_markdown(
                            metadata, chapters, novel_dir, cover_path
                        )

                    if markdown_path:
                        generated_files.append(markdown_path)

                if "epub" in formats:
                    logger.info("Generating EPUB...")
                    if generated_files and generated_files[-1].endswith(".md"):
                        # Prepare metadata for EPUB
                        epub_metadata = {
                            "title": metadata.title,
                            "author": metadata.author,
                            "description": metadata.description,
                            "source_url": metadata.source_url,
                            "genres": metadata.genres,
                            "tags": metadata.tags,
                            "publication_date": metadata.publication_date,
                            "language": getattr(metadata, "language", "en"),
                            "cover_path": cover_path,
                        }

                        # Create progress callback for EPUB generation
                        def epub_progress_callback(message: str, step: int = None):
                            if self.progress_callbacks:
                                # Update progress with EPUB generation status
                                temp_progress = self.progress
                                temp_progress.last_update = time.time()
                                for callback in self.progress_callbacks:
                                    try:
                                        callback(temp_progress)
                                    except Exception as e:
                                        logger.error(f"Error in progress callback: {e}")
                            logger.info(f"EPUB: {message}")

                        epub_path = self.epub_generator.generate_epub_with_progress(
                            generated_files[-1],
                            novel_dir,
                            metadata.title,
                            metadata=epub_metadata,
                            progress_callback=epub_progress_callback,
                        )
                        if epub_path:
                            generated_files.append(epub_path)

                # Complete processing
                self.progress.generated_files = generated_files
                self.progress.complete_scraping()
                self._notify_progress()

                processing_time = time.time() - start_time

                result = {
                    "success": True,
                    "novel_title": metadata.title,
                    "author": metadata.author,
                    "total_chapters": len(chapter_list),
                    "successful_chapters": self.progress.completed_chapters,
                    "failed_chapters": len(self.progress.failed_chapters),
                    "generated_files": generated_files,
                    "output_directory": str(novel_dir),
                    "processing_time": processing_time,
                    "cover_image": cover_path,
                    "enhanced_processing": True,
                    "individual_chapters": save_individual_chapters,
                }

                # Update database with completion status
                if self.db_service:
                    try:
                        self.db_service.mark_scraping_completed(metadata.source_url)
                        # Update file paths using actual generated file paths
                        markdown_path = None
                        epub_path = None

                        # Extract actual file paths from generated_files list
                        for file_path in generated_files:
                            file_path_obj = Path(file_path)
                            if file_path_obj.suffix == ".md":
                                markdown_path = file_path
                            elif file_path_obj.suffix == ".epub":
                                epub_path = file_path

                        self.db_service.update_file_paths(
                            metadata.source_url,
                            markdown_path=markdown_path,
                            epub_path=epub_path,
                            cover_path=cover_path,
                        )
                        logger.info(
                            "Database updated with completion status and file paths"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to update database with completion status: {e}"
                        )

                logger.info(
                    f"Enhanced novel processing completed successfully in {processing_time:.1f}s"
                )
                return result

        except Exception as e:
            logger.error(f"Error during enhanced novel processing: {e}")
            if self.progress:
                self.progress.fail_scraping(str(e))
                self._notify_progress()

            # Update database with failure status
            if self.db_service and "metadata" in locals():
                try:
                    self.db_service.mark_scraping_failed(metadata.source_url, str(e))
                    logger.info("Database updated with failure status")
                except Exception as db_error:
                    logger.warning(
                        f"Failed to update database with failure status: {db_error}"
                    )

            return {"success": False, "error": str(e)}

        finally:
            # Cleanup
            self.image_processor.close()

    async def process_novel(
        self,
        novel_url: str,
        output_dir: Optional[str] = None,
        formats: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[ScrapingProgress], None]] = None,
    ) -> Dict[str, Any]:
        """
        Process a complete novel from URL to output files.

        Args:
            novel_url: URL of the novel to process
            output_dir: Output directory (uses config default if not provided)
            formats: List of output formats ['markdown', 'epub']
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with processing results
        """
        start_time = time.time()

        # Set up parameters
        if output_dir is None:
            output_dir = self.config.get("output", {}).get("directory", "./output")

        if formats is None:
            formats = self.config.get("output", {}).get("formats", ["markdown", "epub"])

        if progress_callback:
            self.add_progress_callback(progress_callback)

        output_path = Path(output_dir)

        try:
            # Step 1: Get scraper for URL
            logger.info(f"Starting novel processing: {novel_url}")
            scraper = await self._get_scraper(novel_url)
            if not scraper:
                return {"success": False, "error": "No suitable scraper found for URL"}

            # Step 2: Extract metadata
            logger.info("Extracting novel metadata...")
            async with scraper:
                metadata = await scraper.get_novel_metadata(novel_url)
                if not metadata:
                    return {
                        "success": False,
                        "error": "Failed to extract novel metadata",
                    }

                # Step 3: Get chapter list
                logger.info("Getting chapter list...")
                chapter_list = await scraper.get_chapter_list(novel_url)
                if not chapter_list:
                    return {"success": False, "error": "No chapters found"}

                # Initialize progress tracking
                self.progress = ScrapingProgress(
                    novel_url=novel_url,
                    total_chapters=len(chapter_list),
                    output_directory=str(output_path),
                )
                self.progress.start_scraping()
                self._notify_progress()

                # Step 4: Create novel-specific output directory
                novel_dir = output_path / self._sanitize_filename(metadata.title)
                if not create_safe_directory(novel_dir):
                    return {
                        "success": False,
                        "error": f"Failed to create directory: {novel_dir}",
                    }

                # Step 4.5: Save/update novel in database
                if self.db_service:
                    try:
                        novel_record = self.db_service.create_or_update_novel(
                            metadata, str(novel_dir)
                        )
                        self.db_service.mark_scraping_started(metadata.source_url)
                        logger.info(
                            f"Novel record created/updated in database: {metadata.title}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save novel to database: {e}")

                # Step 5: Download cover image
                cover_path = None
                if self.config.get("images", {}).get("download_covers", True):
                    logger.info("Processing cover image...")
                    cover_path = await self.image_processor.download_and_process_cover(
                        metadata.cover_url or "", novel_dir, metadata.title
                    )

                # Step 6: Scrape chapters concurrently
                logger.info(f"Scraping {len(chapter_list)} chapters...")
                chapters = await self._scrape_chapters_concurrent(scraper, chapter_list)

                if not chapters:
                    return {"success": False, "error": "Failed to scrape any chapters"}

                # Step 7: Generate output files
                generated_files = []

                if "markdown" in formats:
                    logger.info("Generating markdown...")
                    markdown_path = self.markdown_generator.generate_markdown(
                        metadata, chapters, novel_dir, cover_path
                    )
                    if markdown_path:
                        generated_files.append(markdown_path)

                if "epub" in formats:
                    logger.info("Generating EPUB...")
                    if generated_files and generated_files[-1].endswith(".md"):
                        # Prepare metadata for EPUB
                        epub_metadata = {
                            "title": metadata.title,
                            "author": metadata.author,
                            "description": metadata.description,
                            "source_url": metadata.source_url,
                            "genres": metadata.genres,
                            "tags": metadata.tags,
                            "publication_date": metadata.publication_date,
                            "language": getattr(metadata, "language", "en"),
                            "cover_path": cover_path,
                        }

                        epub_path = self.epub_generator.generate_epub(
                            generated_files[-1],
                            novel_dir,
                            metadata.title,
                            metadata=epub_metadata,
                        )
                        if epub_path:
                            generated_files.append(epub_path)

                # Complete processing
                self.progress.generated_files = generated_files
                self.progress.complete_scraping()
                self._notify_progress()

                # Update database with completion status
                if self.db_service:
                    try:
                        self.db_service.mark_scraping_completed(metadata.source_url)
                        # Update file paths using actual generated file paths
                        markdown_path = None
                        epub_path = None

                        # Extract actual file paths from generated_files list
                        for file_path in generated_files:
                            file_path_obj = Path(file_path)
                            if file_path_obj.suffix == ".md":
                                markdown_path = file_path
                            elif file_path_obj.suffix == ".epub":
                                epub_path = file_path

                        self.db_service.update_file_paths(
                            metadata.source_url,
                            markdown_path=markdown_path,
                            epub_path=epub_path,
                            cover_path=cover_path,
                        )
                        logger.info(
                            "Database updated with completion status and file paths"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to update database with completion status: {e}"
                        )

                # Calculate statistics
                stats = self.markdown_generator.generate_statistics(chapters)

                processing_time = time.time() - start_time

                result = {
                    "success": True,
                    "novel_title": metadata.title,
                    "author": metadata.author,
                    "total_chapters": len(chapters),
                    "successful_chapters": len([c for c in chapters if c]),
                    "failed_chapters": len(self.progress.failed_chapters),
                    "generated_files": generated_files,
                    "output_directory": str(novel_dir),
                    "processing_time": processing_time,
                    "statistics": stats,
                    "cover_image": cover_path,
                }

                logger.info(
                    f"Novel processing completed successfully in {processing_time:.1f}s"
                )
                return result

        except Exception as e:
            logger.error(f"Error during novel processing: {e}")
            if self.progress:
                self.progress.fail_scraping(str(e))
                self._notify_progress()
            return {"success": False, "error": str(e)}

        finally:
            # Cleanup
            self.image_processor.close()

    async def _get_scraper(self, novel_url: str) -> Optional[BaseNovelScraper]:
        """Get appropriate scraper for URL."""
        try:
            # Detect provider from URL
            from ..providers import registry

            provider_name = registry.get_provider_for_url(novel_url)

            if not provider_name:
                logger.error(f"No provider found for URL: {novel_url}")
                return None

            # Load provider configuration
            provider_config = get_provider_config(provider_name)

            # Get cache configuration from user preferences
            cache_config = None
            if hasattr(self.user_preferences, "get_cache_config"):
                cache_config = self.user_preferences.get_cache_config()
                logger.debug(
                    f"Cache configuration loaded: enabled={cache_config.enabled}"
                )

            # Create scraper with cache configuration
            scraper = get_scraper_for_url(novel_url, provider_config, cache_config)

            if not scraper:
                logger.error(f"Failed to create scraper for provider: {provider_name}")
                return None

            logger.info(f"Using provider: {provider_name}")
            return scraper

        except Exception as e:
            logger.error(f"Error getting scraper: {e}")
            return None

    async def _scrape_chapters_concurrent(
        self, scraper: BaseNovelScraper, chapter_list: List[Dict[str, str]]
    ) -> List[ChapterData]:
        """
        Scrape chapters concurrently with rate limiting.

        Args:
            scraper: Scraper instance
            chapter_list: List of chapter information

        Returns:
            List of scraped chapter data
        """
        chapters = []

        # Use provider-specific settings if available
        max_workers = getattr(
            scraper, "get_max_concurrent_requests", lambda: self.max_workers
        )()
        chunk_size = getattr(scraper, "get_chunk_size", lambda: self.chunk_size)()
        delay_between_chunks = getattr(
            scraper, "get_delay_between_chunks", lambda: 1.0
        )()

        logger.info(
            f"Using provider-specific settings: max_workers={max_workers}, chunk_size={chunk_size}, delay={delay_between_chunks}s"
        )

        semaphore = asyncio.Semaphore(max_workers)

        async def scrape_single_chapter(
            chapter_info: Dict[str, str],
        ) -> Optional[ChapterData]:
            async with semaphore:
                try:
                    chapter_data = await scraper.scrape_chapter_content(
                        chapter_info["url"]
                    )
                    if chapter_data:
                        self.progress.complete_chapter()
                        logger.debug(f"Scraped chapter: {chapter_data.title}")
                    else:
                        self.progress.fail_chapter(
                            chapter_info["url"], "Failed to extract content"
                        )
                        logger.warning(
                            f"Failed to scrape chapter: {chapter_info['url']}"
                        )

                    self._notify_progress()
                    return chapter_data

                except Exception as e:
                    error_msg = f"Error scraping chapter {chapter_info['url']}: {e}"
                    self.progress.fail_chapter(chapter_info["url"], error_msg)
                    logger.error(error_msg)
                    self._notify_progress()
                    return None

        # Process chapters in chunks to manage memory
        for i in range(0, len(chapter_list), chunk_size):
            chunk = chapter_list[i : i + chunk_size]
            logger.info(
                f"Processing chunk {i//chunk_size + 1}/{(len(chapter_list) + chunk_size - 1)//chunk_size}"
            )

            # Create tasks for this chunk
            tasks = [scrape_single_chapter(chapter_info) for chapter_info in chunk]

            # Wait for chunk completion
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in chunk_results:
                if isinstance(result, ChapterData):
                    chapters.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Chapter scraping exception: {result}")

            # Add delay between chunks (except for the last chunk)
            if i + chunk_size < len(chapter_list):
                logger.debug(f"Waiting {delay_between_chunks}s before next chunk...")
                await asyncio.sleep(delay_between_chunks)

        # Filter out None values and sort by chapter number
        valid_chapters = [ch for ch in chapters if ch is not None]
        valid_chapters.sort(key=lambda x: x.chapter_number or 0)

        logger.info(
            f"Successfully scraped {len(valid_chapters)}/{len(chapter_list)} chapters"
        )
        return valid_chapters

    async def _process_chapters_individually(
        self,
        scraper: BaseNovelScraper,
        chapter_list: List[Dict[str, str]],
        novel_dir: Path,
        existing_chapters: List[int],
    ) -> None:
        """
        Process chapters individually, saving each as a separate file.

        Args:
            scraper: Scraper instance
            chapter_list: List of chapter information
            novel_dir: Novel output directory
            existing_chapters: List of existing chapter sequence numbers
        """
        # Use provider-specific settings if available
        max_workers = getattr(
            scraper, "get_max_concurrent_requests", lambda: self.max_workers
        )()
        chunk_size = getattr(scraper, "get_chunk_size", lambda: self.chunk_size)()
        delay_between_chunks = getattr(
            scraper, "get_delay_between_chunks", lambda: 1.0
        )()

        logger.info(
            f"Individual processing with: max_workers={max_workers}, chunk_size={chunk_size}, delay={delay_between_chunks}s"
        )

        semaphore = asyncio.Semaphore(max_workers)

        async def process_single_chapter(
            chapter_info: Dict[str, str], sequence_number: int
        ) -> None:
            async with semaphore:
                try:
                    # Skip if chapter already exists
                    if sequence_number in existing_chapters:
                        logger.debug(f"Skipping existing chapter {sequence_number}")
                        return

                    # Scrape chapter content
                    chapter_data = await scraper.scrape_chapter_content(
                        chapter_info["url"]
                    )

                    if chapter_data:
                        # Save individual chapter file
                        chapter_path = self.markdown_generator.save_individual_chapter(
                            chapter_data, novel_dir, sequence_number
                        )

                        if chapter_path:
                            self.progress.complete_chapter()
                            logger.debug(
                                f"Saved chapter {sequence_number}: {chapter_data.title}"
                            )

                            # Update database progress
                            if self.db_service and hasattr(self, "_current_novel_url"):
                                try:
                                    self.db_service.update_novel_by_url(
                                        self._current_novel_url,
                                        completed_chapters=self.progress.completed_chapters,
                                        last_chapter_scraped=sequence_number,
                                    )
                                except Exception:
                                    # Don't fail the whole process for database update errors
                                    pass
                        else:
                            self.progress.fail_chapter(
                                chapter_info["url"], "Failed to save chapter file"
                            )
                            logger.warning(
                                f"Failed to save chapter {sequence_number}: {chapter_info['url']}"
                            )
                    else:
                        self.progress.fail_chapter(
                            chapter_info["url"], "Failed to extract content"
                        )
                        logger.warning(
                            f"Failed to scrape chapter {sequence_number}: {chapter_info['url']}"
                        )

                    self._notify_progress()

                except Exception as e:
                    error_msg = f"Error processing chapter {sequence_number} {chapter_info['url']}: {e}"
                    self.progress.fail_chapter(chapter_info["url"], error_msg)
                    logger.error(error_msg)
                    self._notify_progress()

        # Process chapters in chunks to manage memory and connections
        for i in range(0, len(chapter_list), chunk_size):
            chunk = chapter_list[i : i + chunk_size]
            logger.info(
                f"Processing chunk {i//chunk_size + 1}/{(len(chapter_list) + chunk_size - 1)//chunk_size}"
            )

            # Create tasks for this chunk
            tasks = [
                process_single_chapter(chapter_info, i + j + 1)
                for j, chapter_info in enumerate(chunk)
            ]

            # Wait for chunk completion
            await asyncio.gather(*tasks, return_exceptions=True)

            # Save progress after each chunk
            if self.progress and hasattr(self, "_current_novel_url"):
                progress_file = (
                    novel_dir
                    / f".progress_{self._sanitize_filename(self._current_novel_url)}.json"
                )
                try:
                    self.save_progress(str(progress_file))
                    logger.debug(f"Progress saved after chunk {i//chunk_size + 1}")
                except Exception as e:
                    logger.warning(f"Failed to save progress: {e}")

            # Provider-specific delay between chunks
            if i + chunk_size < len(chapter_list):
                logger.debug(f"Waiting {delay_between_chunks}s before next chunk...")
                await asyncio.sleep(delay_between_chunks)

    def add_progress_callback(
        self, callback: Callable[[ScrapingProgress], None]
    ) -> None:
        """Add a progress callback function."""
        self.progress_callbacks.append(callback)

    def remove_progress_callback(
        self, callback: Callable[[ScrapingProgress], None]
    ) -> None:
        """Remove a progress callback function."""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)

    def _notify_progress(self) -> None:
        """Notify all progress callbacks."""
        if self.progress:
            for callback in self.progress_callbacks:
                try:
                    callback(self.progress)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for directory creation."""
        from ..utils import clean_filename

        return clean_filename(filename)

    async def resume_processing(self, progress_file: str) -> Dict[str, Any]:
        """
        Resume processing from a saved progress file.

        Args:
            progress_file: Path to progress file

        Returns:
            Processing results
        """
        try:
            import json
            from datetime import datetime

            # Load progress data
            progress_path = Path(progress_file)
            if not progress_path.exists():
                return {
                    "success": False,
                    "error": f"Progress file not found: {progress_file}",
                }

            with open(progress_path, "r", encoding="utf-8") as f:
                progress_data = json.load(f)

            # Validate required fields
            required_fields = ["novel_url", "total_chapters", "output_directory"]
            for field in required_fields:
                if field not in progress_data:
                    return {
                        "success": False,
                        "error": f"Invalid progress file: missing {field}",
                    }

            # Restore processor configuration
            if "processor_config" in progress_data:
                config = progress_data["processor_config"]
                self.max_workers = config.get("max_workers", self.max_workers)
                self.chunk_size = config.get("chunk_size", self.chunk_size)

            # Reconstruct progress object
            self.progress = ScrapingProgress(
                novel_url=progress_data["novel_url"],
                total_chapters=progress_data["total_chapters"],
                output_directory=progress_data["output_directory"],
            )

            # Restore progress state
            self.progress.completed_chapters = progress_data.get(
                "completed_chapters", 0
            )
            self.progress.failed_chapters = progress_data.get("failed_chapters", [])
            self.progress.skipped_chapters = progress_data.get("skipped_chapters", [])
            self.progress.error_count = progress_data.get("error_count", 0)
            self.progress.last_error = progress_data.get("last_error")
            self.progress.retry_count = progress_data.get("retry_count", 0)
            self.progress.generated_files = progress_data.get("generated_files", [])

            # Restore timestamps
            if progress_data.get("start_time"):
                self.progress.start_time = datetime.fromisoformat(
                    progress_data["start_time"]
                )
            if progress_data.get("end_time"):
                self.progress.end_time = datetime.fromisoformat(
                    progress_data["end_time"]
                )
            if progress_data.get("last_update"):
                self.progress.last_update = datetime.fromisoformat(
                    progress_data["last_update"]
                )
            if progress_data.get("estimated_completion"):
                self.progress.estimated_completion = datetime.fromisoformat(
                    progress_data["estimated_completion"]
                )

            self.progress.chapters_per_minute = progress_data.get("chapters_per_minute")

            # Set status to resuming
            self.progress.status = ScrapingStatus.IN_PROGRESS
            self.progress.last_update = datetime.now()

            logger.info(
                f"Resuming from progress: {self.progress.completed_chapters}/{self.progress.total_chapters} chapters completed"
            )

            # Resume processing with the loaded state
            return await self._resume_processing_async()

        except Exception as e:
            logger.error(f"Failed to resume from progress: {e}")
            return {"success": False, "error": f"Failed to resume: {str(e)}"}

    def save_progress(self, progress_file: str) -> bool:
        """
        Save current progress to file.

        Args:
            progress_file: Path to save progress

        Returns:
            True if saved successfully
        """
        if not self.progress:
            logger.warning("No progress data to save")
            return False

        try:
            import json
            from datetime import datetime

            # Convert progress to serializable format
            progress_data = {
                "novel_url": self.progress.novel_url,
                "total_chapters": self.progress.total_chapters,
                "completed_chapters": self.progress.completed_chapters,
                "failed_chapters": self.progress.failed_chapters,
                "skipped_chapters": self.progress.skipped_chapters,
                "status": self.progress.status.value,
                "start_time": (
                    self.progress.start_time.isoformat()
                    if self.progress.start_time
                    else None
                ),
                "end_time": (
                    self.progress.end_time.isoformat()
                    if self.progress.end_time
                    else None
                ),
                "last_update": self.progress.last_update.isoformat(),
                "estimated_completion": (
                    self.progress.estimated_completion.isoformat()
                    if self.progress.estimated_completion
                    else None
                ),
                "chapters_per_minute": self.progress.chapters_per_minute,
                "error_count": self.progress.error_count,
                "last_error": self.progress.last_error,
                "retry_count": self.progress.retry_count,
                "output_directory": self.progress.output_directory,
                "generated_files": self.progress.generated_files,
                "saved_at": datetime.now().isoformat(),
                "processor_config": {
                    "max_workers": self.max_workers,
                    "chunk_size": self.chunk_size,
                },
            }

            # Save to file
            progress_path = Path(progress_file)
            progress_path.parent.mkdir(parents=True, exist_ok=True)

            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Progress saved to: {progress_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
            return False

    async def _resume_processing_async(self) -> Dict[str, Any]:
        """
        Internal method to handle the actual resume processing logic.

        Returns:
            Processing results
        """
        try:
            # Get scraper for the novel URL
            scraper = await self._get_scraper(self.progress.novel_url)
            if not scraper:
                return {"success": False, "error": "No suitable scraper found for URL"}

            async with scraper:
                # Get fresh metadata and chapter list
                logger.info("Refreshing novel metadata and chapter list...")
                metadata = await scraper.get_novel_metadata(self.progress.novel_url)
                if not metadata:
                    return {
                        "success": False,
                        "error": "Failed to refresh novel metadata",
                    }

                chapter_list = await scraper.get_chapter_list(self.progress.novel_url)
                if not chapter_list:
                    return {"success": False, "error": "No chapters found"}

                # Update total chapters if it has changed
                if len(chapter_list) != self.progress.total_chapters:
                    logger.info(
                        f"Chapter count changed: {self.progress.total_chapters} -> {len(chapter_list)}"
                    )
                    self.progress.total_chapters = len(chapter_list)

                # Determine output directory
                output_path = Path(self.progress.output_directory)
                novel_dir = output_path / self._sanitize_filename(metadata.title)

                # Check existing chapters to determine what needs to be processed
                existing_chapters = self.markdown_generator.get_existing_chapter_files(
                    novel_dir
                )

                # Filter out chapters that are already completed
                remaining_chapters = []
                for i, chapter in enumerate(chapter_list):
                    chapter_filename = f"chapter_{i+1:04d}.md"
                    if chapter_filename not in existing_chapters:
                        remaining_chapters.append(chapter)

                logger.info(
                    f"Found {len(existing_chapters)} existing chapters, {len(remaining_chapters)} remaining to process"
                )

                # Update progress with current state
                self.progress.completed_chapters = len(existing_chapters)
                self._notify_progress()

                # Continue processing remaining chapters
                if remaining_chapters:
                    await self._process_chapters_individually(
                        scraper, remaining_chapters, novel_dir, existing_chapters
                    )

                # Generate final output files
                logger.info("Generating final output files...")
                generated_files = []

                # Generate markdown
                markdown_path = (
                    self.markdown_generator.compile_from_individual_chapters(
                        metadata, novel_dir, None  # Cover path can be None for resume
                    )
                )
                if markdown_path:
                    generated_files.append(markdown_path)
                    self.progress.generated_files = generated_files

                # Mark as completed
                self.progress.complete_scraping()
                self._notify_progress()

                # Update database if available
                if self.db_service:
                    try:
                        self.db_service.mark_scraping_completed(self.progress.novel_url)

                        # Update file paths using actual generated file paths
                        markdown_path = None
                        epub_path = None

                        # Extract actual file paths from generated_files list
                        for file_path in generated_files:
                            file_path_obj = Path(file_path)
                            if file_path_obj.suffix == ".md":
                                markdown_path = file_path
                            elif file_path_obj.suffix == ".epub":
                                epub_path = file_path

                        self.db_service.update_file_paths(
                            self.progress.novel_url,
                            markdown_path=markdown_path,
                            epub_path=epub_path,
                        )
                        logger.info(
                            "Updated database with completion status and file paths"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update database: {e}")

                return {
                    "success": True,
                    "message": "Resume processing completed successfully",
                    "generated_files": generated_files,
                    "total_chapters": self.progress.total_chapters,
                    "completed_chapters": self.progress.completed_chapters,
                    "failed_chapters": len(self.progress.failed_chapters),
                }

        except Exception as e:
            logger.error(f"Error during resume processing: {e}")
            if self.progress:
                self.progress.fail_scraping(str(e))
                self._notify_progress()
            return {"success": False, "error": f"Resume processing failed: {str(e)}"}
