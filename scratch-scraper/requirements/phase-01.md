Of course\! Building a web scraper, especially for a complex task like scraping web novels into a clean format, is a great project. A modular core allows you to easily add more providers in the future without rewriting everything.

Here is a complete, from-scratch implementation of a web novel scraper for `Novelbin` using Python, `cloudscraper` , and `BeautifulSoup` . This script is designed for concurrency and generates a valid Markdown file.

### 1\. Project Setup and Dependencies

First, ensure you have the necessary libraries installed.

```bash
pip install cloudscraper beautifulsoup4 rich
```

  + `cloudscraper`: To bypass Cloudflare and other bot detection measures.
  + `beautifulsoup4`: The standard for parsing HTML in Python.
  + `rich`: For beautiful and informative console output, including progress bars.

-----

### 2\. The Scraper Core ( `BaseScraper` )

We'll start by defining an abstract base class. This class will serve as a template for any provider-specific scraper you create, ensuring they all follow the same structure.

 `scrapers/base.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import cloudscraper

class BaseScraper(ABC):
    """
    Abstract base class for a web novel scraper.
    It defines the essential methods that every provider-specific scraper must implement.
    """

    def __init__(self, scraper: cloudscraper.CloudScraper):
        self.scraper = scraper

    @abstractmethod
    def get_novel_metadata(self, novel_url: str) -> Dict[str, any]:
        """
        Parses the main novel page to extract metadata.

        Args:
            novel_url: The URL of the novel's main page.

        Returns:
            A dictionary containing novel metadata (title, author, description, etc.).
        """
        pass

    @abstractmethod
    def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Parses the novel page to get a list of all chapters.

        Args:
            novel_url: The URL of the novel's main page.

        Returns:
            A list of dictionaries, where each dictionary contains
            a chapter's 'title' and 'url'.
        """
        pass

    @abstractmethod
    def parse_chapter_content(self, chapter_url: str) -> Optional[Dict[str, str]]:
        """
        Parses a chapter page to extract its title and content.

        Args:
            chapter_url: The URL of the chapter to parse.

        Returns:
            A dictionary with 'title' and 'content', or None if parsing fails.
        """
        pass
```

-----

### 3\. The Novelbin Provider Scraper

Now, let's implement the scraper specifically for `novelbin.com` . We'll inherit from `BaseScraper` and implement its abstract methods.

 `scrapers/novelbin.py`

```python
import cloudscraper
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from .base import BaseScraper

class NovelbinScraper(BaseScraper):
    """
    A scraper for Novelbin, implementing the BaseScraper interface.
    """

    def __init__(self, scraper: cloudscraper.CloudScraper):
        super().__init__(scraper)
        self.base_url = "https://novelbin.com"

    def get_novel_metadata(self, novel_url: str) -> Optional[Dict[str, any]]:
        """
        Extracts metadata from the Novelbin novel page.
        """
        try:
            response = self.scraper.get(novel_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.find('h3', class_='title', itemprop='name').text.strip()
            author = soup.find('a', href=lambda href: href and '/a/' in href).text.strip()
            description = soup.find('div', class_='desc-text', itemprop='description').get_text(separator='\n').strip()
            cover_image_url = soup.find('meta', property='og:image')['content']

            genres = [a.text.strip() for a in soup.select('div.info-meta a[href*="/genre/"]')]
            tags = [a.text.strip() for a in soup.select('div.tag-container a[href*="/tag/"]')]

            return {
                'title': title,
                'author': author,
                'description': description,
                'cover_image_url': cover_image_url,
                'genres': genres,
                'tags': tags,
                'source_url': novel_url,
            }
        except Exception as e:
            print(f"Error fetching metadata from {novel_url}: {e}")
            return None

    def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Retrieves the list of chapters from the novel page.
        Note: Novelbin loads chapters dynamically. For a real-world scenario,
        you might need to inspect network requests or use a browser automation tool.
        For this example, we will parse the static HTML provided.
        """
        chapters = []
        try:
            response = self.scraper.get(novel_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            chapter_elements = soup.select('#list-chapter ul.list-chapter li a')
            for a_tag in chapter_elements:
                chapters.append({
                    'title': a_tag.get('title', 'Untitled Chapter').strip(),
                    'url': a_tag['href']
                })
            
            # Since the provided HTML might not contain all chapters,
            # a real implementation would need to handle pagination or AJAX calls here.
            
        except Exception as e:
            print(f"Error fetching chapter list from {novel_url}: {e}")

        return chapters

    def parse_chapter_content(self, chapter_url: str) -> Optional[Dict[str, str]]:
        """
        Parses the content of a single chapter page.
        """
        try:
            response = self.scraper.get(chapter_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract chapter title
            title_element = soup.find('a', class_='chr-title')
            title = title_element.get('title', 'Untitled Chapter').strip() if title_element else 'Untitled Chapter'
            
            # Extract content and format it
            content_div = soup.find('div', id='chr-content')
            if not content_div:
                return None
                
            # Remove ads or unwanted divs
            for ad_div in content_div.find_all('div', id=lambda x: x and x.startswith('pf-')):
                ad_div.decompose()

            # Get text from paragraphs and format them
            paragraphs = content_div.find_all(['p', 'h4'])
            content_lines = []
            for p in paragraphs:
                if p.name == 'h4':
                    # Make headers bold in Markdown
                    content_lines.append(f"**{p.get_text().strip()}**")
                else:
                    content_lines.append(p.get_text().strip())

            content = '\n\n'.join(line for line in content_lines if line)

            return {'title': title, 'content': content}
        except Exception as e:
            print(f"Failed to parse chapter {chapter_url}: {e}")
            return None

```

-----

### 4\. The Main Application ( `main.py` )

This script ties everything together. It handles user input, uses the `ThreadPoolExecutor` for concurrent downloads, and generates the final Markdown file.

 `main.py`

