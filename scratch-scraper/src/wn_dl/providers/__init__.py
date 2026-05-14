"""
Provider system for web novel scrapers.

This module manages the registration and discovery of provider-specific scrapers.
"""

from .novelbin import NovelBinScraper
from .novelbuddy import NovelBuddyScraper
from .novelfire import NovelFireScraper
from .novelfull import NovelFullScraper
from .registry import (
    ProviderRegistry,
    get_scraper_for_url,
    list_providers,
    list_supported_domains,
    register_provider,
    registry,
)
from .royalroad import RoyalRoadScraper
from .wuxiaworld import WuxiaworldScraper

# Register built-in providers
register_provider("novelbin", NovelBinScraper, ["novelbin.com"])
register_provider("novelbuddy", NovelBuddyScraper, ["novelbuddy.com"])
register_provider("novelfire", NovelFireScraper, ["novelfire.net", "www.novelfire.net"])
register_provider("novelfull", NovelFullScraper, ["novelfull.com"])
register_provider("royalroad", RoyalRoadScraper, ["royalroad.com", "www.royalroad.com"])
register_provider("wuxiaworld", WuxiaworldScraper, ["wuxiaworld.site"])

__all__ = [
    "ProviderRegistry",
    "registry",
    "register_provider",
    "get_scraper_for_url",
    "list_providers",
    "list_supported_domains",
    "NovelBinScraper",
    "NovelBuddyScraper",
    "NovelFireScraper",
    "NovelFullScraper",
    "RoyalRoadScraper",
    "WuxiaworldScraper",
]
