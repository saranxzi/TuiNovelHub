"""
Font embedder for EbookLib EPUB generator.

This module handles embedding of custom fonts from the templates/fonts directory
into EPUB files using ebooklib. Supports dynamic font selection.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ebooklib import epub

from ..font_manager import get_font_manager

logger = logging.getLogger(__name__)


class FontEmbedder:
    """
    Handles font embedding for EPUB generation using ebooklib.

    Supports dynamic font selection and embeds the selected font family
    from the templates/fonts directory.
    """

    def __init__(self, config: Dict[str, Any], selected_font: Optional[str] = None):
        """
        Initialize font embedder with configuration.

        Args:
            config: Font embedding configuration
            selected_font: Name of the font family to embed (defaults to config or system default)
        """
        self.config = config
        self.templates_dir = Path(__file__).parent.parent.parent / "templates"
        self.fonts_dir = self.templates_dir / "fonts"
        self.font_manager = get_font_manager()

        # Resolve font selection
        self.selected_font = self._resolve_font_selection(selected_font)

        logger.debug(f"FontEmbedder initialized, fonts directory: {self.fonts_dir}")
        logger.debug(f"Selected font: {self.selected_font}")

    def _resolve_font_selection(self, requested_font: Optional[str]) -> str:
        """Resolve font selection with fallback logic."""
        # Priority: requested_font > config > default
        if requested_font:
            return self.font_manager.resolve_font(requested_font)

        # Check config for font preference
        config_font = self.config.get("font_family")
        if config_font:
            return self.font_manager.resolve_font(config_font)

        # Use system default
        return self.font_manager.resolve_font(None)

    def embed_fonts(self, book: epub.EpubBook) -> List[epub.EpubItem]:
        """
        Embed selected font family into the EPUB book.

        Args:
            book: EPUB book object to add fonts to

        Returns:
            List of embedded font items
        """
        embedded_fonts = []

        if not self.fonts_dir.exists():
            logger.warning(f"Fonts directory not found: {self.fonts_dir}")
            return embedded_fonts

        # Get font family information
        font_family = self.font_manager.get_font_family(self.selected_font)
        if not font_family:
            logger.error(f"Font family not found: {self.selected_font}")
            return embedded_fonts

        # Get font files for the selected family
        font_files = []
        for variant in font_family.variants.values():
            if variant.file_path.exists():
                font_files.append(variant.file_path)
            else:
                logger.warning(f"Font file not found: {variant.file_path}")

        if not font_files:
            logger.warning(f"No font files found for family: {self.selected_font}")
            return embedded_fonts

        logger.info(
            f"Embedding {len(font_files)} font files for '{font_family.display_name}' family"
        )

        for font_file in font_files:
            font_item = self._create_font_item(font_file)
            if font_item:
                book.add_item(font_item)
                embedded_fonts.append(font_item)
                logger.debug(f"Embedded font: {font_file.name}")

        logger.info(
            f"Successfully embedded {len(embedded_fonts)} fonts for '{font_family.display_name}'"
        )
        return embedded_fonts

    def get_selected_font_info(self) -> Dict[str, Any]:
        """Get information about the selected font family."""
        font_family = self.font_manager.get_font_family(self.selected_font)
        if font_family:
            return {
                "name": font_family.name,
                "display_name": font_family.display_name,
                "variants": font_family.available_variants,
                "is_complete": font_family.is_complete,
            }
        return {
            "name": self.selected_font,
            "display_name": self.selected_font.title(),
            "variants": [],
            "is_complete": False,
        }

    def _create_font_item(self, font_file: Path) -> epub.EpubItem:
        """
        Create an EPUB font item from a font file.

        Args:
            font_file: Path to the font file

        Returns:
            EPUB font item or None if failed
        """
        try:
            # Read font file content
            with open(font_file, "rb") as f:
                font_content = f.read()

            # Create unique ID from filename
            font_id = f"font_{font_file.stem.lower().replace('-', '_')}"

            # Create font item
            font_item = epub.EpubItem(
                uid=font_id,
                file_name=f"fonts/{font_file.name}",
                media_type="font/ttf",
                content=font_content,
            )

            return font_item

        except Exception as e:
            logger.error(f"Error creating font item for {font_file.name}: {e}")
            return None

    def get_font_css_declarations(self) -> str:
        """
        Generate CSS @font-face declarations for embedded fonts.

        Returns:
            CSS string with @font-face declarations
        """
        css_declarations = []

        if not self.fonts_dir.exists():
            logger.warning("Fonts directory not found, no CSS declarations generated")
            return ""

        # Define font families and their corresponding files
        font_families = {
            "Bitter": {
                "regular": "Bitter-Regular.ttf",
                "italic": "Bitter-Italic.ttf",
                "bold": "Bitter-Bold.ttf",
                "bold_italic": "Bitter-BoldItalic.ttf",
            },
            "FiraCode Nerd Font Mono": {
                "regular": "FiraCodeNerdFontMono-Regular.ttf",
                "bold": "FiraCodeNerdFontMono-Bold.ttf",
                "light": "FiraCodeNerdFontMono-Light.ttf",
                "medium": "FiraCodeNerdFontMono-Medium.ttf",
                "retina": "FiraCodeNerdFontMono-Retina.ttf",
                "semibold": "FiraCodeNerdFontMono-SemiBold.ttf",
            },
        }

        # Generate @font-face declarations
        for family_name, variants in font_families.items():
            for variant, filename in variants.items():
                font_path = self.fonts_dir / filename
                if font_path.exists():
                    css_declaration = self._generate_font_face_declaration(
                        family_name, variant, filename
                    )
                    css_declarations.append(css_declaration)

        css_content = "\n\n".join(css_declarations)
        logger.debug(
            f"Generated CSS declarations for {len(css_declarations)} font variants"
        )

        return css_content

    def _generate_font_face_declaration(
        self, family_name: str, variant: str, filename: str
    ) -> str:
        """
        Generate a single @font-face CSS declaration.

        Args:
            family_name: Font family name
            variant: Font variant (regular, bold, italic, etc.)
            filename: Font filename

        Returns:
            CSS @font-face declaration
        """
        # Map variants to CSS properties
        variant_properties = {
            "regular": {"weight": "400", "style": "normal"},
            "italic": {"weight": "400", "style": "italic"},
            "bold": {"weight": "700", "style": "normal"},
            "bold_italic": {"weight": "700", "style": "italic"},
            "light": {"weight": "300", "style": "normal"},
            "medium": {"weight": "500", "style": "normal"},
            "retina": {"weight": "450", "style": "normal"},
            "semibold": {"weight": "600", "style": "normal"},
        }

        properties = variant_properties.get(
            variant, {"weight": "400", "style": "normal"}
        )

        css_declaration = f"""@font-face {{
    font-family: "{family_name}";
    font-weight: {properties["weight"]};
    font-style: {properties["style"]};
    src: url('fonts/{filename}');
}}"""

        return css_declaration

    def get_available_fonts(self) -> List[str]:
        """
        Get list of available font files.

        Returns:
            List of font filenames
        """
        if not self.fonts_dir.exists():
            return []

        font_files = list(self.fonts_dir.glob("*.ttf"))
        return [font_file.name for font_file in font_files]

    def validate_fonts(self) -> bool:
        """
        Validate that required fonts are available.

        Returns:
            True if all required fonts are available
        """
        required_fonts = [
            "Bitter-Regular.ttf",
            "Bitter-Bold.ttf",
            "FiraCodeNerdFontMono-Regular.ttf",
        ]

        if not self.fonts_dir.exists():
            logger.error("Fonts directory not found")
            return False

        missing_fonts = []
        for font_name in required_fonts:
            font_path = self.fonts_dir / font_name
            if not font_path.exists():
                missing_fonts.append(font_name)

        if missing_fonts:
            logger.warning(f"Missing required fonts: {missing_fonts}")
            return False

        logger.info("All required fonts are available")
        return True