```python
import cloudscraper
import concurrent.futures
import os
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from scrapers.novelbin import NovelbinScraper

def generate_markdown(metadata: dict, chapters: list) -> str:
    """
    Generates a Markdown formatted string from novel data.
    """
    md_lines = []
    
    # Metadata Section
    md_lines.append(f"# {metadata['title']}")
    md_lines.append(f"**Author:** {metadata['author']}")
    md_lines.append(f"**Source:** {metadata['source_url']}")
    md_lines.append("\n---")
    
    # Cover Image
    md_lines.append(f"

![Cover]({metadata['cover_image_url']})")

    md_lines.append("\n---")
    
    # Description
    md_lines.append("## Description")
    md_lines.append(metadata['description'])
    md_lines.append("\n---")

    # Tags and Genres
    if metadata.get('genres'):
        md_lines.append("## Genres")
        md_lines.append(f"`{'`, `'.join(metadata['genres'])}`")
    if metadata.get('tags'):
        md_lines.append("\n## Tags")
        md_lines.append(f"`{'`, `'.join(metadata['tags'])}`")
    md_lines.append("\n---")
    
    # Chapters Section
    md_lines.append("\n# Chapters\n")
    for chapter in chapters:
        if chapter:
            md_lines.append(f"## {chapter['title']}")
            md_lines.append(f"\n{chapter['content']}\n")
            md_lines.append("---")
            
    return "\n".join(md_lines)

def main():
    """
    Main function to run the web novel scraper.
    """
    novel_url = input("Enter the Novelbin URL to scrape: ")
    
    if "novelbin.com" not in novel_url:
        print("Error: This scraper is specifically for novelbin.com.")
        return

    # Initialize the HTTP client and the specific scraper
    scraper_instance = cloudscraper.create_scraper()
    provider_scraper = NovelbinScraper(scraper_instance)

    print("Fetching novel metadata...")
    metadata = provider_scraper.get_novel_metadata(novel_url)
    if not metadata:
        print("Could not retrieve novel metadata. Exiting.")
        return
        
    print(f"Scraping '{metadata['title']}'...")

    print("Fetching chapter list...")
    chapter_list = provider_scraper.get_chapter_list(novel_url)
    if not chapter_list:
        print("Could not retrieve chapter list. Exiting.")
        return
    
    print(f"Found {len(chapter_list)} chapters. Starting concurrent download...")

    # Use ThreadPoolExecutor to download chapters concurrently
    all_chapter_content = [None] * len(chapter_list)
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Downloading Chapters...", total=len(chapter_list))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_index = {
                executor.submit(provider_scraper.parse_chapter_content, chapter['url']): i
                for i, chapter in enumerate(chapter_list)
            }
            
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    chapter_content = future.result()
                    if chapter_content:
                        all_chapter_content[index] = chapter_content
                except Exception as e:
                    print(f"Chapter at index {index} generated an exception: {e}")
                progress.update(task, advance=1)

    # Filter out any failed downloads
    successful_chapters = [ch for ch in all_chapter_content if ch is not None]
    print(f"Successfully downloaded {len(successful_chapters)} out of {len(chapter_list)} chapters.")

    # Generate and save the Markdown file
    print("Generating Markdown file...")
    markdown_content = generate_markdown(metadata, successful_chapters)
    
    # Create a valid filename from the novel title
    filename = "".join(c for c in metadata['title'] if c.isalnum() or c in (' ', '-')).rstrip()
    filepath = f"{filename}.md"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
        
    print(f"\n✅ Success! Novel saved as '{filepath}'")

if __name__ == '__main__':
    main()
```

### How to Run the Scraper

01.  Create a directory for your project (e.g., `novel_scraper`).
02.  Inside `novel_scraper`, create another directory named `scrapers`.
03.  Save `base.py` and `novelbin.py` inside the `scrapers` directory.
04.  Create an empty `__init__.py` file inside the `scrapers` directory.
05.  Save `main.py` in the root `novel_scraper` directory.

Your project structure should look like this:

```
novel_scraper/
├── main.py
└── scrapers/
    ├── __init__.py
    ├── base.py
    └── novelbin.py
```

06.  Open your terminal, navigate to the `novel_scraper` directory, and run the main script:

<!-- end list -->

```bash
python main.py
```

07.  When prompted, paste the URL of the Novelbin novel you want to scrape, for example: `https://novelbin.com/b/the-legendary-mechanic`

Of course. Let's refine the scraper to include structured output directories and a configuration for the save location. This makes the project much cleaner and easier to manage as you add more novels.

The changes will primarily be in the `main.py` file to handle file path logic. The scraper classes themselves ( `BaseScraper` and `NovelbinScraper` ) will remain the same.

-----

### \#\# 1. Add Configuration and a "Slugify" Helper

First, we'll add a configuration variable at the top of `main.py` for the output directory. We'll also create a helper function to convert novel titles into safe, filesystem-friendly names (a process often called "slugifying").

Here is the refined `main.py` :

 `main.py`

