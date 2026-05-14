"""
Image processing module for cover images.

This module handles downloading, resizing, and processing cover images for novels.
"""

import asyncio
import io
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import cloudscraper
from PIL import Image, ImageDraw, ImageFont

from ..utils import clean_filename, create_safe_directory

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Handles image processing operations for novel covers.

    Provides functionality to download, resize, optimize, and create placeholder images.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize image processor with configuration.

        Args:
            config: Image processing configuration
        """
        self.config = config.get("images", {})
        self.target_size = tuple(self.config.get("target_size", [600, 800]))
        self.quality = self.config.get("quality", 85)
        self.format = self.config.get("format", "JPEG")
        self.create_placeholder = self.config.get("create_placeholder", True)
        # Enhanced placeholder configuration
        self.placeholder_color = self.config.get("placeholder_color", "#2c3e50")
        self.placeholder_text_color = self.config.get(
            "placeholder_text_color", "#ecf0f1"
        )
        self.placeholder_style = self.config.get(
            "placeholder_style", "gradient"
        )  # gradient, solid, pattern
        self.placeholder_gradient_colors = self.config.get(
            "placeholder_gradient_colors", ["#2c3e50", "#34495e", "#3498db"]
        )
        self.placeholder_border = self.config.get("placeholder_border", True)
        self.placeholder_border_color = self.config.get(
            "placeholder_border_color", "#ecf0f1"
        )
        self.placeholder_border_width = self.config.get("placeholder_border_width", 4)
        self.placeholder_author_text = self.config.get("placeholder_author_text", True)
        self.placeholder_decorative_elements = self.config.get(
            "placeholder_decorative_elements", True
        )

        # Create cloudscraper session for image downloads
        self.session = cloudscraper.create_scraper()

        logger.debug(f"ImageProcessor initialized with target_size: {self.target_size}")

    async def download_and_process_cover(
        self,
        cover_url: str,
        output_dir: Path,
        novel_title: str,
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        Download and process a cover image.

        Args:
            cover_url: URL of the cover image
            output_dir: Directory to save the processed image
            novel_title: Title of the novel (for filename and placeholder)
            filename: Optional custom filename

        Returns:
            Path to the processed image file or None if failed
        """
        if not cover_url:
            logger.warning("No cover URL provided")
            if self.create_placeholder:
                return await self.create_placeholder_cover(
                    output_dir, novel_title, filename
                )
            return None

        try:
            # Create output directory
            if not create_safe_directory(output_dir):
                logger.error(f"Failed to create output directory: {output_dir}")
                return None

            # Generate filename
            if not filename:
                filename = self._generate_filename(novel_title, cover_url)

            output_path = output_dir / filename

            # Download image
            image_data = await self._download_image(cover_url)
            if not image_data:
                logger.warning(f"Failed to download cover image from {cover_url}")
                if self.create_placeholder:
                    return await self.create_placeholder_cover(
                        output_dir, novel_title, filename
                    )
                return None

            # Process image
            processed_path = await self._process_image(image_data, output_path)
            if processed_path:
                logger.info(f"Successfully processed cover image: {processed_path}")
                return str(processed_path)
            else:
                logger.warning("Failed to process cover image")
                if self.create_placeholder:
                    return await self.create_placeholder_cover(
                        output_dir, novel_title, filename
                    )
                return None

        except Exception as e:
            logger.error(f"Error processing cover image: {e}")
            if self.create_placeholder:
                return await self.create_placeholder_cover(
                    output_dir, novel_title, filename
                )
            return None

    async def create_placeholder_cover(
        self,
        output_dir: Path,
        novel_title: str,
        filename: Optional[str] = None,
        author: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create an enhanced placeholder cover image with customizable design.

        Args:
            output_dir: Directory to save the placeholder
            novel_title: Title of the novel
            filename: Optional custom filename
            author: Optional author name to include

        Returns:
            Path to the placeholder image file or None if failed
        """
        try:
            # Create output directory
            if not create_safe_directory(output_dir):
                logger.error(f"Failed to create output directory: {output_dir}")
                return None

            # Generate filename
            if not filename:
                filename = self._generate_filename(novel_title, None, "placeholder")

            output_path = output_dir / filename

            # Create enhanced placeholder image
            image = self._create_enhanced_background()
            draw = ImageDraw.Draw(image)

            # Add border if enabled
            if self.placeholder_border:
                self._add_border(draw, image.size)

            # Add decorative elements if enabled
            if self.placeholder_decorative_elements:
                self._add_decorative_elements(draw, image.size)

            # Add title text with enhanced styling
            self._add_enhanced_text_to_image(draw, novel_title, image.size, author)

            # Save image
            image.save(output_path, self.format, quality=self.quality, optimize=True)

            logger.info(f"Created enhanced placeholder cover: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error creating placeholder cover: {e}")
            return None

    async def _download_image(self, url: str) -> Optional[bytes]:
        """
        Download image from URL.

        Args:
            url: Image URL

        Returns:
            Image data as bytes or None if failed
        """
        try:
            logger.debug(f"Downloading image from: {url}")

            # Use cloudscraper for downloads
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to download image: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e}")
            return None

    async def _process_image(
        self, image_data: bytes, output_path: Path
    ) -> Optional[Path]:
        """
        Process image data and save to file.

        Args:
            image_data: Raw image data
            output_path: Path to save processed image

        Returns:
            Path to processed image or None if failed
        """
        try:
            # Open image
            image = Image.open(io.BytesIO(image_data))

            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Resize image
            image = self._resize_image(image)

            # Save processed image
            image.save(output_path, self.format, quality=self.quality, optimize=True)

            return output_path

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return None

    def _resize_image(self, image: Image.Image) -> Image.Image:
        """
        Resize image to target size while maintaining aspect ratio.

        Args:
            image: PIL Image object

        Returns:
            Resized image
        """
        # Calculate aspect ratios
        original_ratio = image.width / image.height
        target_ratio = self.target_size[0] / self.target_size[1]

        if original_ratio > target_ratio:
            # Image is wider than target ratio
            new_width = self.target_size[0]
            new_height = int(new_width / original_ratio)
        else:
            # Image is taller than target ratio
            new_height = self.target_size[1]
            new_width = int(new_height * original_ratio)

        # Resize image
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create final image with target size and center the resized image
        final_image = Image.new("RGB", self.target_size, (255, 255, 255))

        # Calculate position to center the image
        x = (self.target_size[0] - new_width) // 2
        y = (self.target_size[1] - new_height) // 2

        final_image.paste(resized, (x, y))

        return final_image

    def _add_text_to_image(
        self, draw: ImageDraw.Draw, text: str, image_size: Tuple[int, int]
    ) -> None:
        """
        Add text to image for placeholder covers.

        Args:
            draw: ImageDraw object
            text: Text to add
            image_size: Size of the image
        """
        try:
            # Try to use a nice font, fall back to default
            try:
                font_size = min(image_size) // 20
                font = ImageFont.truetype("arial.ttf", font_size)
            except (OSError, IOError):
                try:
                    font = ImageFont.load_default()
                except:
                    font = None

            if font is None:
                return

            # Wrap text to fit image width
            wrapped_text = self._wrap_text(text, font, image_size[0] - 40)

            # Calculate text position (centered)
            bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (image_size[0] - text_width) // 2
            y = (image_size[1] - text_height) // 2

            # Draw text
            draw.multiline_text(
                (x, y),
                wrapped_text,
                fill=self.placeholder_text_color,
                font=font,
                align="center",
            )

        except Exception as e:
            logger.debug(f"Error adding text to image: {e}")

    def _create_enhanced_background(self) -> Image.Image:
        """
        Create an enhanced background for placeholder covers.

        Returns:
            PIL Image with enhanced background
        """
        if self.placeholder_style == "gradient":
            return self._create_gradient_background()
        elif self.placeholder_style == "pattern":
            return self._create_pattern_background()
        else:
            # Default solid background
            return Image.new("RGB", self.target_size, self.placeholder_color)

    def _create_gradient_background(self) -> Image.Image:
        """Create a gradient background."""
        image = Image.new("RGB", self.target_size)
        draw = ImageDraw.Draw(image)

        # Convert hex colors to RGB
        colors = []
        for color in self.placeholder_gradient_colors:
            if color.startswith("#"):
                colors.append(tuple(int(color[i : i + 2], 16) for i in (1, 3, 5)))
            else:
                colors.append((44, 62, 80))  # Default fallback

        # Create vertical gradient
        height = self.target_size[1]
        for y in range(height):
            # Calculate which colors to interpolate between
            position = y / height
            segment_size = 1.0 / (len(colors) - 1)
            segment = int(position / segment_size)

            if segment >= len(colors) - 1:
                color = colors[-1]
            else:
                # Interpolate between two colors
                local_pos = (position - segment * segment_size) / segment_size
                color1 = colors[segment]
                color2 = colors[segment + 1]

                color = tuple(
                    int(color1[i] + (color2[i] - color1[i]) * local_pos)
                    for i in range(3)
                )

            draw.line([(0, y), (self.target_size[0], y)], fill=color)

        return image

    def _create_pattern_background(self) -> Image.Image:
        """Create a pattern background."""
        image = Image.new("RGB", self.target_size, self.placeholder_color)
        draw = ImageDraw.Draw(image)

        # Create a subtle geometric pattern
        pattern_size = 40
        for x in range(0, self.target_size[0], pattern_size):
            for y in range(0, self.target_size[1], pattern_size):
                # Alternate pattern
                if (x // pattern_size + y // pattern_size) % 2 == 0:
                    # Draw a subtle diamond
                    points = [
                        (x + pattern_size // 2, y),
                        (x + pattern_size, y + pattern_size // 2),
                        (x + pattern_size // 2, y + pattern_size),
                        (x, y + pattern_size // 2),
                    ]
                    # Use a slightly lighter color for the pattern
                    pattern_color = tuple(
                        min(255, c + 10)
                        for c in tuple(
                            int(self.placeholder_color[i : i + 2], 16)
                            for i in (1, 3, 5)
                        )
                    )
                    draw.polygon(points, fill=pattern_color)

        return image

    def _add_border(self, draw: ImageDraw.Draw, image_size: Tuple[int, int]) -> None:
        """Add a decorative border to the image."""
        width, height = image_size
        border_width = self.placeholder_border_width

        # Draw border rectangle
        draw.rectangle(
            [border_width, border_width, width - border_width, height - border_width],
            outline=self.placeholder_border_color,
            width=border_width,
        )

    def _add_decorative_elements(
        self, draw: ImageDraw.Draw, image_size: Tuple[int, int]
    ) -> None:
        """Add decorative elements to the placeholder."""
        width, height = image_size

        # Add corner decorations
        corner_size = 30
        decoration_color = self.placeholder_text_color

        # Top-left corner
        draw.line([(20, 20), (20 + corner_size, 20)], fill=decoration_color, width=2)
        draw.line([(20, 20), (20, 20 + corner_size)], fill=decoration_color, width=2)

        # Top-right corner
        draw.line(
            [(width - 20 - corner_size, 20), (width - 20, 20)],
            fill=decoration_color,
            width=2,
        )
        draw.line(
            [(width - 20, 20), (width - 20, 20 + corner_size)],
            fill=decoration_color,
            width=2,
        )

        # Bottom-left corner
        draw.line(
            [(20, height - 20 - corner_size), (20, height - 20)],
            fill=decoration_color,
            width=2,
        )
        draw.line(
            [(20, height - 20), (20 + corner_size, height - 20)],
            fill=decoration_color,
            width=2,
        )

        # Bottom-right corner
        draw.line(
            [(width - 20 - corner_size, height - 20), (width - 20, height - 20)],
            fill=decoration_color,
            width=2,
        )
        draw.line(
            [(width - 20, height - 20 - corner_size), (width - 20, height - 20)],
            fill=decoration_color,
            width=2,
        )

    def _add_enhanced_text_to_image(
        self,
        draw: ImageDraw.Draw,
        title: str,
        image_size: Tuple[int, int],
        author: Optional[str] = None,
    ) -> None:
        """
        Add enhanced text with better typography and layout.

        Args:
            draw: ImageDraw object
            title: Novel title
            image_size: Size of the image
            author: Optional author name
        """
        try:
            width, height = image_size

            # Calculate available text area (accounting for borders and decorations)
            text_margin = 60
            text_width = width - (text_margin * 2)
            text_height = height - (text_margin * 2)

            # Try to get better fonts with fallbacks
            title_font = self._get_font(min(width, height) // 15, bold=True)
            author_font = self._get_font(min(width, height) // 25, bold=False)

            # Calculate title layout
            wrapped_title = self._wrap_text(title, title_font, text_width)
            title_bbox = draw.multiline_textbbox((0, 0), wrapped_title, font=title_font)
            title_text_height = title_bbox[3] - title_bbox[1]

            # Calculate author layout if provided
            author_text_height = 0
            wrapped_author = ""
            if author and self.placeholder_author_text:
                wrapped_author = f"by {author}"
                author_bbox = draw.multiline_textbbox(
                    (0, 0), wrapped_author, font=author_font
                )
                author_text_height = author_bbox[3] - author_bbox[1]

            # Calculate vertical positioning
            total_text_height = title_text_height + (
                author_text_height + 20 if author_text_height > 0 else 0
            )
            start_y = (height - total_text_height) // 2

            # Draw title with shadow effect
            title_x = width // 2
            title_y = start_y

            # Shadow
            shadow_offset = 2
            draw.multiline_text(
                (title_x + shadow_offset, title_y + shadow_offset),
                wrapped_title,
                fill=(0, 0, 0, 128),  # Semi-transparent black shadow
                font=title_font,
                anchor="mt",
                align="center",
            )

            # Main title text
            draw.multiline_text(
                (title_x, title_y),
                wrapped_title,
                fill=self.placeholder_text_color,
                font=title_font,
                anchor="mt",
                align="center",
            )

            # Draw author if provided
            if author and self.placeholder_author_text and author_text_height > 0:
                author_y = title_y + title_text_height + 20

                # Author text with subtle styling
                author_color = tuple(
                    max(0, c - 40)
                    for c in tuple(
                        int(self.placeholder_text_color[i : i + 2], 16)
                        for i in (1, 3, 5)
                    )
                )

                draw.multiline_text(
                    (title_x, author_y),
                    wrapped_author,
                    fill=author_color,
                    font=author_font,
                    anchor="mt",
                    align="center",
                )

        except Exception as e:
            logger.debug(f"Error adding enhanced text to image: {e}")
            # Fallback to simple text
            self._add_text_to_image(draw, title, image_size)

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        """
        Get the best available font with fallbacks.

        Args:
            size: Font size
            bold: Whether to use bold font

        Returns:
            ImageFont object
        """
        font_names = [
            "arial.ttf" if not bold else "arialbd.ttf",
            "DejaVuSans.ttf" if not bold else "DejaVuSans-Bold.ttf",
            "liberation-sans.ttf" if not bold else "liberation-sans-bold.ttf",
            "NotoSans-Regular.ttf" if not bold else "NotoSans-Bold.ttf",
        ]

        for font_name in font_names:
            try:
                return ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                continue

        # Final fallback to default font
        try:
            return ImageFont.load_default()
        except:
            # If even default fails, create a minimal font
            return ImageFont.load_default()

    def _wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
        """
        Wrap text to fit within specified width.

        Args:
            text: Text to wrap
            font: Font to use for measuring
            max_width: Maximum width in pixels

        Returns:
            Wrapped text with newlines
        """
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    # Word is too long, add it anyway
                    lines.append(word)

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)

    def _generate_filename(
        self, novel_title: str, url: Optional[str] = None, suffix: str = ""
    ) -> str:
        """
        Generate Unix-safe filename for cover image using underscores.

        Args:
            novel_title: Title of the novel
            url: Optional URL to extract extension from
            suffix: Optional suffix to add

        Returns:
            Generated filename with Unix-safe naming
        """
        # Clean title for filename with Unix-safe underscores
        base_name = clean_filename(novel_title, use_underscores=True)

        # Add suffix if provided
        if suffix:
            base_name += f"_{suffix}"

        # Determine extension
        extension = f".{self.format.lower()}"
        if url:
            parsed_url = urlparse(url)
            url_ext = Path(parsed_url.path).suffix.lower()
            if url_ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                extension = url_ext if self.format.upper() == "ORIGINAL" else extension

        return f"{base_name}_cover{extension}"

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()
