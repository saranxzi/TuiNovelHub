"""
Core framework for the web novel scraper.

This module provides the base classes and data models used throughout the application.
"""

from .base_scraper import BaseNovelScraper
from .models import (
    NovelMetadata,
    ChapterData,
    ScrapingProgress,
    NovelStatus,
    ScrapingStatus,
)

__all__ = [
    "BaseNovelScraper",
    "NovelMetadata",
    "ChapterData",
    "ScrapingProgress",
    "NovelStatus",
    "ScrapingStatus",
]