"""
EbookLib EPUB generator components.

This package contains the modular components for the ebooklib-based EPUB generator,
providing an alternative to pandoc for large novel processing.
"""

from .chapter_processor import ChapterProcessor
from .css_processor import CSSProcessor
from .font_embedder import FontEmbedder
from .markdown_parser import MarkdownParser
from .metadata_handler import MetadataHandler

__all__ = [
    "ChapterProcessor",
    "CSSProcessor", 
    "FontEmbedder",
    "MarkdownParser",
    "MetadataHandler",
]
