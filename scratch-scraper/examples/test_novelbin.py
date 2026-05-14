#!/usr/bin/env python3
"""
Test script for NovelBin provider.

This script tests the NovelBin scraper with real data to validate functionality.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wn_dl.config import get_provider_config
from wn_dl.providers.novelbin import NovelBinScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_novel_metadata():
    """Test novel metadata extraction."""
    print("\n=== Testing Novel Metadata Extraction ===")
    
    # Test URL - using a popular novel
    test_url = "https://novelbin.com/b/the-legendary-mechanic"
    
    try:
        # Load provider configuration
        config = get_provider_config("novelbin")
        
        # Create scraper instance
        async with NovelBinScraper(config) as scraper:
            print(f"Testing URL: {test_url}")
            
            # Extract metadata
            metadata = await scraper.get_novel_metadata(test_url)
            
            if metadata:
                print("✅ Metadata extraction successful!")
                print(f"Title: {metadata.title}")
                print(f"Author: {metadata.author}")
                print(f"Description: {metadata.description[:100]}...")
                print(f"Genres: {metadata.genres}")
                print(f"Tags: {metadata.tags[:5]}...")  # Show first 5 tags
                print(f"Status: {metadata.status}")
                print(f"Rating: {metadata.rating}")
                print(f"Cover URL: {metadata.cover_url}")
                return True
            else:
                print("❌ Failed to extract metadata")
                return False
                
    except Exception as e:
        print(f"❌ Error during metadata extraction: {e}")
        logger.exception("Metadata extraction failed")
        return False


async def test_chapter_list():
    """Test chapter list extraction."""
    print("\n=== Testing Chapter List Extraction ===")
    
    test_url = "https://novelbin.com/b/the-legendary-mechanic"
    
    try:
        config = get_provider_config("novelbin")
        
        async with NovelBinScraper(config) as scraper:
            print(f"Testing chapter list for: {test_url}")
            
            # Get chapter list
            chapters = await scraper.get_chapter_list(test_url)
            
            if chapters:
                print(f"✅ Found {len(chapters)} chapters!")
                
                # Show first few chapters
                print("First 5 chapters:")
                for i, chapter in enumerate(chapters[:5]):
                    print(f"  {i+1}. {chapter['title']} - {chapter['url']}")
                
                # Show last few chapters
                if len(chapters) > 5:
                    print("Last 3 chapters:")
                    for chapter in chapters[-3:]:
                        print(f"  {chapter['number']}. {chapter['title']}")
                
                return chapters
            else:
                print("❌ No chapters found")
                return []
                
    except Exception as e:
        print(f"❌ Error during chapter list extraction: {e}")
        logger.exception("Chapter list extraction failed")
        return []


async def test_chapter_content(chapter_url: str):
    """Test chapter content extraction."""
    print(f"\n=== Testing Chapter Content Extraction ===")
    
    try:
        config = get_provider_config("novelbin")
        
        async with NovelBinScraper(config) as scraper:
            print(f"Testing chapter: {chapter_url}")
            
            # Extract chapter content
            chapter_data = await scraper.scrape_chapter_content(chapter_url)
            
            if chapter_data:
                print("✅ Chapter content extraction successful!")
                print(f"Title: {chapter_data.title}")
                print(f"Word count: {chapter_data.word_count}")
                print(f"Content preview: {chapter_data.content[:200]}...")
                return True
            else:
                print("❌ Failed to extract chapter content")
                return False
                
    except Exception as e:
        print(f"❌ Error during chapter content extraction: {e}")
        logger.exception("Chapter content extraction failed")
        return False


async def test_provider_registration():
    """Test provider registration system."""
    print("\n=== Testing Provider Registration ===")
    
    try:
        from wn_dl.providers import registry, get_scraper_for_url
        
        # Test provider listing
        providers = registry.list_providers()
        print(f"Registered providers: {providers}")
        
        # Test domain mapping
        domains = registry.list_supported_domains()
        print(f"Supported domains: {domains}")
        
        # Test URL-based provider detection
        test_url = "https://novelbin.com/b/test-novel"
        provider_name = registry.get_provider_for_url(test_url)
        print(f"Provider for {test_url}: {provider_name}")
        
        # Test scraper creation
        config = get_provider_config("novelbin")
        scraper = get_scraper_for_url(test_url, config)
        
        if scraper:
            print(f"✅ Successfully created scraper: {scraper.__class__.__name__}")
            return True
        else:
            print("❌ Failed to create scraper")
            return False
            
    except Exception as e:
        print(f"❌ Error during provider registration test: {e}")
        logger.exception("Provider registration test failed")
        return False


async def test_error_handling():
    """Test error handling with invalid URLs."""
    print("\n=== Testing Error Handling ===")
    
    try:
        config = get_provider_config("novelbin")
        
        async with NovelBinScraper(config) as scraper:
            # Test invalid URL
            invalid_url = "https://novelbin.com/b/nonexistent-novel-12345"
            print(f"Testing invalid URL: {invalid_url}")
            
            metadata = await scraper.get_novel_metadata(invalid_url)
            
            if metadata is None:
                print("✅ Correctly handled invalid URL (returned None)")
                return True
            else:
                print("❌ Should have returned None for invalid URL")
                return False
                
    except Exception as e:
        print(f"❌ Unexpected error during error handling test: {e}")
        logger.exception("Error handling test failed")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting NovelBin Provider Tests")
    print("=" * 50)
    
    results = []
    
    # Test provider registration
    results.append(await test_provider_registration())
    
    # Test metadata extraction
    results.append(await test_novel_metadata())
    
    # Test chapter list extraction
    chapters = await test_chapter_list()
    results.append(len(chapters) > 0)
    
    # Test chapter content extraction (if we have chapters)
    if chapters:
        # Test first chapter
        first_chapter_url = chapters[0]['url']
        results.append(await test_chapter_content(first_chapter_url))
    else:
        results.append(False)
    
    # Test error handling
    results.append(await test_error_handling())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    test_names = [
        "Provider Registration",
        "Novel Metadata",
        "Chapter List",
        "Chapter Content",
        "Error Handling"
    ]
    
    passed = 0
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! NovelBin provider is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        logger.exception("Unexpected error in main")
        sys.exit(1)
