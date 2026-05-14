"""
NovelFire provider for web novel scraping.

This module provides scraping capabilities for NovelFire (novelfire.net),
a popular web fiction platform with paginated chapter lists.
"""

from .scraper import NovelFireScraper

__all__ = ["NovelFireScraper"]
