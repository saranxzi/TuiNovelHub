#!/usr/bin/env python3
"""
HTML Structure Analysis Tool for Provider Development

This script helps analyze HTML structure of web novel sites to identify
CSS selectors for implementing new providers.

Usage:
    python scripts/analyze_html_structure.py <novel_url> [chapter_url]
    
Example:
    python scripts/analyze_html_structure.py https://example.com/novel/test-novel
    python scripts/analyze_html_structure.py https://example.com/novel/test-novel https://example.com/chapter/1
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiohttp
import cloudscraper
from bs4 import BeautifulSoup, Tag

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HTMLAnalyzer:
    """Analyzes HTML structure to suggest CSS selectors for providers."""
    
    def __init__(self):
        self.session = cloudscraper.create_scraper()
    
    async def analyze_novel_page(self, url: str) -> Dict[str, any]:
        """Analyze novel page structure."""
        print(f"\n🔍 Analyzing Novel Page: {url}")
        print("=" * 60)
        
        soup = await self._get_soup(url)
        if not soup:
            return {}
        
        analysis = {
            'url': url,
            'title_candidates': self._find_title_candidates(soup),
            'author_candidates': self._find_author_candidates(soup),
            'description_candidates': self._find_description_candidates(soup),
            'cover_candidates': self._find_cover_candidates(soup),
            'genre_candidates': self._find_genre_candidates(soup),
            'status_candidates': self._find_status_candidates(soup),
            'rating_candidates': self._find_rating_candidates(soup),
            'chapter_list_candidates': self._find_chapter_list_candidates(soup),
            'meta_tags': self._analyze_meta_tags(soup),
        }
        
        self._print_novel_analysis(analysis)
        return analysis
    
    async def analyze_chapter_page(self, url: str) -> Dict[str, any]:
        """Analyze chapter page structure."""
        print(f"\n📖 Analyzing Chapter Page: {url}")
        print("=" * 60)
        
        soup = await self._get_soup(url)
        if not soup:
            return {}
        
        analysis = {
            'url': url,
            'title_candidates': self._find_chapter_title_candidates(soup),
            'content_candidates': self._find_content_candidates(soup),
            'navigation_candidates': self._find_navigation_candidates(soup),
            'unwanted_elements': self._find_unwanted_elements(soup),
        }
        
        self._print_chapter_analysis(analysis)
        return analysis
    
    async def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse HTML."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _find_title_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential title elements."""
        candidates = []
        
        # Common title patterns
        selectors = [
            'h1', 'h2', 'h3',
            '.title', '.novel-title', '.book-title',
            '[itemprop="name"]', '.name',
            '.header h1', '.header h2',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 3:  # Filter out very short text
                    candidates.append({
                        'selector': selector,
                        'text': text[:100],  # Truncate long text
                        'tag': elem.name,
                        'classes': ' '.join(elem.get('class', [])),
                        'id': elem.get('id', ''),
                    })
        
        return candidates[:10]  # Limit results
    
    def _find_author_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential author elements."""
        candidates = []
        
        selectors = [
            '.author', '.writer', '.author-name',
            'a[href*="/author/"]', 'a[href*="/writer/"]',
            '[itemprop="author"]',
            '.info .author', '.meta .author',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text:
                    candidates.append({
                        'selector': selector,
                        'text': text,
                        'tag': elem.name,
                        'href': elem.get('href', ''),
                    })
        
        return candidates[:10]
    
    def _find_description_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential description elements."""
        candidates = []
        
        selectors = [
            '.description', '.summary', '.synopsis',
            '.desc', '.book-desc', '.novel-desc',
            '[itemprop="description"]',
            '.content .description',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 20:  # Filter short descriptions
                    candidates.append({
                        'selector': selector,
                        'text': text[:200] + '...' if len(text) > 200 else text,
                        'tag': elem.name,
                    })
        
        return candidates[:5]
    
    def _find_cover_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential cover image elements."""
        candidates = []
        
        # Image elements
        img_selectors = [
            '.cover img', '.poster img', '.thumbnail img',
            '.book-cover img', '.novel-cover img',
            'img[alt*="cover"]', 'img[alt*="poster"]',
        ]
        
        for selector in img_selectors:
            elements = soup.select(selector)
            for elem in elements:
                src = elem.get('src', '')
                if src:
                    candidates.append({
                        'selector': selector,
                        'src': src,
                        'alt': elem.get('alt', ''),
                        'type': 'img',
                    })
        
        # Meta tags
        meta_selectors = [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
        ]
        
        for selector in meta_selectors:
            elements = soup.select(selector)
            for elem in elements:
                content = elem.get('content', '')
                if content:
                    candidates.append({
                        'selector': selector,
                        'src': content,
                        'type': 'meta',
                    })
        
        return candidates[:10]
    
    def _find_genre_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential genre elements."""
        candidates = []
        
        selectors = [
            '.genre', '.genres', '.tags', '.categories',
            'a[href*="/genre/"]', 'a[href*="/tag/"]',
            '.genre-list a', '.tag-list a',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                texts = [elem.get_text(strip=True) for elem in elements[:5]]
                candidates.append({
                    'selector': selector,
                    'count': len(elements),
                    'samples': texts,
                })
        
        return candidates[:5]
    
    def _find_chapter_list_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential chapter list elements."""
        candidates = []
        
        selectors = [
            '.chapter-list a', '.chapters a',
            'ul.chapters li a', 'ol.chapters li a',
            '.chapter-item a', '.episode a',
            'a[href*="/chapter"]', 'a[href*="/ch/"]',
            '#chapters a', '.chapter-container a',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                samples = []
                for elem in elements[:3]:
                    text = elem.get_text(strip=True)
                    href = elem.get('href', '')
                    if text and href:
                        samples.append(f"{text} -> {href}")
                
                candidates.append({
                    'selector': selector,
                    'count': len(elements),
                    'samples': samples,
                })
        
        return candidates[:10]
    
    def _find_chapter_title_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential chapter title elements."""
        candidates = []
        
        selectors = [
            'h1', 'h2', 'h3',
            '.chapter-title', '.chapter-name',
            '.title', '.episode-title',
            '.header h1', '.content h1',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and ('chapter' in text.lower() or 'ch' in text.lower() or len(text) > 5):
                    candidates.append({
                        'selector': selector,
                        'text': text,
                        'tag': elem.name,
                    })
        
        return candidates[:10]
    
    def _find_content_candidates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Find potential content container elements."""
        candidates = []
        
        selectors = [
            '.content', '.chapter-content', '.episode-content',
            '#content', '#chapter-content',
            '.text', '.chapter-text', '.story-text',
            '.reader-content', '.reading-content',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for elem in elements:
                # Count paragraphs and text length
                paragraphs = elem.find_all(['p', 'div'])
                text_length = len(elem.get_text(strip=True))
                
                if text_length > 100:  # Filter short content
                    candidates.append({
                        'selector': selector,
                        'paragraph_count': len(paragraphs),
                        'text_length': text_length,
                        'preview': elem.get_text(strip=True)[:100] + '...',
                    })
        
        return candidates[:5]
    
    def _find_unwanted_elements(self, soup: BeautifulSoup) -> List[str]:
        """Find elements that should be removed from content."""
        unwanted = []
        
        selectors = [
            '.ads', '.advertisement', '.ad',
            '.navigation', '.nav', '.chapter-nav',
            '.comments', '.comment-section',
            '.author-note', '.translator-note',
            '.social', '.share', '.sharing',
            '.footer', '.sidebar',
        ]
        
        for selector in selectors:
            if soup.select(selector):
                unwanted.append(selector)
        
        return unwanted
    
    def _analyze_meta_tags(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Analyze meta tags for useful information."""
        meta_info = {}
        
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name') or tag.get('property')
            content = tag.get('content')
            
            if name and content:
                if any(keyword in name.lower() for keyword in ['title', 'description', 'image', 'author']):
                    meta_info[name] = content
        
        return meta_info
    
    def _print_novel_analysis(self, analysis: Dict):
        """Print novel page analysis results."""
        print("\n📚 NOVEL METADATA ANALYSIS")
        print("-" * 40)
        
        print("\n🏷️  Title Candidates:")
        for candidate in analysis['title_candidates'][:5]:
            print(f"  • {candidate['selector']} → '{candidate['text']}'")
        
        print("\n👤 Author Candidates:")
        for candidate in analysis['author_candidates'][:5]:
            print(f"  • {candidate['selector']} → '{candidate['text']}'")
        
        print("\n📝 Description Candidates:")
        for candidate in analysis['description_candidates'][:3]:
            print(f"  • {candidate['selector']} → '{candidate['text'][:50]}...'")
        
        print("\n🖼️  Cover Image Candidates:")
        for candidate in analysis['cover_candidates'][:3]:
            print(f"  • {candidate['selector']} → {candidate['src']}")
        
        print("\n🏷️  Genre Candidates:")
        for candidate in analysis['genre_candidates'][:3]:
            print(f"  • {candidate['selector']} → {candidate['count']} items: {candidate['samples']}")
        
        print("\n📋 Chapter List Candidates:")
        for candidate in analysis['chapter_list_candidates'][:5]:
            print(f"  • {candidate['selector']} → {candidate['count']} chapters")
            for sample in candidate['samples'][:2]:
                print(f"    - {sample}")
        
        if analysis['meta_tags']:
            print("\n🏷️  Useful Meta Tags:")
            for name, content in analysis['meta_tags'].items():
                print(f"  • {name} → {content[:50]}...")
    
    def _print_chapter_analysis(self, analysis: Dict):
        """Print chapter page analysis results."""
        print("\n📖 CHAPTER CONTENT ANALYSIS")
        print("-" * 40)
        
        print("\n🏷️  Chapter Title Candidates:")
        for candidate in analysis['title_candidates'][:5]:
            print(f"  • {candidate['selector']} → '{candidate['text']}'")
        
        print("\n📄 Content Container Candidates:")
        for candidate in analysis['content_candidates'][:3]:
            print(f"  • {candidate['selector']} → {candidate['paragraph_count']} paragraphs, {candidate['text_length']} chars")
            print(f"    Preview: {candidate['preview']}")
        
        if analysis['unwanted_elements']:
            print("\n🚫 Elements to Remove:")
            for selector in analysis['unwanted_elements']:
                print(f"  • {selector}")
    
    def generate_config_template(self, novel_analysis: Dict, chapter_analysis: Optional[Dict] = None) -> str:
        """Generate configuration template based on analysis."""
        config = """# Generated configuration template
provider:
  name: "NewProvider"
  base_url: "https://example.com"
  description: "Provider for example.com"

selectors:
  # Novel metadata selectors"""
        
        if novel_analysis.get('title_candidates'):
            best_title = novel_analysis['title_candidates'][0]['selector']
            config += f'\n  title: "{best_title}"'
        
        if novel_analysis.get('author_candidates'):
            best_author = novel_analysis['author_candidates'][0]['selector']
            config += f'\n  author: "{best_author}"'
        
        if novel_analysis.get('description_candidates'):
            best_desc = novel_analysis['description_candidates'][0]['selector']
            config += f'\n  description: "{best_desc}"'
        
        if novel_analysis.get('cover_candidates'):
            best_cover = novel_analysis['cover_candidates'][0]['selector']
            config += f'\n  cover_image: "{best_cover}"'
        
        if novel_analysis.get('chapter_list_candidates'):
            best_chapters = novel_analysis['chapter_list_candidates'][0]['selector']
            config += f'\n  chapter_list: "{best_chapters}"'
        
        if chapter_analysis:
            config += "\n  \n  # Chapter content selectors"
            if chapter_analysis.get('title_candidates'):
                best_ch_title = chapter_analysis['title_candidates'][0]['selector']
                config += f'\n  chapter_title: "{best_ch_title}"'
            
            if chapter_analysis.get('content_candidates'):
                best_content = chapter_analysis['content_candidates'][0]['selector']
                config += f'\n  chapter_content: "{best_content}"'
        
        config += """

# Content processing
content_processing:
  remove_selectors:"""
        
        if chapter_analysis and chapter_analysis.get('unwanted_elements'):
            for selector in chapter_analysis['unwanted_elements'][:5]:
                config += f'\n    - "{selector}"'
        
        return config


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Analyze HTML structure for provider development')
    parser.add_argument('novel_url', help='URL of the novel page to analyze')
    parser.add_argument('chapter_url', nargs='?', help='Optional URL of a chapter page to analyze')
    parser.add_argument('--output', '-o', help='Output file for configuration template')
    
    args = parser.parse_args()
    
    analyzer = HTMLAnalyzer()
    
    # Analyze novel page
    novel_analysis = await analyzer.analyze_novel_page(args.novel_url)
    
    # Analyze chapter page if provided
    chapter_analysis = None
    if args.chapter_url:
        chapter_analysis = await analyzer.analyze_chapter_page(args.chapter_url)
    
    # Generate configuration template
    print("\n" + "=" * 60)
    print("📋 SUGGESTED CONFIGURATION")
    print("=" * 60)
    
    config_template = analyzer.generate_config_template(novel_analysis, chapter_analysis)
    print(config_template)
    
    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write(config_template)
        print(f"\n💾 Configuration template saved to: {args.output}")
    
    print("\n✅ Analysis complete! Use the suggested selectors to implement your provider.")


if __name__ == "__main__":
    asyncio.run(main())
