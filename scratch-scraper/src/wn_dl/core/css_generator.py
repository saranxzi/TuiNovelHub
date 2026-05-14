"""
CSS Generation System for Dynamic Font Selection.

This module generates CSS files dynamically based on selected font families,
ensuring proper @font-face declarations and font-family references.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from .font_manager import FontFamily, get_font_manager

logger = logging.getLogger(__name__)


class CSSGenerator:
    """Generates CSS files with dynamic font selection."""

    def __init__(self):
        """Initialize CSS generator."""
        self.font_manager = get_font_manager()
        self.base_css_template = self._load_base_css_template()

    def _load_base_css_template(self) -> str:
        """Load the base CSS template."""
        template_path = Path(__file__).parent.parent / "templates" / "novel.css"

        if not template_path.exists():
            logger.error(f"Base CSS template not found: {template_path}")
            return self._get_fallback_css()

        try:
            return template_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to load CSS template: {e}")
            return self._get_fallback_css()

    def _get_fallback_css(self) -> str:
        """Get minimal fallback CSS."""
        return """
@charset "utf-8";

/* Fallback CSS for EPUB generation */
body {
    font-family: serif;
    line-height: 1.6;
    margin: 1em;
}

h1, h2, h3, h4, h5, h6 {
    font-weight: bold;
    margin: 1em 0 0.5em 0;
}

p {
    margin: 0 0 1em 0;
    text-align: justify;
}
"""

    def generate_font_face_declarations(self, font_family: FontFamily) -> str:
        """Generate @font-face declarations for a font family."""
        declarations = []

        # Font weight and style mapping
        variant_mapping = {
            "regular": ("400", "normal"),
            "bold": ("700", "normal"),
            "italic": ("400", "italic"),
            "bolditalic": ("700", "italic"),
            "light": ("300", "normal"),
            "medium": ("500", "normal"),
            "semibold": ("600", "normal"),
        }

        for variant_name, font_variant in font_family.variants.items():
            weight, style = variant_mapping.get(variant_name, ("400", "normal"))

            font_face = f"""@font-face {{
    font-family: "{font_family.display_name}";
    font-weight: {weight};
    font-style: {style};
    src: url('fonts/{font_variant.file_path.name}');
}}"""
            declarations.append(font_face)

        return "\n\n".join(declarations)

    def generate_css_for_font(self, font_name: str) -> str:
        """Generate complete CSS for a specific font."""
        # Resolve font name and get font family
        resolved_font = self.font_manager.resolve_font(font_name)
        font_family = self.font_manager.get_font_family(resolved_font)

        if not font_family:
            logger.warning(
                f"Font family not found: {resolved_font}, using fallback CSS"
            )
            return self._get_fallback_css()

        # Generate font-face declarations
        font_face_declarations = self.generate_font_face_declarations(font_family)

        # Replace font references in base CSS
        css_content = self._replace_font_references(
            self.base_css_template, font_family.display_name
        )

        # Replace the font-face section
        css_content = self._replace_font_face_section(
            css_content, font_face_declarations
        )

        return css_content

    def _replace_font_references(self, css_content: str, font_display_name: str) -> str:
        """Replace font-family references in CSS."""
        # Replace specific font references
        replacements = {
            'font-family: "Bitter"': f'font-family: "{font_display_name}"',
            "font-family: 'Bitter'": f"font-family: '{font_display_name}'",
            "font-family: Bitter": f'font-family: "{font_display_name}"',
        }

        for old_ref, new_ref in replacements.items():
            css_content = css_content.replace(old_ref, new_ref)

        # Update CSS comments to reflect the selected font
        css_content = css_content.replace(
            "- Uses Bitter font for optimal readability",
            f"- Uses {font_display_name} font for optimal readability",
        )
        css_content = css_content.replace(
            "- Embeds Bitter for main text",
            f"- Embeds {font_display_name} for main text",
        )

        return css_content

    def _replace_font_face_section(self, css_content: str, new_font_faces: str) -> str:
        """Replace the @font-face section in CSS."""
        # Find the font-face section
        start_marker = "2. FONT EMBEDDING (@font-face)"
        end_marker = "3. CORE TYPOGRAPHY & LAYOUT"

        start_pos = css_content.find(start_marker)
        end_pos = css_content.find(end_marker)

        if start_pos == -1 or end_pos == -1:
            logger.warning(
                "Could not find font-face section markers, appending font declarations"
            )
            return css_content + "\n\n" + new_font_faces

        # Find the actual start of font-face declarations
        section_start = css_content.find("@font-face", start_pos)
        if section_start == -1:
            section_start = css_content.find("*/", start_pos) + 2

        # Find the end of the section (before the next section comment)
        section_end = css_content.rfind("*/", section_start, end_pos)
        if section_end == -1:
            section_end = end_pos
        else:
            section_end = css_content.find("\n", section_end) + 1

        # Replace the section
        before = css_content[:section_start].rstrip()
        after = css_content[section_end:].lstrip()

        return f"{before}\n{new_font_faces}\n\n{after}"

    def save_css_file(self, font_name: str, output_path: Path) -> bool:
        """Generate and save CSS file for a specific font."""
        try:
            css_content = self.generate_css_for_font(font_name)
            output_path.write_text(css_content, encoding="utf-8")
            logger.info(f"Generated CSS file for font '{font_name}': {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save CSS file: {e}")
            return False

    def get_supported_fonts(self) -> Dict[str, str]:
        """Get mapping of supported font names to display names."""
        fonts = {}
        for font_name in self.font_manager.get_available_fonts():
            font_family = self.font_manager.get_font_family(font_name)
            if font_family and font_family.is_complete:
                fonts[font_name] = font_family.display_name
        return fonts


# Convenience functions
def generate_css_for_font(font_name: str) -> str:
    """Generate CSS content for a specific font."""
    generator = CSSGenerator()
    return generator.generate_css_for_font(font_name)


def save_font_css(font_name: str, output_path: Path) -> bool:
    """Generate and save CSS file for a specific font."""
    generator = CSSGenerator()
    return generator.save_css_file(font_name, output_path)


def get_available_font_css() -> Dict[str, str]:
    """Get mapping of available fonts for CSS generation."""
    generator = CSSGenerator()
    return generator.get_supported_fonts()
