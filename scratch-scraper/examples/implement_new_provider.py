#!/usr/bin/env python3
"""
Example: Implementing a New Provider

This example demonstrates the complete workflow for implementing a new provider
using the tools and templates provided.

This is a demonstration script - adapt the URLs and selectors for your target site.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wn_dl.config import get_provider_config
from wn_dl.providers.novelbin import NovelBinScraper


async def demonstrate_provider_workflow():
    """Demonstrate the complete provider implementation workflow."""
    
    print("🚀 Provider Implementation Workflow Demonstration")
    print("=" * 60)
    
    print("\n📋 Step 1: Analyze HTML Structure")
    print("-" * 40)
    print("Use the HTML analysis tool to understand the target site:")
    print("$ python scripts/analyze_html_structure.py https://example.com/novel/test-novel")
    print("\nThis will output:")
    print("• Suggested CSS selectors for metadata")
    print("• Chapter discovery patterns")
    print("• Content extraction selectors")
    print("• Configuration template")
    
    print("\n📝 Step 2: Create Configuration File")
    print("-" * 40)
    print("Create config/newprovider-provider.yaml with:")
    
    example_config = """
provider:
  name: "NewProvider"
  base_url: "https://example.com"
  description: "Provider for example.com web novels"

selectors:
  title: "h1.novel-title"
  author: ".author a"
  description: ".description"
  cover_image: ".cover img"
  chapter_list: ".chapter-list a"
  chapter_title: ".chapter-title"
  chapter_content: ".chapter-content"

chapter_discovery:
  discovery_method: "static"

content_processing:
  remove_selectors:
    - ".ads"
    - ".navigation"
"""
    print(example_config)
    
    print("\n🔧 Step 3: Implement Scraper Class")
    print("-" * 40)
    print("Create src/wn_dl/providers/newprovider/scraper.py")
    print("• Copy template from docs/PROVIDER_TEMPLATE.md")
    print("• Customize class name and provider name")
    print("• Implement extraction methods")
    
    print("\n📦 Step 4: Register Provider")
    print("-" * 40)
    print("Update src/wn_dl/providers/__init__.py:")
    print("• Import your scraper class")
    print("• Register with domains")
    print("• Add to exports")
    
    print("\n🧪 Step 5: Test Implementation")
    print("-" * 40)
    print("Validate your provider:")
    print("$ python scripts/validate_provider.py newprovider https://example.com/novel/test")
    print("\nThis will test:")
    print("• Configuration validation")
    print("• Metadata extraction")
    print("• Chapter discovery")
    print("• Content extraction")
    
    print("\n✅ Step 6: Integration Testing")
    print("-" * 40)
    print("Test with the main application:")
    print("$ python -m wn_dl https://example.com/novel/test --output ./test_output")
    
    print("\n🎯 Example: Using Existing NovelBin Provider")
    print("-" * 40)
    print("Let's demonstrate with the existing NovelBin provider...")
    
    # Load NovelBin configuration
    try:
        config = get_provider_config("novelbin")
        scraper = NovelBinScraper(config)
        
        print(f"✅ Provider: {scraper.get_provider_name()}")
        print(f"✅ Base URL: {scraper.base_url}")
        print(f"✅ Configuration loaded successfully")
        
        # Show some configuration details
        selectors = config.get("selectors", {})
        print(f"\n📋 Key Selectors:")
        for key in ["title", "author", "description", "chapter_list"]:
            if key in selectors:
                print(f"  • {key}: {selectors[key]}")
        
        print(f"\n⚙️  Chapter Discovery: {config.get('chapter_discovery', {}).get('discovery_method', 'static')}")
        print(f"⚙️  Rate Limit: {config.get('request', {}).get('rate_limit_delay', 1.0)}s")
        
    except Exception as e:
        print(f"❌ Error loading NovelBin config: {e}")
    
    print("\n💡 Key Implementation Tips")
    print("-" * 40)
    print("1. 🔍 Start with HTML analysis - understand the site structure first")
    print("2. 📝 Use specific CSS selectors to avoid false matches")
    print("3. 🧪 Test with multiple novels to ensure robustness")
    print("4. 🚫 Configure content cleaning to remove ads/navigation")
    print("5. ⏱️  Respect rate limits to avoid being blocked")
    print("6. 📊 Aim for validation score > 80%")
    
    print("\n🛠️  Available Tools")
    print("-" * 40)
    print("• scripts/analyze_html_structure.py - Analyze site structure")
    print("• scripts/validate_provider.py - Test implementation")
    print("• docs/PROVIDER_IMPLEMENTATION_GUIDE.md - Complete guide")
    print("• docs/PROVIDER_TEMPLATE.md - Copy-paste templates")
    print("• docs/PROVIDER_QUICK_START.md - Streamlined workflow")
    
    print("\n🎉 Ready to Implement Your Provider!")
    print("=" * 60)
    print("Follow the workflow above to implement your own provider.")
    print("Start with HTML analysis, then use the templates and tools provided.")


async def demonstrate_html_analysis():
    """Demonstrate HTML analysis concepts."""
    
    print("\n🔍 HTML Analysis Demonstration")
    print("=" * 60)
    
    print("\n📚 What to Look For in Novel Pages:")
    print("-" * 40)
    
    novel_html_example = """
    <div class="novel-info">
        <h1 class="novel-title">The Great Adventure</h1>
        <div class="author">
            <span>Author: </span>
            <a href="/author/john-doe">John Doe</a>
        </div>
        <div class="description">
            <p>This is an epic tale of adventure...</p>
        </div>
        <img class="cover" src="/covers/great-adventure.jpg" alt="Cover">
        <div class="genres">
            <a href="/genre/fantasy">Fantasy</a>
            <a href="/genre/adventure">Adventure</a>
        </div>
        <div class="status">Status: Ongoing</div>
    </div>
    """
    
    print("Example HTML structure:")
    print(novel_html_example)
    
    print("\n📋 Resulting CSS Selectors:")
    print("• title: 'h1.novel-title'")
    print("• author: '.author a'")
    print("• description: '.description'")
    print("• cover_image: '.cover'")
    print("• genres: '.genres a'")
    print("• status: '.status'")
    
    print("\n📖 What to Look For in Chapter Pages:")
    print("-" * 40)
    
    chapter_html_example = """
    <div class="chapter-wrapper">
        <h1 class="chapter-title">Chapter 1: The Beginning</h1>
        <div class="chapter-content">
            <p>First paragraph of the story...</p>
            <p>Second paragraph continues...</p>
            <!-- Remove these -->
            <div class="ads">Advertisement</div>
            <div class="navigation">
                <a href="/prev">Previous</a>
                <a href="/next">Next</a>
            </div>
        </div>
    </div>
    """
    
    print("Example chapter HTML:")
    print(chapter_html_example)
    
    print("\n📋 Resulting Configuration:")
    print("• chapter_title: '.chapter-title'")
    print("• chapter_content: '.chapter-content'")
    print("• remove_selectors: ['.ads', '.navigation']")


def print_file_structure():
    """Show the expected file structure for a new provider."""
    
    print("\n📁 Provider File Structure")
    print("=" * 60)
    
    structure = """
