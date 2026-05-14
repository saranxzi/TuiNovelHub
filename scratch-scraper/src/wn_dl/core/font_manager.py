"""
Font Management System for EPUB Generation.

This module provides comprehensive font management capabilities including:
- Font discovery and validation
- Font family registry
- CSS generation for selected fonts
- Font embedding for EPUB generation
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FontVariant:
    """Represents a single font variant (e.g., Regular, Bold, Italic)."""

    name: str
    file_path: Path
    weight: str = "normal"  # normal, bold
    style: str = "normal"  # normal, italic


@dataclass
class FontFamily:
    """Represents a complete font family with all variants."""

    name: str
    display_name: str
    variants: Dict[str, FontVariant]

    @property
    def is_complete(self) -> bool:
        """Check if font family has all required variants."""
        required_variants = {"regular", "bold", "italic", "bolditalic"}
        available_variants = set(self.variants.keys())
        return required_variants.issubset(available_variants)

    @property
    def available_variants(self) -> List[str]:
        """Get list of available variant names."""
        return list(self.variants.keys())


class FontManager:
    """Manages font discovery, validation, and selection for EPUB generation."""

    def __init__(self, fonts_dir: Optional[Path] = None):
        """
        Initialize font manager.

        Args:
            fonts_dir: Path to fonts directory. If None, uses default templates/fonts.
        """
        if fonts_dir is None:
            # Default to templates/fonts directory
            current_dir = Path(__file__).parent.parent
            fonts_dir = current_dir / "templates" / "fonts"

        self.fonts_dir = Path(fonts_dir)
        self.font_families: Dict[str, FontFamily] = {}
        self.default_font = "bitter"  # Default font family

        # Initialize font registry
        self._discover_fonts()

    def _discover_fonts(self) -> None:
        """Discover and register all available font families."""
        if not self.fonts_dir.exists():
            logger.warning(f"Fonts directory not found: {self.fonts_dir}")
            return

        # Group font files by family name
        font_groups: Dict[str, List[Path]] = {}

        for font_file in self.fonts_dir.glob("*.ttf"):
            family_name = self._extract_family_name(font_file.name)
            if family_name:
                if family_name not in font_groups:
                    font_groups[family_name] = []
                font_groups[family_name].append(font_file)

        # Create FontFamily objects
        for family_name, font_files in font_groups.items():
            font_family = self._create_font_family(family_name, font_files)
            if font_family:
                self.font_families[family_name.lower()] = font_family
                logger.debug(f"Registered font family: {family_name}")

    def _extract_family_name(self, filename: str) -> Optional[str]:
        """Extract font family name from filename."""
        # Remove extension
        name = filename.replace(".ttf", "").replace(".otf", "")

        # Split on dash or underscore
        parts = name.replace("_", "-").split("-")

        if len(parts) >= 2:
            return parts[0]

        return None

    def _create_font_family(
        self, family_name: str, font_files: List[Path]
    ) -> Optional[FontFamily]:
        """Create FontFamily object from list of font files."""
        variants: Dict[str, FontVariant] = {}

        for font_file in font_files:
            variant_info = self._parse_variant_info(font_file.name)
            if variant_info:
                variant_name, weight, style = variant_info
                variants[variant_name] = FontVariant(
                    name=variant_name, file_path=font_file, weight=weight, style=style
                )

        if variants:
            return FontFamily(
                name=family_name.lower(),
                display_name=family_name.title(),
                variants=variants,
            )

        return None

    def _parse_variant_info(self, filename: str) -> Optional[Tuple[str, str, str]]:
        """Parse variant information from filename."""
        # Remove extension
        name = filename.replace(".ttf", "").replace(".otf", "")

        # Split on dash or underscore
        parts = name.replace("_", "-").split("-")

        if len(parts) < 2:
            return None

        variant_part = "-".join(parts[1:]).lower()

        # Map variant names to CSS properties
        variant_mapping = {
            "regular": ("regular", "normal", "normal"),
            "bold": ("bold", "bold", "normal"),
            "italic": ("italic", "normal", "italic"),
            "bolditalic": ("bolditalic", "bold", "italic"),
            "light": ("light", "300", "normal"),
            "medium": ("medium", "500", "normal"),
            "semibold": ("semibold", "600", "normal"),
        }

        return variant_mapping.get(variant_part)

    def get_available_fonts(self) -> List[str]:
        """Get list of available font family names."""
        return sorted(self.font_families.keys())

    def get_font_family(self, font_name: str) -> Optional[FontFamily]:
        """Get font family by name."""
        return self.font_families.get(font_name.lower())

    def is_font_available(self, font_name: str) -> bool:
        """Check if font family is available."""
        return font_name.lower() in self.font_families

    def validate_font(self, font_name: str) -> Tuple[bool, str]:
        """
        Validate font availability and completeness.

        Returns:
            Tuple of (is_valid, message)
        """
        if not font_name:
            return False, "Font name cannot be empty"

        font_family = self.get_font_family(font_name)
        if not font_family:
            available = ", ".join(self.get_available_fonts())
            return False, f"Font '{font_name}' not found. Available fonts: {available}"

        if not font_family.is_complete:
            missing = {"regular", "bold", "italic", "bolditalic"} - set(
                font_family.available_variants
            )
            return (
                False,
                f"Font '{font_name}' is missing variants: {', '.join(missing)}",
            )

        return True, f"Font '{font_name}' is valid and complete"

    def get_font_info(self, font_name: str) -> Optional[Dict]:
        """Get detailed information about a font family."""
        font_family = self.get_font_family(font_name)
        if not font_family:
            return None

        return {
            "name": font_family.name,
            "display_name": font_family.display_name,
            "variants": font_family.available_variants,
            "is_complete": font_family.is_complete,
            "files": {
                variant: str(font_variant.file_path)
                for variant, font_variant in font_family.variants.items()
            },
        }

    def get_default_font(self) -> str:
        """Get the default font name."""
        return self.default_font

    def set_default_font(self, font_name: str) -> bool:
        """Set the default font if it's available."""
        if self.is_font_available(font_name):
            self.default_font = font_name.lower()
            return True
        return False

    def resolve_font(self, requested_font: Optional[str]) -> str:
        """
        Resolve font name with fallback to default.

        Args:
            requested_font: Requested font name (can be None)

        Returns:
            Valid font name (falls back to default if requested font unavailable)
        """
        if requested_font and self.is_font_available(requested_font):
            return requested_font.lower()

        # Fallback to default
        if self.is_font_available(self.default_font):
            return self.default_font

        # Last resort: use first available font
        available_fonts = self.get_available_fonts()
        if available_fonts:
            return available_fonts[0]

        raise RuntimeError("No fonts available in the system")


# Global font manager instance
_font_manager: Optional[FontManager] = None


def get_font_manager() -> FontManager:
    """Get the global font manager instance."""
    global _font_manager
    if _font_manager is None:
        _font_manager = FontManager()
    return _font_manager


def list_available_fonts() -> List[str]:
    """Convenience function to list available fonts."""
    return get_font_manager().get_available_fonts()


def validate_font_selection(font_name: str) -> Tuple[bool, str]:
    """Convenience function to validate font selection."""
    return get_font_manager().validate_font(font_name)


def resolve_font_name(requested_font: Optional[str]) -> str:
    """Convenience function to resolve font name with fallback."""
    return get_font_manager().resolve_font(requested_font)
