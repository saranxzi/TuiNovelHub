#!/usr/bin/env python3
"""
Provider Validation Script

This script validates a provider implementation by testing it against real URLs
and checking for common issues.

Usage:
    python scripts/validate_provider.py <provider_name> <test_novel_url> [test_chapter_url]
    
Example:
    python scripts/validate_provider.py novelbin https://novelbin.com/b/test-novel
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wn_dl.config import get_provider_config
from wn_dl.providers import get_scraper_for_url, registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProviderValidator:
    """Validates provider implementations."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.config = None
        self.scraper = None
        self.validation_results = {
            'config_validation': {},
            'metadata_extraction': {},
            'chapter_discovery': {},
            'chapter_extraction': {},
            'overall_score': 0,
        }
    
    async def validate_provider(self, novel_url: str, chapter_url: Optional[str] = None) -> Dict:
        """Run complete provider validation."""
        print(f"\n🔍 Validating Provider: {self.provider_name}")
        print("=" * 60)
        
        # Step 1: Validate configuration
        await self._validate_configuration()
        
        # Step 2: Initialize scraper
        if not await self._initialize_scraper(novel_url):
            return self.validation_results
        
        # Step 3: Test metadata extraction
        await self._test_metadata_extraction(novel_url)
        
        # Step 4: Test chapter discovery
        await self._test_chapter_discovery(novel_url)
        
        # Step 5: Test chapter extraction
        if chapter_url:
            await self._test_chapter_extraction(chapter_url)
        
        # Step 6: Calculate overall score
        self._calculate_overall_score()
        
        # Step 7: Print results
        self._print_validation_results()
        
        return self.validation_results
    
    async def _validate_configuration(self):
        """Validate provider configuration."""
        print("\n📋 Validating Configuration...")
        
        try:
            self.config = get_provider_config(self.provider_name)
            
            # Check required sections
            required_sections = ['provider', 'selectors']
            missing_sections = []
            
            for section in required_sections:
                if section not in self.config:
                    missing_sections.append(section)
            
            # Check required provider fields
            provider_config = self.config.get('provider', {})
            required_provider_fields = ['name', 'base_url']
            missing_provider_fields = []
            
            for field in required_provider_fields:
                if field not in provider_config:
                    missing_provider_fields.append(field)
            
            # Check required selectors
            selectors = self.config.get('selectors', {})
            required_selectors = ['title', 'author', 'chapter_list', 'chapter_content']
            missing_selectors = []
            
            for selector in required_selectors:
                if selector not in selectors:
                    missing_selectors.append(selector)
            
            self.validation_results['config_validation'] = {
                'status': 'pass' if not (missing_sections or missing_provider_fields or missing_selectors) else 'fail',
                'missing_sections': missing_sections,
                'missing_provider_fields': missing_provider_fields,
                'missing_selectors': missing_selectors,
                'config_loaded': True,
            }
            
            print("✅ Configuration loaded successfully")
            if missing_sections:
                print(f"❌ Missing sections: {missing_sections}")
            if missing_provider_fields:
                print(f"❌ Missing provider fields: {missing_provider_fields}")
            if missing_selectors:
                print(f"⚠️  Missing selectors: {missing_selectors}")
        
        except Exception as e:
            self.validation_results['config_validation'] = {
                'status': 'fail',
                'error': str(e),
                'config_loaded': False,
            }
            print(f"❌ Configuration validation failed: {e}")
    
    async def _initialize_scraper(self, novel_url: str) -> bool:
        """Initialize scraper instance."""
        print("\n🔧 Initializing Scraper...")
        
        try:
            # Check if provider is registered
            if self.provider_name not in registry.list_providers():
                print(f"❌ Provider '{self.provider_name}' not registered")
                return False
            
            # Create scraper instance
            self.scraper = get_scraper_for_url(novel_url, self.config)
            
            if not self.scraper:
                print(f"❌ Failed to create scraper for URL: {novel_url}")
                return False
            
            print(f"✅ Scraper initialized: {self.scraper.__class__.__name__}")
            return True
        
        except Exception as e:
            print(f"❌ Scraper initialization failed: {e}")
            return False
    
    async def _test_metadata_extraction(self, novel_url: str):
        """Test novel metadata extraction."""
        print("\n📚 Testing Metadata Extraction...")
        
        try:
            metadata = await self.scraper.get_novel_metadata(novel_url)
            
            if not metadata:
                self.validation_results['metadata_extraction'] = {
                    'status': 'fail',
                    'error': 'No metadata returned',
                }
                print("❌ No metadata extracted")
                return
            
            # Check required fields
            required_fields = ['title', 'author', 'source_url']
            missing_fields = []
            field_values = {}
            
            for field in required_fields:
                value = getattr(metadata, field, None)
                field_values[field] = value
                if not value:
                    missing_fields.append(field)
            
            # Check optional fields
            optional_fields = ['description', 'cover_url', 'genres', 'status']
            optional_values = {}
            
            for field in optional_fields:
                value = getattr(metadata, field, None)
                optional_values[field] = value is not None and value != ""
            
            self.validation_results['metadata_extraction'] = {
                'status': 'pass' if not missing_fields else 'partial',
                'missing_required_fields': missing_fields,
                'field_values': field_values,
                'optional_fields_present': optional_values,
                'metadata_object': metadata,
            }
            
            print(f"✅ Title: {metadata.title}")
            print(f"✅ Author: {metadata.author}")
            print(f"✅ Description: {'Present' if metadata.description else 'Missing'}")
            print(f"✅ Cover URL: {'Present' if metadata.cover_url else 'Missing'}")
            print(f"✅ Genres: {len(metadata.genres) if metadata.genres else 0} found")
            
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
        
        except Exception as e:
            self.validation_results['metadata_extraction'] = {
                'status': 'fail',
                'error': str(e),
            }
            print(f"❌ Metadata extraction failed: {e}")
    
    async def _test_chapter_discovery(self, novel_url: str):
        """Test chapter list discovery."""
        print("\n📋 Testing Chapter Discovery...")
        
        try:
            chapters = await self.scraper.get_chapter_list(novel_url)
            
            if not chapters:
                self.validation_results['chapter_discovery'] = {
                    'status': 'fail',
                    'error': 'No chapters found',
                    'chapter_count': 0,
                }
                print("❌ No chapters discovered")
                return
            
            # Validate chapter structure
            valid_chapters = 0
            invalid_chapters = []
            
            for i, chapter in enumerate(chapters[:10]):  # Check first 10 chapters
                if isinstance(chapter, dict) and 'title' in chapter and 'url' in chapter:
                    valid_chapters += 1
                else:
                    invalid_chapters.append(i)
            
            self.validation_results['chapter_discovery'] = {
                'status': 'pass' if valid_chapters > 0 else 'fail',
                'chapter_count': len(chapters),
                'valid_chapters': valid_chapters,
                'invalid_chapters': invalid_chapters,
                'sample_chapters': chapters[:5],
            }
            
            print(f"✅ Found {len(chapters)} chapters")
            print(f"✅ Valid chapter structure: {valid_chapters}/{min(10, len(chapters))}")
            
            # Show sample chapters
            print("📋 Sample chapters:")
            for i, chapter in enumerate(chapters[:3]):
                title = chapter.get('title', 'No title')
                url = chapter.get('url', 'No URL')
                print(f"  {i+1}. {title} → {url}")
            
            if invalid_chapters:
                print(f"⚠️  Invalid chapter structures at indices: {invalid_chapters}")
        
        except Exception as e:
            self.validation_results['chapter_discovery'] = {
                'status': 'fail',
                'error': str(e),
                'chapter_count': 0,
            }
            print(f"❌ Chapter discovery failed: {e}")
    
    async def _test_chapter_extraction(self, chapter_url: str):
        """Test chapter content extraction."""
        print("\n📖 Testing Chapter Extraction...")
        
        try:
            chapter_data = await self.scraper.scrape_chapter_content(chapter_url)
            
            if not chapter_data:
                self.validation_results['chapter_extraction'] = {
                    'status': 'fail',
                    'error': 'No chapter data returned',
                }
                print("❌ No chapter data extracted")
                return
            
            # Validate chapter data
            content_length = len(chapter_data.content) if chapter_data.content else 0
            word_count = chapter_data.word_count if hasattr(chapter_data, 'word_count') else 0
            
            self.validation_results['chapter_extraction'] = {
                'status': 'pass' if content_length > 100 else 'partial',
                'title': chapter_data.title,
                'content_length': content_length,
                'word_count': word_count,
                'chapter_number': getattr(chapter_data, 'chapter_number', None),
                'url': chapter_data.url,
            }
            
            print(f"✅ Chapter title: {chapter_data.title}")
            print(f"✅ Content length: {content_length} characters")
            print(f"✅ Word count: {word_count} words")
            print(f"✅ Chapter number: {getattr(chapter_data, 'chapter_number', 'Not detected')}")
            
            # Show content preview
            if chapter_data.content:
                preview = chapter_data.content[:200] + "..." if len(chapter_data.content) > 200 else chapter_data.content
                print(f"📄 Content preview: {preview}")
            
            if content_length < 100:
                print("⚠️  Content seems very short, check extraction logic")
        
        except Exception as e:
            self.validation_results['chapter_extraction'] = {
                'status': 'fail',
                'error': str(e),
            }
            print(f"❌ Chapter extraction failed: {e}")
    
    def _calculate_overall_score(self):
        """Calculate overall validation score."""
        scores = {
            'config_validation': 20,
            'metadata_extraction': 30,
            'chapter_discovery': 30,
            'chapter_extraction': 20,
        }
        
        total_score = 0
        max_score = sum(scores.values())
        
        for test, max_points in scores.items():
            result = self.validation_results.get(test, {})
            status = result.get('status', 'fail')
            
            if status == 'pass':
                total_score += max_points
            elif status == 'partial':
                total_score += max_points * 0.5
            # 'fail' adds 0 points
        
        self.validation_results['overall_score'] = (total_score / max_score) * 100
    
    def _print_validation_results(self):
        """Print comprehensive validation results."""
        print("\n" + "=" * 60)
        print("📊 VALIDATION RESULTS")
        print("=" * 60)
        
        score = self.validation_results['overall_score']
        
        if score >= 80:
            status_emoji = "🎉"
            status_text = "EXCELLENT"
        elif score >= 60:
            status_emoji = "✅"
            status_text = "GOOD"
        elif score >= 40:
            status_emoji = "⚠️"
            status_text = "NEEDS IMPROVEMENT"
        else:
            status_emoji = "❌"
            status_text = "POOR"
        
        print(f"\n{status_emoji} Overall Score: {score:.1f}% - {status_text}")
        
        print("\n📋 Test Results:")
        for test_name, result in self.validation_results.items():
            if test_name == 'overall_score':
                continue
            
            status = result.get('status', 'unknown')
            emoji = "✅" if status == 'pass' else "⚠️" if status == 'partial' else "❌"
            print(f"  {emoji} {test_name.replace('_', ' ').title()}: {status.upper()}")
        
        print("\n💡 Recommendations:")
        
        if self.validation_results['config_validation'].get('status') != 'pass':
            print("  • Fix configuration issues before proceeding")
        
        if self.validation_results['metadata_extraction'].get('status') != 'pass':
            print("  • Review and fix metadata extraction selectors")
        
        if self.validation_results['chapter_discovery'].get('status') != 'pass':
            print("  • Check chapter list selectors and discovery method")
        
        if self.validation_results['chapter_extraction'].get('status') != 'pass':
            print("  • Verify chapter content selectors and cleanup logic")
        
        if score >= 80:
            print("  🎉 Provider implementation looks great! Ready for production use.")
        elif score >= 60:
            print("  ✅ Provider implementation is functional with minor issues.")
        else:
            print("  ⚠️  Provider needs significant improvements before use.")


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Validate provider implementation')
    parser.add_argument('provider_name', help='Name of the provider to validate')
    parser.add_argument('novel_url', help='URL of a test novel')
    parser.add_argument('chapter_url', nargs='?', help='Optional URL of a test chapter')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    validator = ProviderValidator(args.provider_name)
    results = await validator.validate_provider(args.novel_url, args.chapter_url)
    
    # Exit with appropriate code
    score = results['overall_score']
    if score >= 60:
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure


if __name__ == "__main__":
    asyncio.run(main())