wn-dl/
├── config/
│   └── newprovider-provider.yaml     # Provider configuration
├── src/wn_dl/providers/
│   ├── __init__.py                   # Update to register provider
│   └── newprovider/
│       ├── __init__.py               # Provider module init
│       └── scraper.py                # Scraper implementation
├── tests/
│   ├── unit/providers/
│   │   └── test_newprovider.py       # Unit tests
│   └── integration/
│       └── test_newprovider_integration.py  # Integration tests
└── docs/
    ├── PROVIDER_IMPLEMENTATION_GUIDE.md
    ├── PROVIDER_TEMPLATE.md
    └── PROVIDER_QUICK_START.md
"""
    
    print(structure)


async def main():
    """Main demonstration function."""
    await demonstrate_provider_workflow()
    await demonstrate_html_analysis()
    print_file_structure()
    
    print("\n🎯 Next Steps")
    print("=" * 60)
    print("1. Choose a web novel site to implement")
    print("2. Run HTML analysis on a novel page:")
    print("   $ python scripts/analyze_html_structure.py <novel_url>")
    print("3. Follow the templates and guides to implement")
    print("4. Test with the validation script")
    print("5. Integrate and test with real novels")
    
    print("\n📚 Documentation References:")
    print("• docs/PROVIDER_QUICK_START.md - Start here")
    print("• docs/PROVIDER_IMPLEMENTATION_GUIDE.md - Complete reference")
    print("• docs/PROVIDER_TEMPLATE.md - Copy-paste templates")
    
    print("\n🛠️  Tools Available:")
    print("• scripts/analyze_html_structure.py - HTML analysis")
    print("• scripts/validate_provider.py - Implementation testing")
    print("• examples/implement_new_provider.py - This demonstration")


if __name__ == "__main__":
    asyncio.run(main())