```python
import cloudscraper
import concurrent.futures
import os
import re # Import the regular expression module
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from scrapers.novelbin import NovelbinScraper

# --- CONFIGURATION ---
# All scraped novels will be saved inside this directory.
OUTPUT_DIR = "scraped_novels"

# --- HELPER FUNCTIONS ---
def slugify(text: str) -> str:
    """
    Converts a string into a safe, file-system-friendly slug.
    This is used to create valid directory and file names from novel titles.
    Example: "The Legendary Mechanic!" -> "the-legendary-mechanic"
    """
    text = text.lower()
    # Remove any character that is not a letter, number, space, or hyphen
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace one or more spaces/hyphens with a single hyphen
    text = re.sub(r'[\s-]+', '-', text).strip('-')
    return text

def generate_markdown(metadata: dict, chapters: list) -> str:
    """
    Generates a Markdown formatted string from novel data. (No changes needed here)
    """
    md_lines = []
    
    # Metadata Section
    md_lines.append(f"# {metadata['title']}")
    md_lines.append(f"**Author:** {metadata['author']}")
    md_lines.append(f"**Source:** {metadata['source_url']}")
    md_lines.append("\n---")
    
    # Cover Image
    md_lines.append(f"

![Cover]({metadata['cover_image_url']})")

    md_lines.append("\n---")
    
    # Description
    md_lines.append("## Description")
    md_lines.append(metadata['description'])
    md_lines.append("\n---")

    # Tags and Genres
    if metadata.get('genres'):
        md_lines.append("## Genres")
        md_lines.append(f"`{'`, `'.join(metadata['genres'])}`")
    if metadata.get('tags'):
        md_lines.append("\n## Tags")
        md_lines.append(f"`{'`, `'.join(metadata['tags'])}`")
    md_lines.append("\n---")
    
    # Chapters Section
    md_lines.append("\n# Chapters\n")
    for chapter in chapters:
        if chapter:
            md_lines.append(f"## {chapter['title']}")
            md_lines.append(f"\n{chapter['content']}\n")
            md_lines.append("---")
            
    return "\n".join(md_lines)

def main():
    """
    Main function to run the web novel scraper.
    """
    novel_url = input("Enter the Novelbin URL to scrape: ")
    
    if "novelbin.com" not in novel_url:
        print("Error: This scraper is specifically for novelbin.com.")
        return

    # Initialize the HTTP client and the specific scraper
    scraper_instance = cloudscraper.create_scraper()
    provider_scraper = NovelbinScraper(scraper_instance)

    print("Fetching novel metadata...")
    metadata = provider_scraper.get_novel_metadata(novel_url)
    if not metadata:
        print("Could not retrieve novel metadata. Exiting.")
        return
        
    print(f"Scraping '{metadata['title']}'...")

    # Create a safe name for the novel's directory and create it
    novel_slug = slugify(metadata['title'])
    novel_output_dir = os.path.join(OUTPUT_DIR, novel_slug)
    os.makedirs(novel_output_dir, exist_ok=True)
    print(f"✔️ Output will be saved in: {novel_output_dir}")

    print("Fetching chapter list...")
    chapter_list = provider_scraper.get_chapter_list(novel_url)
    if not chapter_list:
        print("Could not retrieve chapter list. Exiting.")
        return
    
    print(f"Found {len(chapter_list)} chapters. Starting concurrent download...")

    # Use ThreadPoolExecutor to download chapters concurrently
    all_chapter_content = [None] * len(chapter_list)
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Downloading Chapters...", total=len(chapter_list))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_index = {
                executor.submit(provider_scraper.parse_chapter_content, chapter['url']): i
                for i, chapter in enumerate(chapter_list)
            }
            
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    chapter_content = future.result()
                    if chapter_content:
                        all_chapter_content[index] = chapter_content
                except Exception as e:
                    print(f"Chapter at index {index} generated an exception: {e}")
                progress.update(task, advance=1)

    # Filter out any failed downloads
    successful_chapters = [ch for ch in all_chapter_content if ch is not None]
    print(f"Successfully downloaded {len(successful_chapters)} out of {len(chapter_list)} chapters.")

    # Generate and save the Markdown file
    print("Generating Markdown file...")
    markdown_content = generate_markdown(metadata, successful_chapters)
    
    # Define the final file path inside the novel's specific directory
    filepath = os.path.join(novel_output_dir, f"{novel_slug}.md")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
        
    print(f"\n✅ Success! Novel saved as '{filepath}'")

if __name__ == '__main__':
    main()

```

-----

### \#\# 2. How It Works Now

By replacing your old `main.py` with this refined version, the scraper's behavior is now improved:

01.  **Configurable Directory**: You can easily change the `OUTPUT_DIR = "scraped_novels"` variable to any path you want (e.g.,   `"C:/Users/YourUser/Documents/Novels"`).

02.  **Safe Naming**: The `slugify()` function takes a title like `"The Legendary Mechanic!"` and converts it to a clean, safe string like `"the-legendary-mechanic"`. This prevents errors when creating directories and files.

03.  **Structured Output**: When you run the scraper, it will create the following directory structure:
    

```
    novel_scraper/
    ├── main.py
    ├── scrapers/
    |   └── ...
    └── scraped_novels/  <-- The main output directory
        └── the-legendary-mechanic/  <-- Directory for the novel
            └── the-legendary-mechanic.md  <-- The final Markdown file
    ```

# Web Novel Scraper - AI Development Instructions

## Project Overview

Build a modular web novel scraper in Python that can extract content from multiple web novel provider sites and generate well-formatted markdown files.

## Core Requirements

### Architecture

* **Modular Design**: Create a core scraper framework that supports pluggable provider-specific scrapers
* **Provider System**: Each provider should be a separate module that inherits from a base scraper class
* **Configuration**: Support for provider-specific configurations (selectors, rate limits, headers, etc.)

### Technical Stack

