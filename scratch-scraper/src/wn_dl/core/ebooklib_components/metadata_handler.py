"""
Metadata handler for EbookLib EPUB generator.

This module handles extraction and embedding of metadata from YAML frontmatter
into EPUB files using ebooklib, maintaining compatibility with existing metadata structure.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ebooklib import epub

logger = logging.getLogger(__name__)


class MetadataHandler:
    """
    Handles metadata extraction and embedding for EPUB generation using ebooklib.
    
    Converts YAML frontmatter metadata to ebooklib format while maintaining
    compatibility with the existing pandoc metadata structure.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize metadata handler with configuration.

        Args:
            config: Metadata handling configuration
        """
        self.config = config
        logger.debug("MetadataHandler initialized")

    def set_book_metadata(
        self,
        book: epub.EpubBook,
        yaml_metadata: Dict[str, Any],
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Set EPUB book metadata from YAML frontmatter and additional metadata.

        Args:
            book: EPUB book object
            yaml_metadata: Metadata from YAML frontmatter
            additional_metadata: Additional metadata from CLI or other sources
        """
        try:
            # Merge metadata sources
            metadata = self._merge_metadata(yaml_metadata, additional_metadata)

            # Set core metadata
            self._set_core_metadata(book, metadata)

            # Set Dublin Core metadata
            self._set_dublin_core_metadata(book, metadata)

            # Set custom metadata
            self._set_custom_metadata(book, metadata)

            logger.info("Successfully set EPUB metadata")

        except Exception as e:
            logger.error(f"Error setting EPUB metadata: {e}")

    def _merge_metadata(
        self,
        yaml_metadata: Dict[str, Any],
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Merge metadata from different sources.

        Args:
            yaml_metadata: Metadata from YAML frontmatter
            additional_metadata: Additional metadata

        Returns:
            Merged metadata dictionary
        """
        metadata = yaml_metadata.copy()

        if additional_metadata:
            # Additional metadata takes precedence
            metadata.update(additional_metadata)

        return metadata

    def _set_core_metadata(self, book: epub.EpubBook, metadata: Dict[str, Any]) -> None:
        """
        Set core EPUB metadata (identifier, title, language).

        Args:
            book: EPUB book object
            metadata: Metadata dictionary
        """
        # Set identifier (required)
        identifier = metadata.get("identifier") or metadata.get("source_url") or f"wn-dl-{datetime.now().isoformat()}"
        book.set_identifier(str(identifier))

        # Set title (required)
        title = metadata.get("title", "Untitled Novel")
        book.set_title(title)

        # Set language (required)
        language = metadata.get("language") or metadata.get("lang", "en")
        book.set_language(language)

        logger.debug(f"Set core metadata: title='{title}', language='{language}'")

    def _set_dublin_core_metadata(self, book: epub.EpubBook, metadata: Dict[str, Any]) -> None:
        """
        Set Dublin Core metadata.

        Args:
            book: EPUB book object
            metadata: Metadata dictionary
        """
        # Author(s)
        author = metadata.get("author")
        if author:
            if isinstance(author, list):
                for auth in author:
                    book.add_author(str(auth))
            else:
                book.add_author(str(author))

        # Description
        description = metadata.get("description")
        if description:
            book.add_metadata("DC", "description", str(description))

        # Publisher
        publisher = metadata.get("publisher")
        if publisher:
            book.add_metadata("DC", "publisher", str(publisher))

        # Date
        date = metadata.get("date") or metadata.get("publication_date")
        if date:
            if hasattr(date, "isoformat"):
                date_str = date.isoformat()[:10]  # YYYY-MM-DD format
            else:
                date_str = str(date)
            book.add_metadata("DC", "date", date_str)

        # Rights
        rights = metadata.get("rights")
        if rights:
            book.add_metadata("DC", "rights", str(rights))

        # Subject (genres)
        subject = metadata.get("subject")
        if subject:
            if isinstance(subject, str):
                # Split comma-separated subjects
                subjects = [s.strip() for s in subject.split(",")]
                for subj in subjects:
                    if subj:
                        book.add_metadata("DC", "subject", subj)
            elif isinstance(subject, list):
                for subj in subject:
                    book.add_metadata("DC", "subject", str(subj))

        # Handle genres as subjects if subject not present
        if not subject:
            genres = metadata.get("genres")
            if genres:
                if isinstance(genres, list):
                    for genre in genres:
                        book.add_metadata("DC", "subject", str(genre))
                elif isinstance(genres, str):
                    # Split comma-separated genres
                    genre_list = [g.strip() for g in genres.split(",")]
                    for genre in genre_list:
                        if genre:
                            book.add_metadata("DC", "subject", genre)

        logger.debug("Set Dublin Core metadata")

    def _set_custom_metadata(self, book: epub.EpubBook, metadata: Dict[str, Any]) -> None:
        """
        Set custom metadata specific to web novels.

        Args:
            book: EPUB book object
            metadata: Metadata dictionary
        """
        # Status
        status = metadata.get("status")
        if status:
            book.add_metadata(None, "meta", "", {"name": "status", "content": str(status)})

        # Rating
        rating = metadata.get("rating")
        if rating:
            book.add_metadata(None, "meta", "", {"name": "rating", "content": str(rating)})

        # Rating count
        rating_count = metadata.get("rating_count")
        if rating_count:
            book.add_metadata(None, "meta", "", {"name": "rating_count", "content": str(rating_count)})

        # Chapter count
        chapters = metadata.get("chapters")
        if chapters:
            book.add_metadata(None, "meta", "", {"name": "chapters", "content": str(chapters)})

        # Last updated
        last_updated = metadata.get("last_updated")
        if last_updated:
            book.add_metadata(None, "meta", "", {"name": "last_updated", "content": str(last_updated)})

        # Source URL
        source_url = metadata.get("source_url")
        if source_url:
            book.add_metadata(None, "meta", "", {"name": "source_url", "content": str(source_url)})

        # Provider
        provider = metadata.get("provider")
        if provider:
            book.add_metadata(None, "meta", "", {"name": "provider", "content": str(provider)})

        # Tags (as keywords)
        tags = metadata.get("tags")
        if tags:
            if isinstance(tags, list):
                keywords = ", ".join(str(tag) for tag in tags)
            else:
                keywords = str(tags)
            book.add_metadata(None, "meta", "", {"name": "keywords", "content": keywords})

        # Alternative names
        alternative_names = metadata.get("alternative_names")
        if alternative_names:
            if isinstance(alternative_names, list):
                alt_names = ", ".join(str(name) for name in alternative_names)
            else:
                alt_names = str(alternative_names)
            book.add_metadata(None, "meta", "", {"name": "alternative_names", "content": alt_names})

        logger.debug("Set custom metadata")

    def extract_cover_path(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Extract cover image path from metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Cover image path or None if not found
        """
        # Try different cover path keys
        cover_keys = ["cover-image", "cover_image", "cover_path", "cover"]
        
        for key in cover_keys:
            cover_path = metadata.get(key)
            if cover_path:
                # Convert to Path object and resolve
                path_obj = Path(cover_path)
                
                # Handle absolute paths
                if path_obj.is_absolute() and path_obj.exists():
                    return str(path_obj)
                
                # Handle relative paths (relative to current working directory)
                if path_obj.exists():
                    return str(path_obj.resolve())
                
                logger.warning(f"Cover image not found: {cover_path}")

        return None

    def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate metadata for EPUB requirements.

        Args:
            metadata: Metadata dictionary

        Returns:
            True if metadata is valid
        """
        required_fields = ["title"]
        
        for field in required_fields:
            if not metadata.get(field):
                logger.error(f"Required metadata field missing: {field}")
                return False

        # Validate title length
        title = metadata.get("title", "")
        if len(title) > 255:
            logger.warning("Title is very long, may cause issues")

        # Validate language code
        language = metadata.get("language") or metadata.get("lang", "en")
        if len(language) < 2:
            logger.warning(f"Invalid language code: {language}")

        return True

    def get_metadata_summary(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a summary of metadata for logging/debugging.

        Args:
            metadata: Metadata dictionary

        Returns:
            Summary dictionary
        """
        summary = {
            "title": metadata.get("title", "Unknown"),
            "author": metadata.get("author", "Unknown"),
            "language": metadata.get("language") or metadata.get("lang", "en"),
            "has_description": bool(metadata.get("description")),
            "has_cover": bool(self.extract_cover_path(metadata)),
            "genre_count": len(metadata.get("genres", [])) if isinstance(metadata.get("genres"), list) else (1 if metadata.get("genres") else 0),
            "metadata_keys": list(metadata.keys()),
        }

        return summary
