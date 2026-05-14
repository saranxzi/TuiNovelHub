#!/usr/bin/env python3
"""
Test script to reproduce the actual scraping error.
"""

import asyncio
import os
import sys
import traceback

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from wn_dl.providers.novelfull.scraper import NovelFullScraper


async def test_real_scraping():
    """Test real scraping of the problematic chapter."""
    print("=== Testing Real NovelFull Scraping ===")

    # Load configuration
    config_path = "config/novelfull-provider.yaml"
    try:
        import yaml

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        config = {}

    # Create scraper instance
    scraper = NovelFullScraper(config)

    # Test the problematic URL
    chapter_url = "https://novelfull.com/world-defying-dan-god/chapter-555.html"

    print(f"Testing chapter URL: {chapter_url}")

    try:
        # Get the soup first to test step by step
        soup = await scraper._get_soup_cached(chapter_url)
        if soup is None:
            print("ERROR: Could not get soup from URL")
            return

        print("Step 1: Got soup successfully")

        # Test title extraction
        try:
            title = scraper._extract_chapter_title(soup)
            print(f"Step 2: Title extracted: '{title}'")
        except Exception as e:
            print(f"ERROR in _extract_chapter_title: {e}")
            traceback.print_exc()
            return

        # Test content extraction
        try:
            content = scraper._extract_chapter_content(soup, title)
            print(f"Step 3: Content extracted, length: {len(content)}")
        except Exception as e:
            print(f"ERROR in _extract_chapter_content: {e}")
            traceback.print_exc()
            return

        # Test chapter number extraction
        try:
            chapter_number = scraper._extract_chapter_number(title, chapter_url)
            print(f"Step 4: Chapter number: {chapter_number}")
        except Exception as e:
            print(f"ERROR in _extract_chapter_number: {e}")
            traceback.print_exc()
            return

        # Test title enhancement
        try:
            enhanced_title = scraper._extract_title_from_content(
                content, title or "Untitled Chapter", chapter_number
            )
            print(f"Step 5: Enhanced title: '{enhanced_title}'")
        except Exception as e:
            print(f"ERROR in _extract_title_from_content: {e}")
            traceback.print_exc()
            return

        print("SUCCESS: All steps completed without error")

        # Test the full scrape_chapter_content method
        print("\nTesting full scrape_chapter_content method...")
        try:
            chapter_data = await scraper.scrape_chapter_content(chapter_url)
            if chapter_data:
                print(f"FULL SUCCESS: Chapter scraped successfully")
                print(f"Final title: '{chapter_data.title}'")
                print(f"Content length: {len(chapter_data.content)}")
                print(f"Word count: {chapter_data.word_count}")
            else:
                print("ERROR: Full scraping returned None")
        except Exception as e:
            print(f"ERROR in full scraping: {e}")
            traceback.print_exc()

    except Exception as e:
        print(f"ERROR during scraping: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_real_scraping())
