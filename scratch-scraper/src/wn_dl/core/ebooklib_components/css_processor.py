"""
CSS processor for EbookLib EPUB generator.

This module handles processing and embedding of CSS styles, integrating the
existing novel.css template with ebooklib to maintain consistent styling.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from ebooklib import epub

logger = logging.getLogger(__name__)


class CSSProcessor:
    """
    Handles CSS processing and embedding for EPUB generation using ebooklib.

    Integrates dynamic font selection with CSS generation to maintain
    consistent styling across different font families.
    """

    def __init__(self, config: Dict[str, Any], selected_font: Optional[str] = None):
        """
        Initialize CSS processor with configuration.

        Args:
            config: CSS processing configuration
            selected_font: Selected font family name
        """
        self.config = config
        self.epub_config = config.get("epub", {})
        self.custom_css = self.epub_config.get("custom_css", True)
        self.templates_dir = Path(__file__).parent.parent.parent / "templates"
        self.default_css_path = self.templates_dir / "novel.css"

        # Resolve font selection
        self.selected_font = self._resolve_font_selection(selected_font)

        logger.debug(f"CSSProcessor initialized, default CSS: {self.default_css_path}")
        logger.debug(f"Selected font: {self.selected_font}")

    def _resolve_font_selection(self, requested_font: Optional[str]) -> str:
        """Resolve font selection with fallback logic."""
        from ..font_manager import get_font_manager

        font_manager = get_font_manager()

        # Priority: requested_font > config > default
        if requested_font:
            return font_manager.resolve_font(requested_font)

        # Check config for font preference
        config_font = self.epub_config.get("font_family")
        if config_font:
            return font_manager.resolve_font(config_font)

        # Use system default
        return font_manager.resolve_font(None)

    def create_css_item(
        self, custom_css_file: Optional[str] = None
    ) -> Optional[epub.EpubItem]:
        """
        Create CSS item for EPUB book.

        Args:
            custom_css_file: Optional path to custom CSS file

        Returns:
            EPUB CSS item or None if failed
        """
        try:
            # Determine which CSS to use
            css_content = self._get_css_content(custom_css_file)

            if not css_content:
                logger.error("No CSS content available")
                return None

            # Add font declarations
            font_css = self._get_font_css_declarations()
            if font_css:
                css_content = font_css + "\n\n" + css_content

            # Create CSS item
            css_item = epub.EpubItem(
                uid="style_default",
                file_name="styles/novel.css",
                media_type="text/css",
                content=css_content,
            )

            logger.info("Created CSS item for EPUB")
            return css_item

        except Exception as e:
            logger.error(f"Error creating CSS item: {e}")
            return None

    def _get_css_content(self, custom_css_file: Optional[str] = None) -> str:
        """
        Get CSS content from custom file or default template.

        Args:
            custom_css_file: Optional path to custom CSS file

        Returns:
            CSS content string
        """
        # Try custom CSS file first
        if custom_css_file:
            custom_path = Path(custom_css_file)
            if custom_path.exists():
                try:
                    with open(custom_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    logger.info(f"Using custom CSS file: {custom_css_file}")
                    return content
                except Exception as e:
                    logger.warning(f"Error reading custom CSS file: {e}")

        # Fall back to dynamic CSS generation based on selected font
        if self.custom_css:
            try:
                from ..css_generator import generate_css_for_font

                content = generate_css_for_font(self.selected_font)
                logger.info(f"Using dynamic CSS for font: {self.selected_font}")
                return content
            except Exception as e:
                logger.error(f"Error generating dynamic CSS: {e}")

                # Fallback to static template
                if self.default_css_path.exists():
                    try:
                        with open(self.default_css_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        logger.info(
                            f"Using default CSS template: {self.default_css_path}"
                        )
                        return content
                    except Exception as e2:
                        logger.error(f"Error reading default CSS template: {e2}")

        # Return minimal CSS if nothing else works
        logger.warning("Using minimal fallback CSS")
        return self._get_minimal_css()

    def _get_font_css_declarations(self) -> str:
        """
        Get font CSS declarations from font embedder.

        Returns:
            CSS font declarations string
        """
        try:
            from .font_embedder import FontEmbedder

            font_embedder = FontEmbedder(self.config)
            return font_embedder.get_font_css_declarations()
        except Exception as e:
            logger.error(f"Error getting font CSS declarations: {e}")
            return ""

    def _get_minimal_css(self) -> str:
        """
        Get minimal fallback CSS.

        Returns:
            Minimal CSS content
        """
        return """
/* Minimal EPUB CSS */
body {
    font-family: serif;
    font-size: 100%;
    line-height: 1.5;
    margin: 2%;
}

h1, h2, h3, h4, h5, h6 {
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}

h1 { font-size: 1.8em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.2em; }

p {
    margin: 0;
    text-indent: 1.2em;
    orphans: 2;
    widows: 2;
}

p.first-paragraph {
    text-indent: 0;
}

.scene-break {
    text-align: center;
    margin: 2em 0;
    font-size: 1.2em;
}

.chapter {
    page-break-before: always;
}
"""

    def process_css_for_epub(self, css_content: str) -> str:
        """
        Process CSS content for EPUB compatibility.

        Args:
            css_content: Raw CSS content

        Returns:
            Processed CSS content
        """
        # Remove any @import statements (not supported in EPUB)
        import re

        css_content = re.sub(r"@import[^;]+;", "", css_content)

        # Remove any external URL references
        css_content = re.sub(r'url\(["\']?https?://[^)]+\)', "", css_content)

        # Ensure font paths are relative
        css_content = re.sub(r'url\(["\']?/?fonts/', 'url("fonts/', css_content)

        return css_content

    def validate_css(self, css_content: str) -> bool:
        """
        Basic CSS validation for EPUB compatibility.

        Args:
            css_content: CSS content to validate

        Returns:
            True if CSS appears valid
        """
        try:
            # Check for basic CSS structure
            if not css_content.strip():
                return False

            # Check for balanced braces
            open_braces = css_content.count("{")
            close_braces = css_content.count("}")

            if open_braces != close_braces:
                logger.warning("CSS has unbalanced braces")
                return False

            # Check for problematic patterns
            problematic_patterns = [
                r"@import\s+url\(",  # External imports
                r"javascript:",  # JavaScript URLs
                r"expression\(",  # IE expressions
            ]

            for pattern in problematic_patterns:
                if re.search(pattern, css_content, re.IGNORECASE):
                    logger.warning(f"CSS contains problematic pattern: {pattern}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating CSS: {e}")
            return False

    def get_css_info(self) -> Dict[str, Any]:
        """
        Get information about available CSS resources.

        Returns:
            Dictionary with CSS information
        """
        info = {
            "default_css_available": self.default_css_path.exists(),
            "default_css_path": str(self.default_css_path),
            "custom_css_enabled": self.custom_css,
        }

        if self.default_css_path.exists():
            try:
                info["default_css_size"] = self.default_css_path.stat().st_size
            except Exception:
                info["default_css_size"] = None

        return info
