#!/usr/bin/env python3
"""
Debug script to test NovelFull chapter extraction functions step by step.
"""

import sys
import os
import traceback
from bs4 import BeautifulSoup

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from wn_dl.providers.novelfull.scraper import NovelFullScraper
from wn_dl.core.models import ChapterData

def load_test_html():
    """Load the test HTML file."""
    with open('test_chapter_555.html', 'r', encoding='utf-8') as f:
        return f.read()

def test_chapter_extraction():
    """Test chapter extraction step by step."""
    print("=== Testing NovelFull Chapter Extraction ===")
    
    # Load configuration
    config_path = "config/novelfull-provider.yaml"
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        config = {}
    
    # Create scraper instance
    scraper = NovelFullScraper(config)
    
    # Load test HTML
    html_content = load_test_html()
    soup = BeautifulSoup(html_content, 'html.parser')
    
    print("1. Testing _extract_chapter_title...")
    try:
        title = scraper._extract_chapter_title(soup)
        print(f"   Title extracted: '{title}'")
    except Exception as e:
        print(f"   ERROR in _extract_chapter_title: {e}")
        traceback.print_exc()
        return
    
    print("\n2. Testing _extract_chapter_content...")
    try:
        content = scraper._extract_chapter_content(soup, title)
        print(f"   Content length: {len(content)} characters")
        print(f"   First 100 chars: {content[:100]}...")
    except Exception as e:
        print(f"   ERROR in _extract_chapter_content: {e}")
        traceback.print_exc()
        return
    
    print("\n3. Testing _extract_chapter_number...")
    try:
        chapter_url = "https://novelfull.com/world-defying-dan-god/chapter-555.html"
        chapter_number = scraper._extract_chapter_number(title, chapter_url)
        print(f"   Chapter number: {chapter_number}")
    except Exception as e:
        print(f"   ERROR in _extract_chapter_number: {e}")
        traceback.print_exc()
        return
    
    print("\n4. Testing _extract_title_from_content...")
    try:
        enhanced_title = scraper._extract_title_from_content(
            content, title or "Untitled Chapter", chapter_number
        )
        print(f"   Enhanced title: '{enhanced_title}'")
    except Exception as e:
        print(f"   ERROR in _extract_title_from_content: {e}")
        traceback.print_exc()
        return
    
    print("\n5. Testing full chapter data creation...")
    try:
        chapter_data = ChapterData(
            title=enhanced_title or title or "Untitled Chapter",
            content=content,
            url=chapter_url,
            chapter_number=chapter_number,
            is_cleaned=True,
        )
        chapter_data.calculate_word_count()
        print(f"   Chapter data created successfully")
        print(f"   Final title: '{chapter_data.title}'")
        print(f"   Word count: {chapter_data.word_count}")
    except Exception as e:
        print(f"   ERROR in chapter data creation: {e}")
        traceback.print_exc()
        return
    
    print("\n=== All tests passed! ===")

if __name__ == "__main__":
    test_chapter_extraction()
