"""
Data models for the web novel scraper.

This module defines the core data structures used throughout the application.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum


class NovelStatus(Enum):
    """Enumeration for novel status."""
    ONGOING = "ongoing"
    COMPLETED = "completed"
    HIATUS = "hiatus"
    DROPPED = "dropped"
    UNKNOWN = "unknown"


class ScrapingStatus(Enum):
    """Enumeration for scraping status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class NovelMetadata:
    """
    Metadata for a web novel.
    
    Contains all the information about a novel including title, author,
    description, and other metadata.
    """
    title: str
    author: str
    description: str
    source_url: str
    
    # Optional metadata
    cover_url: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    status: NovelStatus = NovelStatus.UNKNOWN
    alternative_names: List[str] = field(default_factory=list)
    
    # Ratings and statistics
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    chapter_count: Optional[int] = None
    word_count: Optional[int] = None
    
    # Dates
    publication_date: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    
    # Provider information
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "author": self.author,
            "description": self.description,
            "source_url": self.source_url,
            "cover_url": self.cover_url,
            "genres": self.genres,
            "tags": self.tags,
            "status": self.status.value if self.status else None,
            "alternative_names": self.alternative_names,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "chapter_count": self.chapter_count,
            "word_count": self.word_count,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "scraped_at": self.scraped_at.isoformat(),
            "provider": self.provider,
            "provider_id": self.provider_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NovelMetadata":
        """Create instance from dictionary."""
        # Handle datetime fields
        for date_field in ["publication_date", "last_updated", "scraped_at"]:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field])
        
        # Handle status enum
        if data.get("status"):
            data["status"] = NovelStatus(data["status"])
        
        return cls(**data)


@dataclass
class ChapterData:
    """
    Data for a single chapter.
    
    Contains the chapter content, metadata, and processing information.
    """
    title: str
    content: str
    url: str
    
    # Chapter identification
    chapter_number: Optional[int] = None
    volume_number: Optional[int] = None
    chapter_id: Optional[str] = None
    
    # Content statistics
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    
    # Dates
    published_date: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    
    # Processing information
    is_cleaned: bool = False
    processing_notes: List[str] = field(default_factory=list)
    
    def calculate_word_count(self) -> int:
        """Calculate and cache word count."""
        if self.word_count is None:
            self.word_count = len(self.content.split())
        return self.word_count
    
    def calculate_character_count(self) -> int:
        """Calculate and cache character count."""
        if self.character_count is None:
            self.character_count = len(self.content)
        return self.character_count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "chapter_number": self.chapter_number,
            "volume_number": self.volume_number,
            "chapter_id": self.chapter_id,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "scraped_at": self.scraped_at.isoformat(),
            "is_cleaned": self.is_cleaned,
            "processing_notes": self.processing_notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterData":
        """Create instance from dictionary."""
        # Handle datetime fields
        for date_field in ["published_date", "scraped_at"]:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field])
        
        return cls(**data)


@dataclass
class ScrapingProgress:
    """
    Progress tracking for novel scraping operations.
    
    Tracks the current state of a scraping operation including
    completed chapters, errors, and timing information.
    """
    novel_url: str
    total_chapters: int
    
    # Progress tracking
    completed_chapters: int = 0
    failed_chapters: List[str] = field(default_factory=list)
    skipped_chapters: List[str] = field(default_factory=list)
    
    # Status and timing
    status: ScrapingStatus = ScrapingStatus.NOT_STARTED
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)
    
    # Estimates
    estimated_completion: Optional[datetime] = None
    chapters_per_minute: Optional[float] = None
    
    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None
    retry_count: int = 0
    
    # Output information
    output_directory: Optional[str] = None
    generated_files: List[str] = field(default_factory=list)
    
    def start_scraping(self) -> None:
        """Mark scraping as started."""
        self.status = ScrapingStatus.IN_PROGRESS
        self.start_time = datetime.now()
        self.last_update = self.start_time
    
    def complete_chapter(self) -> None:
        """Mark a chapter as completed."""
        self.completed_chapters += 1
        self.last_update = datetime.now()
        self._update_estimates()
    
    def fail_chapter(self, chapter_url: str, error: str) -> None:
        """Mark a chapter as failed."""
        if chapter_url not in self.failed_chapters:
            self.failed_chapters.append(chapter_url)
        self.error_count += 1
        self.last_error = error
        self.last_update = datetime.now()
    
    def skip_chapter(self, chapter_url: str) -> None:
        """Mark a chapter as skipped."""
        if chapter_url not in self.skipped_chapters:
            self.skipped_chapters.append(chapter_url)
        self.last_update = datetime.now()
    
    def complete_scraping(self) -> None:
        """Mark scraping as completed."""
        self.status = ScrapingStatus.COMPLETED
        self.end_time = datetime.now()
        self.last_update = self.end_time
    
    def fail_scraping(self, error: str) -> None:
        """Mark scraping as failed."""
        self.status = ScrapingStatus.FAILED
        self.end_time = datetime.now()
        self.last_error = error
        self.last_update = self.end_time
    
    def pause_scraping(self) -> None:
        """Mark scraping as paused."""
        self.status = ScrapingStatus.PAUSED
        self.last_update = datetime.now()
    
    def resume_scraping(self) -> None:
        """Resume scraping from paused state."""
        self.status = ScrapingStatus.IN_PROGRESS
        self.last_update = datetime.now()
    
    def _update_estimates(self) -> None:
        """Update completion estimates based on current progress."""
        if self.start_time and self.completed_chapters > 0:
            elapsed = (datetime.now() - self.start_time).total_seconds() / 60  # minutes
            self.chapters_per_minute = self.completed_chapters / elapsed
            
            if self.chapters_per_minute > 0:
                remaining_chapters = self.total_chapters - self.completed_chapters
                remaining_minutes = remaining_chapters / self.chapters_per_minute
                self.estimated_completion = datetime.now() + \
                    timedelta(minutes=remaining_minutes)
    
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_chapters == 0:
            return 0.0
        return (self.completed_chapters / self.total_chapters) * 100
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total_attempted = self.completed_chapters + len(self.failed_chapters)
        if total_attempted == 0:
            return 100.0
        return (self.completed_chapters / total_attempted) * 100
    
    @property
    def elapsed_time(self) -> Optional[timedelta]:
        """Calculate elapsed time."""
        if self.start_time:
            end = self.end_time or datetime.now()
            return end - self.start_time
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "novel_url": self.novel_url,
            "total_chapters": self.total_chapters,
            "completed_chapters": self.completed_chapters,
            "failed_chapters": self.failed_chapters,
            "skipped_chapters": self.skipped_chapters,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "last_update": self.last_update.isoformat(),
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "chapters_per_minute": self.chapters_per_minute,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "retry_count": self.retry_count,
            "output_directory": self.output_directory,
            "generated_files": self.generated_files,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScrapingProgress":
        """Create instance from dictionary."""
        # Handle datetime fields
        for date_field in ["start_time", "end_time", "last_update", "estimated_completion"]:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field])
        
        # Handle status enum
        if data.get("status"):
            data["status"] = ScrapingStatus(data["status"])
        
        return cls(**data)