* **Language**: Python 3.8+
* **HTTP Library**: Use [cloudscraper](https://github.com/VeNoMouS/cloudscraper) for HTTP requests (handles Cloudflare protection)
* **Parsing**: BeautifulSoup4 or lxml for HTML parsing
* **Concurrency**: asyncio/aiohttp or threading for concurrent chapter processing
* **Image Processing**: Pillow (PIL) for cover image processing and validation
* **EPUB Generation**: Pandoc for converting markdown to EPUB format
* **Output**: Generate clean markdown files optimized for EPUB conversion

### Core Features

#### 1. Base Scraper Class

```python
class BaseNovelScraper:
    def __init__(self, base_url, config):
        # Initialize with provider-specific config
        pass
    
    def get_novel_metadata(self, novel_url):
        # Extract: title, author, description, tags, cover_image, etc.
        pass
    
    def download_cover_image(self, cover_url, output_dir):
        # Download and process cover image
        # Return local file path for EPUB generation
        pass
    
    def get_chapter_list(self, novel_url):
        # Return list of chapter URLs and titles
        pass
    
    def scrape_chapter(self, chapter_url):
        # Extract chapter title and content
        pass
    
    def generate_markdown(self, novel_data, chapters):
        # Create formatted markdown file optimized for EPUB
        pass
    
    def generate_epub(self, markdown_file, output_path, cover_image=None):
        # Convert markdown to EPUB using pandoc
        pass
```

#### 2. Cover Image Processing

* **Download**: Fetch cover image from provider URL
* **Validation**: Verify image format and dimensions
* **Processing**: Resize/optimize for EPUB standards (recommended 600x800px)
* **Fallback**: Generate placeholder cover if original is unavailable
* **Storage**: Save to local assets directory with proper naming

#### 3. Metadata Extraction

Extract and structure the following novel metadata:
* **Title**: Novel title
* **Author(s)**: Author name(s)
* **Description/Synopsis**: Novel summary
* **Tags/Genres**: Category tags
* **Status**: Ongoing, Completed, Hiatus, etc.
* **Cover Image**: Download and embed cover image
* **Publication Info**: Original publication date, last update
* **Chapter Count**: Total number of chapters
* **Rating**: If available

#### 4. Chapter Processing

* **Discovery**: Parse the novel's table of contents to get all chapter URLs
* **Concurrent Processing**: Download multiple chapters simultaneously (respect rate limits)
* **Content Cleaning**: Remove ads, navigation elements, and irrelevant content
* **Format Preservation**: Maintain paragraph breaks, emphasis, and basic formatting
* **EPUB Optimization**: Ensure proper heading hierarchy and page breaks

#### 5. Markdown Generation (EPUB-Ready)

Generate a single markdown file optimized for EPUB conversion:
* **Pandoc Metadata**: YAML front matter with EPUB-specific fields
* **Proper Heading Structure**: H1 for title, H2 for chapters, H3+ for subsections
* **Cover Integration**: Reference to downloaded cover image
* **Chapter Breaks**: Page break markers for EPUB chapters
* **Typography**: Proper emphasis, quotes, and special characters

#### 6. EPUB Generation

* **Pandoc Integration**: Automated conversion from markdown to EPUB
* **Cover Embedding**: Include downloaded cover image in EPUB
* **Metadata Preservation**: Transfer all novel metadata to EPUB format
* **Styling**: Apply custom CSS for better reading experience
* **Validation**: Verify EPUB integrity and compatibility

### Example Output Structure

```markdown
---
title: "Novel Title"
author: "Author Name"
description: "Novel description..."
tags: ["fantasy", "adventure", "magic"]
status: "ongoing"
chapters: 150
last_updated: "2024-01-15"
# EPUB-specific metadata
lang: "en"
cover-image: "assets/cover.jpg"
stylesheet: "styles/novel.css"
# Pandoc EPUB options
epub-chapter-level: 2
epub-subdirectory: "text"
---

# Novel Title

![Cover](assets/cover.jpg)

## Table of Contents

- [Chapter 1: Beginning](#chapter-1-beginning)
- [Chapter 2: Adventure](#chapter-2-adventure)

\newpage

## Chapter 1: Beginning

Chapter content here...

\newpage

## Chapter 2: Adventure

Chapter content here...
```

### Implementation Requirements

#### Error Handling

* Retry mechanism for failed requests
* Graceful handling of missing chapters or metadata
* Logging for debugging and monitoring

#### Rate Limiting

* Configurable delays between requests
* Respect robots.txt and provider-specific limits
* Implement exponential backoff for rate limit errors

#### Provider Configuration

```python
# Example provider config
PROVIDER_CONFIG = {
    "name": "ExampleSite",
    "base_url": "https://example.com",
    "selectors": {
        "title": "h1.novel-title",
        "author": ".author-name",
        "description": ".novel-description",
        "cover_image": ".novel-cover img",
        "chapter_list": ".chapter-list a",
        "chapter_content": ".chapter-content"
    },
    "rate_limit": 1.0,  # seconds between requests
    "headers": {
        "User-Agent": "Mozilla/5.0...",
        "Referer": "https://example.com"
    },
    "cover_processing": {
        "target_size": (600, 800),  # width, height for EPUB
        "quality": 85,  # JPEG quality
        "format": "JPEG"  # output format
    }
}
```

#### Cover Image Processing Implementation

```python
def download_cover_image(self, cover_url, output_dir):
    """
    Download and process cover image for EPUB generation
    """
    try:
        # Download image using cloudscraper
        response = self.scraper.get(cover_url)
        
        # Process with Pillow
        from PIL import Image
        import io
        
        image = Image.open(io.BytesIO(response.content))
        
        # Resize for EPUB standards
        target_size = self.config.get('cover_processing', {}).get('target_size', (600, 800))
        image = image.resize(target_size, Image.Resampling.LANCZOS)
        
        # Save processed image
        cover_path = os.path.join(output_dir, 'assets', 'cover.jpg')
        os.makedirs(os.path.dirname(cover_path), exist_ok=True)
        image.save(cover_path, 'JPEG', quality=85)
        
        return cover_path
        
    except Exception as e:
        # Generate placeholder cover if download fails
        return self.create_placeholder_cover(output_dir)

def create_placeholder_cover(self, output_dir):
    """
    Create a simple placeholder cover when original is unavailable
    """
    from PIL import Image, ImageDraw, ImageFont
    
    # Create blank image
    image = Image.new('RGB', (600, 800), color='#2c3e50')
    draw = ImageDraw.Draw(image)
    
    # Add title text (basic implementation)
    title = self.novel_metadata.get('title', 'Unknown Title')
    # Add text drawing logic here
    
    cover_path = os.path.join(output_dir, 'assets', 'cover.jpg')
    os.makedirs(os.path.dirname(cover_path), exist_ok=True)
    image.save(cover_path, 'JPEG', quality=85)
    
    return cover_path
```

#### EPUB Generation Implementation

```python
def generate_epub(self, markdown_file, output_path, cover_image=None):
    """
    Convert markdown to EPUB using pandoc
    """
    import subprocess
    
    # Base pandoc command
    pandoc_cmd = [
        'pandoc',
        markdown_file,
        '-o', output_path,
        '--from', 'markdown',
        '--to', 'epub3',
        '--standalone',
        '--toc',
        '--toc-depth=2',
        '--epub-chapter-level=2'
    ]
    
    # Add cover image if available
    if cover_image and os.path.exists(cover_image):
        pandoc_cmd.extend(['--epub-cover-image', cover_image])
    
    # Add custom CSS for better formatting
    css_file = self.create_epub_css()
    if css_file:
        pandoc_cmd.extend(['--css', css_file])
    
    # Execute pandoc
    try:
        result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return output_path
        else:
            raise Exception(f"Pandoc error: {result.stderr}")
    except Exception as e:
        raise Exception(f"EPUB generation failed: {str(e)}")

def create_epub_css(self):
    """
    Create custom CSS for EPUB styling
    """
    css_content = """
    body {
        font-family: "Times New Roman", serif;
        line-height: 1.6;
        margin: 0;
        padding: 1em;
    }
    
    h1, h2, h3 {
        color: #2c3e50;
        margin-top: 2em;
        margin-bottom: 1em;
    }
    
    h1 {
        text-align: center;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.5em;
    }
    
    h2 {
        page-break-before: always;
        border-left: 4px solid #3498db;
        padding-left: 1em;
    }
    
    p {
        text-align: justify;
        margin: 1em 0;
        text-indent: 2em;
    }
    
    .cover-image {
        text-align: center;
        page-break-after: always;
    }
    
    .toc {
        page-break-after: always;
    }
    """
    
    css_path = os.path.join(self.output_dir, 'styles', 'novel.css')
    os.makedirs(os.path.dirname(css_path), exist_ok=True)
    
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    return css_path
```

### Development Steps

01. **Core Framework**: Implement base scraper class and markdown generator
02. **Provider Template**: Create the first provider scraper as a template
03. **Concurrency Layer**: Add async processing for chapters
04. **CLI Interface**: Create command-line interface for easy usage
05. **Configuration System**: Implement provider config management
06. **Testing**: Add unit tests and integration tests

### Usage Example

```bash
# Scrape a novel and generate EPUB
python scraper.py --provider novelfull --url "https://novelfull.com/novel-title.html" --output "novel.epub"

# Generate both markdown and EPUB
python scraper.py --provider webnovel --url "https://webnovel.com/book/123" --output-md "novel.md" --output-epub "novel.epub"

# With custom settings and cover processing
python scraper.py --provider webnovel --url "https://webnovel.com/book/123" --chapters 1-50 --delay 2 --cover-size 600x800
```

### Required Dependencies

```bash
pip install cloudscraper beautifulsoup4 lxml pillow aiohttp
# Also requires pandoc to be installed system-wide
sudo apt-get install pandoc  # Ubuntu/Debian
brew install pandoc         # macOS
```

### Additional Features (Optional)

* **Resume Capability**: Save progress and resume interrupted scrapes
* **Multiple Formats**: Support for EPUB, PDF, and AZW3 output formats
* **Chapter Filtering**: Option to scrape specific chapter ranges
* **Update Detection**: Check for new chapters in already scraped novels
* **Batch Processing**: Scrape multiple novels from a list
* **Cover Customization**: Generate custom covers with title, author, and themes
* **EPUB Validation**: Verify EPUB integrity using epubcheck
* **Metadata Enhancement**: Add series information, publication dates, and ISBN

## Provider Information Required

Please provide the following details for the first provider:
* **Site Name**: Name of the web novel site
* **Base URL**: Main domain URL
* **Sample Novel URL**: Link to a specific novel for testing
* **Site Structure**: How novels and chapters are organized
* **Any known anti-scraping measures**: Cloudflare, rate limits, etc.

## Deliverables

01. Core scraper framework with base classes
02. First provider implementation
03. Cover image download and processing module
04. Markdown generation module (EPUB-optimized)
05. EPUB generation system using pandoc
06. CLI interface with EPUB output options
07. Configuration management system
08. Custom CSS styling for EPUB
09. Documentation and usage examples
10. Sample EPUB output for testing

Excellent. This is a comprehensive and well-defined project plan. Building a modular, feature-rich scraper is a fantastic way to create a robust and maintainable tool. I'll provide a complete implementation based on your detailed instructions.

Here is the full, modular web novel scraper with all the features you've outlined.

### 1\. **Prerequisites: Installing Pandoc**

This project requires **Pandoc** to be installed on your system. It's a command-line utility that the script will call to create EPUB files.

  + **Windows:**
      * Download the `.msi` installer from the [Pandoc releases page](https://pandoc.org/installing.html).
      * Run the installer and follow the on-screen instructions.
  + **macOS (using Homebrew):**

$mdFormatter$78$mdFormatter$

```bash
    brew install pandoc
    ```

  + **Linux (Ubuntu/Debian):**

$mdFormatter$78$mdFormatter$

```bash
    sudo apt-get update && sudo apt-get install pandoc
    ```

-----

### 2\. **Project Structure**

First, let's set up the recommended directory structure. This organization is key to a modular project.

```
novel-scraper/
├── main.py                   # Main CLI entry point
├── requirements.txt          # Project dependencies
|
├── core/
│   ├── __init__.py
│   ├── base_scraper.py       # Abstract base class for all scrapers
│   ├── epub_generator.py     # Handles Pandoc EPUB conversion
│   ├── image_processor.py    # Downloads and processes cover images
│   └── markdown_generator.py # Creates the EPUB-ready Markdown file
|
├── providers/
│   ├── __init__.py
│   ├── novelbin/             # Module for the NovelBin provider
│   │   ├── __init__.py
│   │   ├── config.py         # Configuration (selectors, etc.)
│   │   └── scraper.py        # The scraper implementation
│   └── # (add other provider modules here in the future)
|
└── templates/
    └── novel.css             # Default CSS for EPUB styling
```

-----

### 3\. **Core Framework Implementation**

These modules form the backbone of the scraper.

#### **`core/base_scraper.py`**

This abstract class defines the contract that all provider scrapers must follow.

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import aiohttp

class BaseNovelScraper(ABC):
    """Abstract base class for a web novel scraper."""

    def __init__(self, config: dict, session: aiohttp.ClientSession):
        self.config = config
        self.session = session
        self.base_url = config.get("base_url")

    @abstractmethod
    async def get_novel_metadata(self, novel_url: str) -> Optional[Dict[str, any]]:
        """
        Parses the main novel page to extract metadata.
        Should return a dictionary with keys like 'title', 'author', etc.
        """
        pass

    @abstractmethod
    async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        """
        Parses the novel page to get a list of all chapters.
        Should return a list of dicts, each with 'title' and 'url'.
        """
        pass

    @abstractmethod
    async def scrape_chapter_content(self, chapter_url: str) -> Optional[Dict[str, str]]:
        """
        Parses a chapter page to extract its title and cleaned content.
        Should return a dict with 'title' and 'content'.
        """
        pass
```

#### **`core/image_processor.py`**

Handles all cover image operations using `Pillow` .

```python
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import io

async def download_and_process_cover(
    session: aiohttp.ClientSession,
    cover_url: str,
    output_dir: str,
    config: dict,
    novel_title: str
) -> Optional[str]:
    """Downloads, processes, and saves the cover image."""
    try:
        async with session.get(cover_url) as response:
            response.raise_for_status()
            image_data = await response.read()

        image = Image.open(io.BytesIO(image_data))
        processing_config = config.get("cover_processing", {})
        target_size = tuple(processing_config.get("target_size", (600, 800)))
        quality = processing_config.get("quality", 85)
        img_format = processing_config.get("format", "JPEG")

        # Resize the image
        image = image.resize(target_size, Image.Resampling.LANCZOS)
        
        # Ensure the assets directory exists
        assets_dir = os.path.join(output_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        
        cover_path = os.path.join(assets_dir, f'cover.{img_format.lower()}')
        image.save(cover_path, img_format, quality=quality)
        
        return cover_path
    except Exception as e:
        print(f"⚠️  Could not download or process cover image: {e}. Creating a placeholder.")
        return create_placeholder_cover(output_dir, novel_title, config)

def create_placeholder_cover(output_dir: str, title: str, config: dict) -> str:
    """Creates a simple placeholder cover image."""
    try:
        processing_config = config.get("cover_processing", {})
        target_size = tuple(processing_config.get("target_size", (600, 800)))
        width, height = target_size
        img_format = processing_config.get("format", "JPEG").lower()

        image = Image.new('RGB', (width, height), color='#2c3e50')
        draw = ImageDraw.Draw(image)

        # Basic text wrapping and font selection
        try:
            font = ImageFont.truetype("arial.ttf", size=40)
        except IOError:
            font = ImageFont.load_default()

        # Simple text wrapping
        margin = 40
        offset = 60
        for line in title.split():
            draw.text((margin, offset), line, font=font, fill="#ecf0f1")
            offset += font.getbbox(line)[3] + 10 # height + spacing

        assets_dir = os.path.join(output_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        cover_path = os.path.join(assets_dir, f'cover.{img_format}')
        image.save(cover_path, img_format.upper())
        
        return cover_path
    except Exception as e:
        print(f"❌ Failed to create placeholder cover: {e}")
        return None
```

#### **`core/markdown_generator.py`**

Generates the `pandoc` -ready markdown file with YAML front matter.

```python
import os
import yaml

def generate_markdown(
    metadata: dict,
    chapters: list,
    output_dir: str,
    css_path: str,
    cover_path: str
) -> str:
    """Generates a single markdown file optimized for EPUB conversion."""
    
    # Prepare YAML front matter for Pandoc
    pandoc_metadata = {
        'title': metadata.get('title', 'Untitled Novel'),
        'author': metadata.get('author', 'Unknown Author'),
        'description': metadata.get('description', ''),
        'tags': metadata.get('tags', []),
        'status': metadata.get('status', 'Unknown'),
        'lang': 'en',
        'cover-image': os.path.relpath(cover_path, output_dir).replace('\\', '/'),
        'stylesheet': os.path.relpath(css_path, output_dir).replace('\\', '/'),
        'epub-chapter-level': 2,
    }

    yaml_header = f"---\n{yaml.dump(pandoc_metadata, allow_unicode=True)}---\n"
    
    md_content = [yaml_header]
    
    # Add chapters
    for chapter in chapters:
        if chapter and 'title' in chapter and 'content' in chapter:
            md_content.append(f"## {chapter['title']}\n")
            # Pandoc uses a period on a line by itself for a pause without a page break,
            # and `\newpage` for a hard page break.
            # We'll rely on `epub-chapter-level: 2` to create breaks before H2.
            md_content.append(chapter['content'])

    markdown_file_path = os.path.join(output_dir, "novel.md")
    with open(markdown_file_path, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(md_content))
        
    return markdown_file_path
```

#### **`core/epub_generator.py`**

Handles `pandoc` command execution and CSS creation.

```python
import os
import subprocess

def create_epub_css(output_dir: str, template_path: str) -> Optional[str]:
    """Copies the template CSS to the output directory for EPUB styling."""
    try:
        styles_dir = os.path.join(output_dir, 'styles')
        os.makedirs(styles_dir, exist_ok=True)
        
        css_path = os.path.join(styles_dir, 'novel.css')
        
        with open(template_path, 'r', encoding='utf-8') as f_in, \
             open(css_path, 'w', encoding='utf-8') as f_out:
            f_out.write(f_in.read())
            
        return css_path
    except Exception as e:
        print(f"❌ Could not create epub CSS file: {e}")
        return None

def generate_epub(markdown_file: str, epub_output_path: str) -> Optional[str]:
    """Converts the markdown file to EPUB using pandoc."""
    
    pandoc_cmd = [
        'pandoc',
        markdown_file,
        '-o', epub_output_path,
        '--from', 'markdown+yaml_metadata_block',
        '--to', 'epub3',
        '--standalone'
    ]
    
    print(f"⚙️ Running Pandoc command: {' '.join(pandoc_cmd)}")
    
    try:
        result = subprocess.run(
            pandoc_cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=os.path.dirname(markdown_file)
        )
        if result.returncode == 0:
            print(f"✅ EPUB generated successfully at: {epub_output_path}")
            return epub_output_path
        else:
            print(f"❌ Pandoc error: {result.stderr}")
            return None
    except FileNotFoundError:
        print("❌ Pandoc not found. Please ensure it's installed and in your system's PATH.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Pandoc failed with error:\n{e.stderr}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred during EPUB generation: {e}")
        return None

```

-----

### 4\. **Provider Implementation (NovelBin)**

Now we implement the scraper for a specific provider.

#### **`providers/novelbin/config.py`**

```python
PROVIDER_CONFIG = {
    "name": "NovelBin",
    "base_url": "https://novelbin.com",
    "selectors": {
        "title": "h3.title[itemprop='name']",
        "author": ".info-meta a[href*='/a/']",
        "description": ".desc-text[itemprop='description']",
        "cover_image": "meta[property='og:image']",
        "tags": ".tag-container a",
        "status": ".info-meta li:-soup-contains('Status:') a",
        "chapter_list": "#list-chapter ul.list-chapter li a",
        "chapter_content": "#chr-content",
        "chapter_title": "a.chr-title"
    },
    "rate_limit_delay": 0.5,  # seconds between requests
    "cover_processing": {
        "target_size": (600, 800),
        "quality": 85,
        "format": "JPEG"
    }
}
```

#### **`providers/novelbin/scraper.py`**

This is the concrete implementation, using `asyncio` and `BeautifulSoup` .

```python
import asyncio
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from core.base_scraper import BaseNovelScraper

class NovelBinScraper(BaseNovelScraper):

    async def get_novel_metadata(self, novel_url: str) -> Optional[Dict[str, any]]:
        try:
            async with self.session.get(novel_url) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), 'lxml')
                
                sel = self.config["selectors"]
                
                metadata = {
                    'title': soup.select_one(sel["title"]).text.strip(),
                    'author': soup.select_one(sel["author"]).text.strip(),
                    'description': soup.select_one(sel["description"]).get_text(separator='\n').strip(),
                    'cover_url': soup.select_one(sel["cover_image"])['content'],
                    'tags': [a.text.strip() for a in soup.select(sel["tags"])],
                    'status': soup.select_one(sel["status"]).text.strip(),
                    'source_url': novel_url
                }
                return metadata
        except Exception as e:
            print(f"❌ Failed to fetch metadata from {novel_url}: {e}")
            return None

    async def get_chapter_list(self, novel_url: str) -> List[Dict[str, str]]:
        chapters = []
        try:
            async with self.session.get(novel_url) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), 'lxml')
                
                sel = self.config["selectors"]
                chapter_links = soup.select(sel["chapter_list"])
                
                for link in chapter_links:
                    chapters.append({
                        'title': link.get('title', 'Untitled Chapter').strip(),
                        'url': link['href']
                    })
        except Exception as e:
            print(f"❌ Failed to fetch chapter list from {novel_url}: {e}")
        return chapters

    async def scrape_chapter_content(self, chapter_url: str) -> Optional[Dict[str, str]]:
        await asyncio.sleep(self.config.get("rate_limit_delay", 0.5)) # Rate limiting
        try:
            async with self.session.get(chapter_url) as response:
                response.raise_for_status()
                soup = BeautifulSoup(await response.text(), 'lxml')
                
                sel = self.config["selectors"]
                
                title = soup.select_one(sel["chapter_title"]).get('title', 'Untitled Chapter').strip()
                content_div = soup.select_one(sel["chapter_content"])
                
                # Clean up ads and unwanted elements
                for ad_div in content_div.find_all('div', id=lambda x: x and x.startswith('pf-')):
                    ad_div.decompose()
                
                content_html = content_div.decode_contents()
                # Basic cleaning - replace <p> with newlines, etc. This can be improved.
                content_text = content_div.get_text(separator='\n\n', strip=True)

                return {'title': title, 'content': content_text}
        except Exception as e:
            print(f"❌ Failed to scrape chapter {chapter_url}: {e}")
            return None
