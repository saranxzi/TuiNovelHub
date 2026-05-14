#!/usr/bin/env python3
"""
Import existing novels from filesystem to database.

This script scans a directory for existing novel files and imports them
into the database without needing to re-scrape them.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Add the src directory to the path so we can import wn_dl modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wn_dl.core.novel_database_service import NovelDatabaseService
from wn_dl.core.novel_discovery import NovelDiscoveryService
from wn_dl.core.models import NovelMetadata, NovelStatus
from wn_dl.core.user_config import get_user_preferences

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_novels_from_directory(
    directory: Path, 
    db_service: NovelDatabaseService,
    dry_run: bool = False,
    force_update: bool = False
) -> dict:
    """
    Import novels from a directory into the database.
    
    Args:
        directory: Directory to scan for novels
        db_service: Database service instance
        dry_run: If True, only show what would be imported without actually doing it
        force_update: If True, update existing records
        
    Returns:
        Dictionary with import statistics
    """
    stats = {
        "scanned": 0,
        "imported": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0
    }
    
    logger.info(f"Scanning directory: {directory}")
    
    # Use discovery service to find novels
    discovery_service = NovelDiscoveryService(str(directory))
    novels = discovery_service._discover_novels_from_filesystem(directory)
    
    stats["scanned"] = len(novels)
    logger.info(f"Found {len(novels)} novels to process")
    
    for novel in novels:
        try:
            stats["scanned"] += 1
            
            # Check if novel already exists in database
            existing_record = db_service.get_novel_by_directory(str(novel.directory))
            
            if existing_record and not force_update:
                logger.debug(f"Skipping existing novel: {novel.title}")
                stats["skipped"] += 1
                continue
            
            # Create metadata from discovered novel info
            metadata = create_metadata_from_novel_info(novel)
            
            if dry_run:
                if existing_record:
                    logger.info(f"[DRY RUN] Would update: {novel.title}")
                    stats["updated"] += 1
                else:
                    logger.info(f"[DRY RUN] Would import: {novel.title}")
                    stats["imported"] += 1
                continue
            
            if existing_record:
                # Update existing record
                db_service.update_novel(
                    existing_record.id,
                    metadata=metadata,
                    markdown_file_path=str(novel.markdown_file) if novel.markdown_file else None,
                    epub_file_path=str(novel.epub_file) if novel.epub_file else None,
                    cover_file_path=str(novel.cover_file) if novel.cover_file else None,
                    markdown_file_size=novel.markdown_size,
                    epub_file_size=novel.epub_size,
                    has_epub=novel.has_epub,
                    has_cover=novel.has_cover,
                    total_chapters=novel.chapter_count,
                )
                logger.info(f"Updated: {novel.title}")
                stats["updated"] += 1
            else:
                # Create new record
                novel_record = db_service.create_novel(metadata, str(novel.directory))
                
                # Update file paths
                db_service.update_file_paths(
                    metadata.source_url,
                    markdown_path=str(novel.markdown_file) if novel.markdown_file else None,
                    epub_path=str(novel.epub_file) if novel.epub_file else None,
                    cover_path=str(novel.cover_file) if novel.cover_file else None
                )
                
                logger.info(f"Imported: {novel.title}")
                stats["imported"] += 1
                
        except Exception as e:
            logger.error(f"Error processing {novel.title}: {e}")
            stats["errors"] += 1
    
    return stats


def create_metadata_from_novel_info(novel_info) -> NovelMetadata:
    """
    Create NovelMetadata from NovelInfo discovered from filesystem.
    
    Args:
        novel_info: NovelInfo object from discovery service
        
    Returns:
        NovelMetadata object
    """
    # Try to extract metadata from markdown file if available
    metadata_from_file = extract_metadata_from_markdown(novel_info.markdown_file)
    
    # Create metadata with available information
    metadata = NovelMetadata(
        title=novel_info.title,
        author=novel_info.author,
        description=novel_info.description or metadata_from_file.get("description", ""),
        source_url=metadata_from_file.get("source_url", f"file://{novel_info.directory}"),
        cover_url=metadata_from_file.get("cover_url"),
        genres=metadata_from_file.get("genres", []),
        tags=metadata_from_file.get("tags", []),
        status=parse_novel_status(metadata_from_file.get("status", novel_info.status)),
        chapter_count=novel_info.chapter_count,
        word_count=getattr(novel_info, 'word_count', None),
        provider=metadata_from_file.get("provider", "Unknown"),
        provider_id=metadata_from_file.get("provider_id"),
        scraped_at=novel_info.created_at,
    )
    
    return metadata


def extract_metadata_from_markdown(markdown_file: Optional[Path]) -> dict:
    """
    Extract metadata from markdown file YAML frontmatter.
    
    Args:
        markdown_file: Path to markdown file
        
    Returns:
        Dictionary with extracted metadata
    """
    metadata = {}
    
    if not markdown_file or not markdown_file.exists():
        return metadata
    
    try:
        import yaml
        
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for YAML frontmatter
        if content.startswith('---\n'):
            end_marker = content.find('\n---\n', 4)
            if end_marker != -1:
                yaml_content = content[4:end_marker]
                metadata = yaml.safe_load(yaml_content) or {}
                
    except Exception as e:
        logger.debug(f"Could not extract metadata from {markdown_file}: {e}")
    
    return metadata


def parse_novel_status(status_str: str) -> NovelStatus:
    """
    Parse novel status string to NovelStatus enum.
    
    Args:
        status_str: Status string
        
    Returns:
        NovelStatus enum value
    """
    if not status_str:
        return NovelStatus.UNKNOWN
    
    status_lower = status_str.lower()
    
    if status_lower in ['completed', 'complete', 'finished']:
        return NovelStatus.COMPLETED
    elif status_lower in ['ongoing', 'in progress', 'updating']:
        return NovelStatus.ONGOING
    elif status_lower in ['hiatus', 'paused', 'on hold']:
        return NovelStatus.HIATUS
    elif status_lower in ['dropped', 'cancelled', 'discontinued']:
        return NovelStatus.DROPPED
    else:
        return NovelStatus.UNKNOWN


def main():
    """Main entry point for the import script."""
    parser = argparse.ArgumentParser(
        description="Import existing novels from filesystem to database"
    )
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=Path("/home/sugeng/novels"),
        help="Directory to scan for novels (default: /home/sugeng/novels)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without actually doing it"
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Update existing records even if they already exist"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        help="Custom database path (uses user preference if not specified)"
    )
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate directory
    if not args.directory.exists():
        logger.error(f"Directory does not exist: {args.directory}")
        sys.exit(1)
    
    if not args.directory.is_dir():
        logger.error(f"Path is not a directory: {args.directory}")
        sys.exit(1)
    
    try:
        # Get database path
        if args.database_path:
            db_path = str(args.database_path)
        else:
            user_prefs = get_user_preferences()
            db_path = user_prefs.database_path
        
        # Initialize database service
        logger.info("Initializing database service...")
        db_service = NovelDatabaseService(db_path)
        
        # Import novels
        logger.info(f"Starting import from: {args.directory}")
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        stats = import_novels_from_directory(
            args.directory,
            db_service,
            dry_run=args.dry_run,
            force_update=args.force_update
        )
        
        # Print results
        logger.info("Import completed!")
        logger.info(f"📚 Scanned: {stats['scanned']} novels")
        logger.info(f"➕ Imported: {stats['imported']} new novels")
        logger.info(f"🔄 Updated: {stats['updated']} existing novels")
        logger.info(f"⏭️ Skipped: {stats['skipped']} novels")
        if stats['errors'] > 0:
            logger.warning(f"❌ Errors: {stats['errors']} novels")
        
        # Show database statistics
        if not args.dry_run:
            db_stats = db_service.get_statistics()
            logger.info(f"📊 Total novels in database: {db_stats['total_novels']}")
            logger.info(f"📖 Novels with EPUB: {db_stats['novels_with_epub']}")
        
        db_service.close()
        
    except KeyboardInterrupt:
        logger.info("Import cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