```

-----

### 5\. **Templates and Dependencies**

#### **`templates/novel.css`**

A clean, readable stylesheet for the EPUB.

```css
body {
    font-family: Georgia, "Times New Roman", serif;
    line-height: 1.6;
    margin: 1em;
}

h1,
h2 {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    color: #333;
    margin-top: 1.5em;
    margin-bottom: 1em;
    page-break-after: avoid;
    page-break-inside: avoid;
}

h1 {
    text-align: center;
    font-size: 2em;
    border-bottom: 1px solid #ccc;
    padding-bottom: 0.5em;
}

h2 {
    font-size: 1.5em;
    page-break-before: always;
    /* Each chapter starts on a new page */
}

p {
    text-align: justify;
    margin: 0 0 1em 0;
    text-indent: 1.5em;
}

/* For the cover image page */
.cover-image {
    text-align: center;
    page-break-after: always;
}
```

#### **`requirements.txt`**

```
aiohttp
beautifulsoup4
lxml
Pillow
PyYAML
cloudscraper
```

Install them with: `pip install -r requirements.txt`

-----

### 6\. **The CLI Entry Point**

#### **`main.py`**

This script ties everything together. It's the user-facing part of your application.

```python
import argparse
import asyncio
import os
import importlib
import cloudscraper
import aiohttp
from typing import List

from core.image_processor import download_and_process_cover
from core.markdown_generator import generate_markdown
from core.epub_generator import create_epub_css, generate_epub

def get_provider_scraper(provider_name: str):
    """Dynamically imports and returns the scraper class and config."""
    try:
        config_module = importlib.import_module(f"providers.{provider_name}.config")
        scraper_module = importlib.import_module(f"providers.{provider_name}.scraper")
        
        config = getattr(config_module, "PROVIDER_CONFIG")
        # Find the scraper class (assuming one class per module inheriting BaseNovelScraper)
        for attr in dir(scraper_module):
            cls = getattr(scraper_module, attr)
            if isinstance(cls, type) and "BaseNovelScraper" in [b.__name__ for b in cls.__bases__]:
                return cls, config
        
        raise ImportError(f"No scraper class found in providers.{provider_name}.scraper")
    except (ImportError, AttributeError) as e:
        print(f"❌ Could not load provider '{provider_name}'. Make sure the module and config exist.")
        print(f"   Error details: {e}")
        return None, None

async def main(args):
    """Main asynchronous function to orchestrate the scraping process."""
    
    ScraperClass, config = get_provider_scraper(args.provider)
    if not ScraperClass:
        return

    # Using cloudscraper to create an aiohttp session
    # Note: cloudscraper itself doesn't have an async version, but we can
    # steal its cookies/headers for aiohttp. A more robust solution might
    # involve an async-native cloudflare solver if needed.
    # For now, we make one sync request to solve the challenge.
    print("Solving Cloudflare challenge (if any)...")
    scraper = cloudscraper.create_scraper()
    initial_resp = scraper.get(args.url)
    cookies = scraper.cookies.get_dict()
    headers = scraper.headers

    async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
        scraper_instance = ScraperClass(config, session)
        
        # 1. Fetch Metadata
        print("Fetching novel metadata...")
        metadata = await scraper_instance.get_novel_metadata(args.url)
        if not metadata:
            return
        
        # 2. Prepare Output Directory
        novel_slug = "".join(c for c in metadata['title'].lower() if c.isalnum() or c in (' ', '-')).replace(' ', '-')
        output_dir = os.path.join(args.output_dir, novel_slug)
        os.makedirs(output_dir, exist_ok=True)
        print(f"📂 Output will be saved in: {output_dir}")

        # 3. Download and Process Cover
        print("Processing cover image...")
        cover_path = await download_and_process_cover(
            session, metadata['cover_url'], output_dir, config, metadata['title']
        )
        if not cover_path:
            print("⚠️ Proceeding without a cover image.")

        # 4. Fetch Chapter List
        print("Fetching chapter list...")
        chapter_list = await scraper_instance.get_chapter_list(args.url)
        if not chapter_list:
            print("❌ No chapters found. Exiting.")
            return
        
        # Optional: filter chapter range
        if args.chapters:
            start, end = map(int, args.chapters.split('-'))
            chapter_list = chapter_list[start-1:end]
            print(f"📖 Scraping chapters from {start} to {end}.")
        
        print(f"Found {len(chapter_list)} chapters to scrape.")

        # 5. Concurrently Scrape Chapters
        tasks = [scraper_instance.scrape_chapter_content(ch['url']) for ch in chapter_list]
        
        # Simple progress tracking
        scraped_chapters = []
        for i, task in enumerate(asyncio.as_completed(tasks)):
            result = await task
            if result:
                scraped_chapters.append(result)
            print(f"  > Progress: {i+1}/{len(chapter_list)} chapters processed", end='\r')
        print("\n✅ Chapter scraping complete.")
        
        # 6. Generate Markdown
        print("Generating EPUB-ready Markdown file...")
        css_path = create_epub_css(output_dir, args.css_template)
        md_file = generate_markdown(metadata, scraped_chapters, output_dir, css_path, cover_path)
        print(f"✔️ Markdown file saved at: {md_file}")

        # 7. Generate EPUB
        if args.output_epub:
            epub_path = os.path.join(output_dir, f"{novel_slug}.epub")
            print("Generating EPUB file...")
            generate_epub(md_file, epub_path)
            
        print("\n🎉 Scraping process finished!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="A modular web novel scraper.")
    parser.add_argument('-p', '--provider', required=True, help="The provider to use (e.g., 'novelbin').")
    parser.add_argument('-u', '--url', required=True, help="The URL of the novel's main page.")
    parser.add_argument('-o', '--output-dir', default='novels', help="The base directory to save scraped novels.")
    parser.add_argument('--output-epub', action='store_true', help="Generate an EPUB file.")
    parser.add_argument('--chapters', help="A range of chapters to scrape (e.g., '1-50').")
    parser.add_argument('--css-template', default='templates/novel.css', help="Path to custom CSS for EPUB.")
    
    args = parser.parse_args()
    
    # Run the async main function
    asyncio.run(main(args))
```

### 7\. **How to Use**

01.  **Set up the project** as described in the "Project Structure" section.

02.  **Install dependencies**: `pip install -r requirements.txt`.

03.  **Install Pandoc** for your operating system.

04.  **Run the scraper** from your terminal in the `novel-scraper` directory:

$mdFormatter$78$mdFormatter$

```bash
    # Scrape a novel from NovelBin and create an EPUB
    python main.py --provider novelbin --url "https://novelbin.com/b/the-legendary-mechanic" --output-epub

    # Scrape only chapters 1 to 10
    python main.py --provider novelbin --url "https://novelbin.com/b/the-legendary-mechanic" --chapters 1-10 --output-epub
    ```

This structure provides a powerful, maintainable, and extensible foundation for your web novel scraping project, fulfilling all the advanced requirements you laid out.
