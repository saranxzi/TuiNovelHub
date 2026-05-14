"""
Command Line Interface for Web Novel Scraper.

This module provides the main CLI entry point and argument parsing.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import click
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from wn_dl import __version__
from wn_dl.config import get_config
from wn_dl.core.epub_generator import EPUBGenerator
from wn_dl.core.font_manager import get_font_manager
from wn_dl.core.models import ScrapingProgress
from wn_dl.core.novel_discovery import NovelDiscoveryService
from wn_dl.core.processor import NovelProcessor
from wn_dl.core.user_config import get_user_config_manager, get_user_preferences
from wn_dl.providers import list_providers, list_supported_domains

console = Console()
logger = logging.getLogger(__name__)


def setup_rich_logging(
    console: Console, verbose: bool = False, quiet: bool = False
) -> None:
    """
    Set up Rich logging handler that works well with progress bars.

    Args:
        console: Rich console instance
        verbose: Enable verbose logging
        quiet: Enable quiet mode (warnings only)
    """
    log_level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO

    # Configure Rich logging handler to work with progress bars
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=verbose,
        markup=True,  # Enable Rich markup in log messages
        log_time_format="[%X]",  # Time format
    )

    # Set up logging with Rich handler
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler],
        force=True,  # Override any existing configuration
    )

    # Suppress some noisy loggers in quiet mode
    if quiet:
        logging.getLogger("urllib3").setLevel(logging.ERROR)
        logging.getLogger("aiohttp").setLevel(logging.ERROR)


@click.group()
@click.version_option(version=__version__, prog_name="wn-dl")
@click.option(
    "--with-info",
    is_flag=True,
    help="Show detailed logging information (default is silent mode)",
)
@click.option(
    "--config",
    "-c",
    help="Configuration file path",
    default=None,
)
@click.pass_context
def cli(ctx, with_info: bool, config: Optional[str]):
    """
    Web Novel Scraper - Download and convert web novels to EPUB format.

    A modular scraper that supports multiple web novel providers with
    concurrent processing and high-quality EPUB generation.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Set up logging with Rich integration
    # Default is silent mode (quiet=True), unless --with-info is specified
    verbose = with_info
    quiet = not with_info

    setup_rich_logging(console, verbose, quiet)

    # Load user preferences
    try:
        user_preferences = get_user_preferences()
        ctx.obj["user_preferences"] = user_preferences
    except Exception as e:
        logger.warning(f"Could not load user preferences: {e}")
        ctx.obj["user_preferences"] = None

    # Store configuration in context
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["with_info"] = with_info
    ctx.obj["config"] = config


@cli.command()
@click.option(
    "--url",
    "-u",
    help="URL of the novel to scrape",
    default=None,
)
@click.option(
    "--files",
    help="Text file containing list of novel URLs (one per line)",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--output",
    "-o",
    help="Output directory for generated files (uses user preference if not specified)",
    default=None,
    show_default=False,
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["markdown", "epub", "both"]),
    default="both",
    help="Output format",
    show_default=True,
)
@click.option(
    "--provider",
    "-p",
    help="Provider to use (auto-detected if not specified)",
    default=None,
)
@click.option(
    "--max-workers",
    "-w",
    type=int,
    help="Maximum concurrent workers",
    default=None,
)
@click.option(
    "--rate-limit",
    "-r",
    type=float,
    help="Rate limit in requests per second",
    default=None,
)
@click.option(
    "--no-cover",
    is_flag=True,
    help="Skip cover image download",
)
@click.option(
    "--font",
    help="Font family to use for EPUB generation (use 'wn-dl list-fonts' to see available fonts)",
    default=None,
)
@click.pass_context
def scrape(
    ctx,
    url: Optional[str],
    files: Optional[Path],
    output: str,
    output_format: str,
    provider: Optional[str],
    max_workers: Optional[int],
    rate_limit: Optional[float],
    no_cover: bool,
    font: Optional[str],
) -> None:
    """Scrape a novel from the given URL or multiple novels from a file."""
    # Validate input parameters
    if not url and not files:
        console.print("[red]Error: Either --url or --files must be specified[/red]")
        console.print("Use --help for more information")
        sys.exit(1)

    if url and files:
        console.print("[red]Error: Cannot specify both --url and --files[/red]")
        console.print(
            "Use either --url for single novel or --files for multiple novels"
        )
        sys.exit(1)

    if files:
        # Process multiple URLs from file
        asyncio.run(
            _scrape_multiple_async(
                ctx,
                files,
                output,
                output_format,
                provider,
                max_workers,
                rate_limit,
                no_cover,
                font,
            )
        )
    else:
        # Process single URL
        asyncio.run(
            _scrape_async(
                ctx,
                url,
                output,
                output_format,
                provider,
                max_workers,
                rate_limit,
                no_cover,
                font,
            )
        )


async def _scrape_multiple_async(
    ctx,
    files: Path,
    output: Optional[str],
    output_format: str,
    provider: Optional[str],
    max_workers: Optional[int],
    rate_limit: Optional[float],
    no_cover: bool,
    font: Optional[str],
) -> None:
    """Async implementation of scrape command for multiple URLs from file."""
    verbose = ctx.obj.get("verbose", False)
    quiet = ctx.obj.get("quiet", False)

    try:
        # Read URLs from file
        with open(files, "r", encoding="utf-8") as f:
            urls = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]

        if not urls:
            console.print(f"[red]No valid URLs found in file: {files}[/red]")
            sys.exit(1)

        total_novels = len(urls)
        successful_novels = 0
        failed_novels = 0

        if not quiet:
            console.print(
                f"[green]Found {total_novels} novels to scrape from:[/green] {files}"
            )
            console.print(f"[blue]Output directory:[/blue] {output or './output'}")
            console.print(f"[blue]Output formats:[/blue] {output_format}")
            console.print("")

        # Process each URL sequentially
        for i, url in enumerate(urls, 1):
            if not quiet:
                console.print(
                    f"[bold cyan]Processing novel {i}/{total_novels}:[/bold cyan] {url}"
                )
            else:
                console.print(f"[cyan]Novel {i}/{total_novels}:[/cyan] {url}")

            try:
                # Call the single scrape function for each URL
                await _scrape_async(
                    ctx,
                    url,
                    output,
                    output_format,
                    provider,
                    max_workers,
                    rate_limit,
                    no_cover,
                    font,
                )
                successful_novels += 1

                if not quiet:
                    console.print(f"[green]✅ Novel {i} completed successfully[/green]")
                else:
                    console.print(f"[green]✅ Completed[/green]")

            except KeyboardInterrupt:
                console.print(
                    f"\n[yellow]⏹️  Batch scraping interrupted by user at novel {i}/{total_novels}[/yellow]"
                )
                break
            except Exception as e:
                failed_novels += 1
                console.print(f"[red]❌ Novel {i} failed: {e}[/red]")
                if verbose:
                    console.print_exception()
                # Continue with next novel instead of stopping
                continue

            # Add small delay between novels to be respectful
            if i < total_novels:
                await asyncio.sleep(1)
                if not quiet:
                    console.print("")  # Add spacing between novels

        # Display final summary
        console.print(f"\n[bold blue]Batch Scraping Summary[/bold blue]")
        console.print(
            f"[green]✅ Successful:[/green] {successful_novels}/{total_novels}"
        )
        if failed_novels > 0:
            console.print(f"[red]❌ Failed:[/red] {failed_novels}/{total_novels}")

        if failed_novels > 0:
            console.print(
                f"\n[yellow]Some novels failed to scrape. Check the output above for details.[/yellow]"
            )

    except FileNotFoundError:
        console.print(f"[red]File not found: {files}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error reading file {files}: {e}[/red]")
        sys.exit(1)


async def _scrape_async(
    ctx,
    url: str,
    output: Optional[str],
    output_format: str,
    provider: Optional[str],
    max_workers: Optional[int],
    rate_limit: Optional[float],
    no_cover: bool,
    font: Optional[str],
) -> None:
    """Async implementation of scrape command."""
    verbose = ctx.obj.get("verbose", False)
    quiet = ctx.obj.get("quiet", False)
    config_file = ctx.obj.get("config")
    user_preferences = ctx.obj.get("user_preferences")

    try:
        # Apply user preferences as defaults
        if output is None and user_preferences and user_preferences.output_directory:
            output = user_preferences.output_directory
        elif output is None:
            output = "./output"

        if max_workers is None and user_preferences:
            max_workers = user_preferences.max_workers

        if rate_limit is None and user_preferences:
            rate_limit = user_preferences.rate_limit

        if font is None and user_preferences:
            font = user_preferences.font_family

        # Load configuration
        config = get_config(config_file)

        # Override config with CLI options
        if max_workers:
            config.setdefault("processing", {})["max_workers"] = max_workers
        if rate_limit:
            config.setdefault("processing", {})["rate_limit"] = rate_limit
        if no_cover:
            config.setdefault("images", {})["download_covers"] = False

        # For scrape command, automatically use EbookLib for EPUB generation
        config.setdefault("epub", {})["use_ebooklib"] = True

        # Handle font selection
        if font:
            from wn_dl.core.font_manager import validate_font_selection

            is_valid, message = validate_font_selection(font)
            if not is_valid:
                console.print(f"[yellow]Warning: {message}[/yellow]")
                console.print("[yellow]Using default font instead.[/yellow]")
            else:
                config.setdefault("epub", {})["font_family"] = font
                if not quiet:
                    console.print(f"[green]Using font:[/green] {font}")

        # Determine output formats
        if output_format == "both":
            formats = ["markdown", "epub"]
        else:
            formats = [output_format]

        if not quiet:
            console.print(f"[green]Starting scraper for:[/green] {url}")
            console.print(f"[blue]Output directory:[/blue] {output}")
            console.print(f"[blue]Output formats:[/blue] {', '.join(formats)}")

            if provider:
                console.print(f"[blue]Provider:[/blue] {provider}")
            else:
                console.print("[blue]Provider:[/blue] Auto-detect")

        # Create processor and set up progress tracking
        processor = NovelProcessor(config)

        # Progress tracking with Rich integration
        progress_task = None
        progress_display = None

        # Always show progress, but with different styles for quiet vs verbose mode
        if quiet:
            # Silent mode: Show only essential download progress
            progress_display = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
                transient=False,  # Keep progress visible
                refresh_per_second=2,  # Lower refresh rate for silent mode
            )
        else:
            # Verbose mode: Show detailed progress with spinner and time
            progress_display = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=False,  # Keep progress visible
                refresh_per_second=4,  # Higher refresh rate for verbose mode
            )

        progress_display.start()
        progress_task = progress_display.add_task("Initializing...", total=100)

        def progress_callback(progress: ScrapingProgress):
            if progress_display and progress_task is not None:
                # Update progress description based on status and mode
                if progress.status.value == "in_progress":
                    if progress.total_chapters > 0:
                        if quiet:
                            # Silent mode: Concise progress
                            description = f"Downloading {progress.completed_chapters}/{progress.total_chapters}"
                        else:
                            # Verbose mode: Detailed progress
                            description = f"Scraping chapters ({progress.completed_chapters}/{progress.total_chapters})"
                    else:
                        description = (
                            "Discovering chapters..." if not quiet else "Discovering..."
                        )
                elif progress.status.value == "completed":
                    if quiet:
                        description = (
                            f"Complete ({progress.completed_chapters} chapters)"
                        )
                    else:
                        description = (
                            f"Completed! ({progress.completed_chapters} chapters)"
                        )
                elif progress.status.value == "failed":
                    description = f"Failed after {progress.completed_chapters} chapters"
                else:
                    description = "Processing..." if not quiet else "Processing"

                progress_display.update(
                    progress_task,
                    completed=progress.completed_chapters,
                    total=max(progress.total_chapters, 1),  # Avoid division by zero
                    description=description,
                )

                # Log significant progress milestones without interfering with progress bar
                if (
                    progress.completed_chapters > 0
                    and progress.completed_chapters % 50 == 0
                ):
                    logger = logging.getLogger("wn_dl.progress")
                    logger.info(
                        f"Progress milestone: {progress.completed_chapters}/{progress.total_chapters} chapters completed"
                    )

        # Process the novel with proper cleanup
        try:
            result = await processor.process_novel_enhanced(
                novel_url=url,
                output_dir=output,
                formats=formats,
                progress_callback=progress_callback,
                save_individual_chapters=False,  # Disable individual chapters to prevent duplication
                resume_existing=False,  # Disable resume to ensure clean scraping
            )
        finally:
            # Ensure progress display is properly stopped
            if progress_display:
                progress_display.stop()
                # Add a small delay to ensure clean output
                await asyncio.sleep(0.1)

        # Display results
        if result["success"]:
            if quiet:
                # Silent mode: Show only essential completion info
                console.print(
                    f"[green]✅ {result['novel_title']} - {result['successful_chapters']} chapters downloaded[/green]"
                )
                if result.get("generated_files"):
                    files = [Path(f).name for f in result["generated_files"]]
                    console.print(f"[dim]Files: {', '.join(files)}[/dim]")
            else:
                # Verbose mode: Show detailed results table
                console.print("\n[green]✅ Scraping completed successfully![/green]")

                # Create results table
                table = Table(title="Scraping Results")
                table.add_column("Property", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("Novel Title", result["novel_title"])
                table.add_row("Author", result["author"])
                table.add_row("Total Chapters", str(result["total_chapters"]))
                table.add_row("Successful Chapters", str(result["successful_chapters"]))
                table.add_row("Failed Chapters", str(result["failed_chapters"]))
                table.add_row("Processing Time", f"{result['processing_time']:.1f}s")
                table.add_row("Output Directory", result["output_directory"])

                if result.get("generated_files"):
                    files_text = "\n".join(
                        Path(f).name for f in result["generated_files"]
                    )
                    table.add_row("Generated Files", files_text)

                console.print(table)

                # Display statistics
                if result.get("statistics"):
                    stats = result["statistics"]
                    stats_panel = Panel(
                        f"Total Words: {stats['total_words']:,}\n"
                        f"Average Words per Chapter: {stats['average_words_per_chapter']:,}\n"
                        f"Estimated Reading Time: {stats['estimated_reading_time_hours']:.1f} hours",
                        title="Novel Statistics",
                        border_style="blue",
                    )
                    console.print(stats_panel)
        else:
            console.print(f"[red]❌ Scraping failed: {result['error']}[/red]")
            sys.exit(1)

    except KeyboardInterrupt:
        if progress_display:
            progress_display.stop()
        console.print("\n[yellow]⏹️  Scraping interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if progress_display:
            progress_display.stop()
        console.print(f"[red]💥 Unexpected error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


@cli.command("resume")
@click.option(
    "--progress-file",
    "-p",
    help="Path to progress file to resume from",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress progress output",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.pass_context
def resume_scraping(ctx, progress_file: Path, quiet: bool, verbose: bool):
    """Resume interrupted novel scraping from a progress file."""
    try:
        from wn_dl.core.processor import NovelProcessor

        # Set up logging
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        elif not quiet:
            logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=logging.WARNING)

        # Initialize processor
        processor = NovelProcessor()

        if not quiet:
            console.print(f"[blue]Resuming from progress file: {progress_file}[/blue]")

        # Set up progress tracking
        progress_display = None
        if not quiet:
            from rich.progress import (
                BarColumn,
                Progress,
                SpinnerColumn,
                TaskProgressColumn,
                TextColumn,
            )

            progress_display = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
                transient=False,
            )
            progress_display.start()

            progress_task = progress_display.add_task("Resuming...", total=None)

            def progress_callback(progress):
                if progress_display and progress.total_chapters > 0:
                    progress_display.update(
                        progress_task,
                        description=f"Processing chapters ({progress.completed_chapters}/{progress.total_chapters})",
                        completed=progress.completed_chapters,
                        total=progress.total_chapters,
                    )

            processor.add_progress_callback(progress_callback)

        # Resume processing
        async def run_resume():
            return await processor.resume_processing(str(progress_file))

        result = asyncio.run(run_resume())

        # Stop progress display
        if progress_display:
            progress_display.stop()

        # Display results
        if result["success"]:
            if not quiet:
                console.print("\n[green]✅ Resume completed successfully![/green]")
                console.print(
                    f"[cyan]Total chapters:[/cyan] {result['total_chapters']}"
                )
                console.print(
                    f"[cyan]Completed chapters:[/cyan] {result['completed_chapters']}"
                )
                console.print(
                    f"[cyan]Failed chapters:[/cyan] {result['failed_chapters']}"
                )

                if result.get("generated_files"):
                    console.print(f"[cyan]Generated files:[/cyan]")
                    for file_path in result["generated_files"]:
                        console.print(f"  • {file_path}")
            else:
                console.print(
                    f"[green]✅ Resume completed - {result['completed_chapters']}/{result['total_chapters']} chapters[/green]"
                )
        else:
            console.print(f"[red]❌ Resume failed: {result['error']}[/red]")
            sys.exit(1)

    except KeyboardInterrupt:
        if progress_display:
            progress_display.stop()
        console.print("\n[yellow]⏹️  Resume interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        if progress_display:
            progress_display.stop()
        console.print(f"[red]💥 Unexpected error: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


@cli.command("generate-epub")
@click.option(
    "--input",
    "-i",
    "input_file",
    help="Input markdown file path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    help="Output directory for EPUB file (uses user preference if not specified)",
    default=None,
    show_default=False,
    type=click.Path(path_type=Path),
)
@click.option(
    "--title",
    "-t",
    help="Novel title (overrides YAML metadata if provided)",
    default=None,
)
@click.option(
    "--author",
    "-a",
    help="Author name (overrides YAML metadata if provided)",
    default=None,
)
@click.option(
    "--description",
    "-d",
    help="Novel description (overrides YAML metadata if provided)",
    default=None,
)
@click.option(
    "--cover",
    "-c",
    help="Cover image path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--css",
    help="Custom CSS file path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--no-toc",
    is_flag=True,
    help="Disable table of contents generation",
)
@click.option(
    "--check-duplicates",
    is_flag=True,
    help="Check for and report duplicate content in markdown file",
)
@click.option(
    "--use-ebooklib",
    is_flag=True,
    help="Force use of EbookLib instead of Pandoc for EPUB generation",
)
@click.option(
    "--no-fallback",
    is_flag=True,
    help="Disable automatic fallback to EbookLib when Pandoc fails",
)
@click.option(
    "--silent",
    is_flag=True,
    help="Silent mode - show only progress bar and success message",
)
@click.option(
    "--font",
    help="Font family to use for EPUB generation (use 'wn-dl list-fonts' to see available fonts)",
    default=None,
)
@click.pass_context
def generate_epub(
    ctx,
    input_file: Path,
    output_dir: Optional[Path],
    title: Optional[str],
    author: Optional[str],
    description: Optional[str],
    cover: Optional[Path],
    css: Optional[Path],
    no_toc: bool,
    check_duplicates: bool,
    use_ebooklib: bool,
    no_fallback: bool,
    silent: bool,
    font: Optional[str],
) -> None:
    """Generate EPUB from existing markdown file."""
    verbose = ctx.obj.get("verbose", False)
    quiet = ctx.obj.get("quiet", False)
    config_file = ctx.obj.get("config")
    user_preferences = ctx.obj.get("user_preferences")

    try:
        # Apply user preferences as defaults
        if (
            output_dir is None
            and user_preferences
            and user_preferences.output_directory
        ):
            output_dir = Path(user_preferences.output_directory)
        elif output_dir is None:
            output_dir = Path("./")

        if font is None and user_preferences:
            font = user_preferences.font_family

        if not use_ebooklib and user_preferences:
            # Use user's preferred generator if not explicitly specified
            use_ebooklib = user_preferences.preferred_generator == "ebooklib"

        # Load configuration
        config = get_config(config_file)

        # Override EPUB config with CLI options
        epub_config = config.setdefault("epub", {})
        if no_toc:
            epub_config["include_toc"] = False
        # Note: if no_toc is False, we keep the config file value
        if use_ebooklib:
            epub_config["use_ebooklib"] = True
        if no_fallback:
            epub_config["ebooklib_fallback"] = False

        # Handle font selection
        if font:
            from wn_dl.core.font_manager import validate_font_selection

            is_valid, message = validate_font_selection(font)
            if not is_valid:
                console.print(f"[yellow]Warning: {message}[/yellow]")
                console.print("[yellow]Using default font instead.[/yellow]")
            else:
                epub_config["font_family"] = font
                if not quiet and not silent:
                    console.print(f"[green]Using font:[/green] {font}")

        # Create EPUB generator
        epub_generator = EPUBGenerator(config, silent=silent)

        # Check if we can proceed with EPUB generation
        if (
            not epub_generator.pandoc_available
            and not epub_config.get("use_ebooklib", False)
            and not epub_config.get("ebooklib_fallback", True)
        ):
            console.print(
                "[red]Error: Pandoc is not available and EbookLib fallback is disabled.[/red]"
            )
            console.print(
                "[yellow]Install Pandoc: https://pandoc.org/installing.html[/yellow]"
            )
            console.print(
                "[yellow]Or use --use-ebooklib to force EbookLib usage[/yellow]"
            )
            sys.exit(1)

        # Check for duplicate content if requested
        if check_duplicates:
            duplicate_info = _check_for_duplicates(input_file)
            if duplicate_info["has_duplicates"]:
                console.print("[red]⚠️  DUPLICATE CONTENT DETECTED![/red]")
                console.print(
                    f"[yellow]File size: {duplicate_info['file_size_mb']:.1f}MB[/yellow]"
                )
                console.print(
                    f"[yellow]YAML sections: {duplicate_info['yaml_sections']} (should be 2)[/yellow]"
                )
                console.print(
                    f"[yellow]Title occurrences: {duplicate_info['title_count']}[/yellow]"
                )
                console.print("")
                console.print(
                    "[red]This file appears to contain duplicate content from multiple scraping sessions.[/red]"
                )
                console.print("[yellow]RECOMMENDED SOLUTION:[/yellow]")
                console.print("1. Delete the existing novel directory")
                console.print("2. Re-scrape the novel with a clean start")
                console.print("3. Or manually clean the markdown file")
                console.print("")
                if not click.confirm("Continue with EPUB generation anyway?"):
                    sys.exit(1)

        # Extract YAML metadata from markdown file
        yaml_metadata = _extract_yaml_metadata(input_file)

        # Determine final metadata (CLI options override YAML)
        final_title = (
            title
            or yaml_metadata.get("title")
            or _extract_title_from_markdown(input_file)
        )
        if not final_title:
            final_title = input_file.stem.replace("_", " ").replace("-", " ").title()

        final_author = author or yaml_metadata.get("author")
        final_description = description or yaml_metadata.get("description")
        final_cover = (
            cover or yaml_metadata.get("cover-image") or yaml_metadata.get("cover_path")
        )

        # Prepare metadata for EPUB generation
        metadata = {"title": final_title}
        if final_author:
            metadata["author"] = final_author
        if final_description:
            metadata["description"] = final_description
        if final_cover:
            # Handle both absolute and relative cover paths
            cover_path = Path(final_cover)
            if not cover_path.is_absolute():
                # Resolve relative to markdown file directory
                cover_path = input_file.parent / cover_path
            if cover_path.exists():
                metadata["cover_path"] = str(cover_path)
            else:
                if not quiet:
                    console.print(
                        f"[yellow]Warning: Cover image not found: {cover_path}[/yellow]"
                    )

        # Add any additional YAML metadata
        for key, value in yaml_metadata.items():
            if (
                key
                not in ["title", "author", "description", "cover-image", "cover_path"]
                and value
            ):
                metadata[key] = value

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        if not quiet and not silent:
            console.print(f"[blue]Generating EPUB from:[/blue] {input_file}")
            console.print(f"[blue]Title:[/blue] {final_title}")
            if final_author:
                console.print(f"[blue]Author:[/blue] {final_author}")
            if final_description:
                console.print(
                    f"[blue]Description:[/blue] {final_description[:100]}{'...' if len(final_description) > 100 else ''}"
                )
            console.print(f"[blue]Output directory:[/blue] {output_dir}")
            if css:
                console.print(f"[blue]Using CSS:[/blue] {css}")
            elif yaml_metadata.get("epub-css"):
                console.print(
                    f"[blue]Using CSS from YAML:[/blue] {yaml_metadata.get('epub-css')}"
                )
            if metadata.get("cover_path"):
                console.print(f"[blue]Cover image:[/blue] {metadata.get('cover_path')}")

        # Generate EPUB
        result = epub_generator.generate_epub(
            str(input_file),
            output_dir,
            final_title,
            css_file=str(css) if css else None,
            metadata=metadata,
        )

        if result:
            # result is already a full path from the generator
            epub_path = Path(result) if isinstance(result, str) else result
            if not quiet and not silent:
                # Format file size in MB for consistency
                file_size_bytes = epub_path.stat().st_size if epub_path.exists() else 0
                file_size_mb = file_size_bytes / (1024 * 1024)

                console.print(
                    f"[green]✅ EPUB generated successfully:[/green] {epub_path.name} ({file_size_mb:.1f} MB)"
                )
                if not epub_path.exists():
                    console.print(
                        "[yellow]Warning: EPUB file path may be incorrect[/yellow]"
                    )

            # Update database if enabled
            if user_preferences and user_preferences.enable_database:
                try:
                    from datetime import datetime

                    from wn_dl.core.novel_database_service import NovelDatabaseService

                    db_service = NovelDatabaseService(user_preferences.database_path)

                    # Find the novel record by directory path
                    novel_directory = input_file.parent
                    existing_novel = db_service.get_novel_by_directory(
                        str(novel_directory)
                    )

                    if existing_novel:
                        # Update EPUB information
                        epub_size = (
                            epub_path.stat().st_size if epub_path.exists() else None
                        )
                        update_data = {
                            "has_epub": True,
                            "epub_file_path": str(epub_path),
                            "epub_file_size": epub_size,
                            "scraping_end_time": datetime.utcnow(),  # EPUB creation time
                        }

                        success = db_service.update_novel(
                            existing_novel.id, **update_data
                        )
                        if success and not silent:
                            console.print(
                                "[blue]📊 Database updated with EPUB information[/blue]"
                            )
                    else:
                        if not silent:
                            console.print(
                                "[yellow]⚠️ Novel not found in database - skipping database update[/yellow]"
                            )

                    db_service.close()

                except Exception as e:
                    if not silent:
                        console.print(
                            f"[yellow]⚠️ Failed to update database: {e}[/yellow]"
                        )
        else:
            if not silent:
                console.print("[red]❌ Failed to generate EPUB[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error generating EPUB: {e}[/red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


def _extract_title_from_markdown(markdown_file: Path) -> Optional[str]:
    """Extract title from markdown file (first H1 heading)."""
    try:
        with open(markdown_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Skip YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        # Find first H1 heading
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            # Stop after first few lines to avoid reading entire file
            if len(line) > 0 and not line.startswith("#"):
                break
    except Exception:
        pass
    return None


def _extract_yaml_metadata(markdown_file: Path) -> Dict[str, Any]:
    """Extract YAML frontmatter metadata from markdown file."""
    try:
        with open(markdown_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if file starts with YAML frontmatter
        if not content.startswith("---"):
            return {}

        # Split content to extract YAML
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        yaml_content = parts[1].strip()
        if not yaml_content:
            return {}

        # Parse YAML
        metadata = yaml.safe_load(yaml_content)
        return metadata if isinstance(metadata, dict) else {}

    except Exception as e:
        # Log error but don't fail the entire operation
        logger.debug(f"Failed to extract YAML metadata from {markdown_file}: {e}")
        return {}


def _check_for_duplicates(markdown_file: Path) -> Dict[str, Any]:
    """
    Check for duplicate content in markdown file.

    Args:
        markdown_file: Path to markdown file to check

    Returns:
        Dictionary with duplicate detection results
    """
    try:
        file_size_mb = markdown_file.stat().st_size / (1024 * 1024)

        with open(markdown_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Count YAML delimiters (should be exactly 2: opening and closing)
        yaml_sections = content.count("---")

        # Extract title from YAML to count occurrences
        title = None
        yaml_metadata = _extract_yaml_metadata(markdown_file)
        if yaml_metadata and "title" in yaml_metadata:
            title = yaml_metadata["title"]
            title_count = content.count(title) if title else 0
        else:
            title_count = 0

        # Determine if duplicates exist
        has_duplicates = (
            yaml_sections > 2  # More than one YAML frontmatter
            or (title and title_count > 10)  # Title appears too many times
            or file_size_mb > 30  # Suspiciously large file
        )

        return {
            "has_duplicates": has_duplicates,
            "file_size_mb": file_size_mb,
            "yaml_sections": yaml_sections,
            "title_count": title_count,
            "title": title,
        }

    except Exception as e:
        logger.debug(f"Failed to check for duplicates in {markdown_file}: {e}")
        return {
            "has_duplicates": False,
            "file_size_mb": 0,
            "yaml_sections": 0,
            "title_count": 0,
            "title": None,
        }


@cli.command()
def providers():
    """List supported providers and domains."""
    console.print("[bold blue]Supported Providers[/bold blue]")

    from wn_dl.providers.registry import registry

    provider_list = list_providers()

    if provider_list:
        table = Table(title="Available Providers")
        table.add_column("Provider", style="cyan")
        table.add_column("Supported Domains", style="green")

        for provider in provider_list:
            # Get provider info which includes specific domains
            provider_info = registry.get_provider_info(provider)
            if provider_info:
                provider_domains = provider_info.get("domains", [])
                table.add_row(
                    provider, ", ".join(provider_domains) if provider_domains else "N/A"
                )
            else:
                table.add_row(provider, "N/A")

        console.print(table)
    else:
        console.print("[yellow]No providers registered[/yellow]")


@cli.command("list-fonts")
def list_fonts():
    """List available fonts for EPUB generation."""
    try:
        font_manager = get_font_manager()
        available_fonts = font_manager.get_available_fonts()

        if not available_fonts:
            console.print("[yellow]No fonts available[/yellow]")
            return

        console.print("[bold blue]Available Fonts for EPUB Generation[/bold blue]\n")

        # Create table for font information
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Font Name", style="cyan", no_wrap=True)
        table.add_column("Display Name", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Variants", style="blue")

        for font_name in available_fonts:
            font_info = font_manager.get_font_info(font_name)
            if font_info:
                status = "✅ Complete" if font_info["is_complete"] else "⚠️ Incomplete"
                variants = ", ".join(font_info["variants"])

                # Highlight default font
                display_name = font_info["display_name"]
                if font_name == font_manager.get_default_font():
                    display_name = f"{display_name} [bold](default)[/bold]"

                table.add_row(font_name, display_name, status, variants)

        console.print(table)

        # Show usage examples
        console.print("\n[bold green]Usage Examples:[/bold green]")
        console.print("  wn-dl scrape -u URL --font bookerly")
        console.print("  wn-dl generate-epub --input novel.md --font bitter")

        # Show incomplete fonts warning
        incomplete_fonts = [
            font
            for font in available_fonts
            if not font_manager.get_font_info(font)["is_complete"]
        ]
        if incomplete_fonts:
            console.print(
                f"\n[yellow]Note: Incomplete fonts ({', '.join(incomplete_fonts)}) may not work properly for EPUB generation.[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error listing fonts: {e}[/red]")


@cli.group()
def config():
    """Manage user configuration and preferences."""
    pass


@config.command("show")
def config_show():
    """Display current user configuration."""
    try:
        user_config_manager = get_user_config_manager()
        config_file = user_config_manager.get_config_file_path()

        if not config_file or not config_file.exists():
            console.print("[yellow]No user configuration file found.[/yellow]")
            console.print("Run 'wn-dl config init' to create one.")
            return

        console.print(f"[bold blue]User Configuration[/bold blue] ({config_file})\n")

        # Load and display configuration
        preferences = user_config_manager.get_preferences()

        # Create table for preferences
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        table.add_column("Description", style="blue")

        # Font preferences
        table.add_row(
            "font.default_family",
            preferences.font_family,
            "Default font for EPUB generation",
        )
        table.add_row(
            "font.fallback_family",
            preferences.font_fallback,
            "Fallback font if default unavailable",
        )

        # Logging preferences
        table.add_row("logging.level", preferences.log_level, "Logging verbosity level")
        table.add_row(
            "logging.file",
            str(preferences.log_file) if preferences.log_file else "console",
            "Log output destination",
        )

        # Directory preferences
        table.add_row(
            "directories.output",
            preferences.output_directory or "current",
            "Default output directory",
        )
        table.add_row(
            "directories.input",
            preferences.input_directory or "current",
            "Default input directory",
        )

        # EPUB preferences
        table.add_row(
            "epub.preferred_generator",
            preferences.preferred_generator,
            "Preferred EPUB generator",
        )
        table.add_row(
            "epub.fallback_enabled",
            str(preferences.fallback_enabled),
            "Enable generator fallback",
        )
        table.add_row(
            "epub.include_toc",
            str(preferences.include_toc),
            "Include table of contents",
        )

        # Processing preferences
        table.add_row(
            "processing.max_workers",
            str(preferences.max_workers),
            "Maximum concurrent workers",
        )
        table.add_row(
            "processing.rate_limit", str(preferences.rate_limit), "Requests per second"
        )
        table.add_row(
            "processing.timeout", str(preferences.timeout), "Request timeout (seconds)"
        )

        # Cache preferences
        table.add_row(
            "cache.enabled",
            str(preferences.cache_enabled),
            "Enable HTTP response caching",
        )
        table.add_row(
            "cache.size_limit",
            preferences.cache_size_limit,
            "Maximum cache size",
        )
        table.add_row(
            "cache.default_ttl",
            str(preferences.cache_default_ttl),
            "Default cache TTL (seconds)",
        )
        table.add_row(
            "cache.compression",
            str(preferences.cache_compression),
            "Enable cache compression",
        )
        table.add_row(
            "cache.respect_headers",
            str(preferences.cache_respect_headers),
            "Honor HTTP cache headers",
        )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error displaying configuration: {e}[/red]")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value."""
    try:
        user_config_manager = get_user_config_manager()

        # Convert string value to appropriate type
        converted_value = _convert_config_value(value)

        # Validate the key
        if not _validate_config_key(key):
            console.print(f"[red]Invalid configuration key: {key}[/red]")
            console.print("Use 'wn-dl config show' to see available settings.")
            return

        # Set the preference
        success = user_config_manager.set_preference(key, converted_value)

        if success:
            console.print(f"[green]✅ Set {key} = {converted_value}[/green]")
        else:
            console.print(f"[red]Failed to set {key}[/red]")

    except Exception as e:
        console.print(f"[red]Error setting configuration: {e}[/red]")


@config.command("reset")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def config_reset(confirm: bool):
    """Reset configuration to defaults."""
    try:
        if not confirm:
            response = click.confirm(
                "This will reset all user preferences to defaults. Continue?"
            )
            if not response:
                console.print("Configuration reset cancelled.")
                return

        user_config_manager = get_user_config_manager()
        success = user_config_manager.reset_to_defaults()

        if success:
            console.print("[green]✅ Configuration reset to defaults[/green]")
        else:
            console.print("[red]Failed to reset configuration[/red]")

    except Exception as e:
        console.print(f"[red]Error resetting configuration: {e}[/red]")


@config.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing configuration")
def config_init(force: bool):
    """Initialize user configuration with interactive setup."""
    try:
        user_config_manager = get_user_config_manager()
        config_file = user_config_manager.get_config_file_path()

        # Check if config already exists
        if config_file and config_file.exists() and not force:
            console.print(
                f"[yellow]Configuration file already exists: {config_file}[/yellow]"
            )
            console.print(
                "Use --force to overwrite or 'wn-dl config set' to modify settings."
            )
            return

        console.print("[bold blue]🔧 wn-dl Configuration Setup[/bold blue]\n")
        console.print("Let's set up your preferences. Press Enter to use defaults.\n")

        # Interactive setup
        preferences = {}

        # Font preferences
        console.print("[bold]Font Preferences[/bold]")
        font_manager = get_font_manager()
        available_fonts = font_manager.get_available_fonts()
        console.print(f"Available fonts: {', '.join(available_fonts)}")

        font_family = click.prompt(
            "Default font family",
            default="bitter",
            type=click.Choice(available_fonts, case_sensitive=False),
        )
        preferences["font"] = {
            "default_family": font_family,
            "fallback_family": "bitter",
        }

        # Logging preferences
        console.print("\n[bold]Logging Preferences[/bold]")
        log_level = click.prompt(
            "Log level",
            default="WARNING",
            type=click.Choice(
                ["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False
            ),
        )
        preferences["logging"] = {"level": log_level}

        # Directory preferences
        console.print("\n[bold]Directory Preferences[/bold]")
        output_dir = click.prompt(
            "Default output directory (empty for current)",
            default="",
            show_default=False,
        )
        if output_dir:
            preferences["directories"] = {"output": output_dir, "auto_create": True}

        # EPUB preferences
        console.print("\n[bold]EPUB Generator Preferences[/bold]")
        generator = click.prompt(
            "Preferred EPUB generator",
            default="pandoc",
            type=click.Choice(["pandoc", "ebooklib"], case_sensitive=False),
        )
        preferences["epub"] = {
            "preferred_generator": generator,
            "fallback_enabled": True,
            "include_toc": True,
        }

        # Save configuration
        config_data = {"preferences": preferences}
        success = user_config_manager.save_user_config(config_data, create_backup=False)

        if success:
            config_file = user_config_manager.get_config_file_path()
            console.print(f"\n[green]✅ Configuration saved to: {config_file}[/green]")
            console.print("Use 'wn-dl config show' to view your settings.")
            console.print("Use 'wn-dl config set <key> <value>' to modify settings.")
        else:
            console.print("\n[red]Failed to save configuration[/red]")

    except Exception as e:
        console.print(f"[red]Error initializing configuration: {e}[/red]")


@config.command("validate")
def config_validate():
    """Validate current configuration."""
    try:
        user_config_manager = get_user_config_manager()
        config_file = user_config_manager.get_config_file_path()

        if not config_file or not config_file.exists():
            console.print("[yellow]No user configuration file found.[/yellow]")
            return

        console.print(
            f"[bold blue]Validating Configuration[/bold blue] ({config_file})\n"
        )

        # Load configuration
        preferences = user_config_manager.get_preferences()

        issues = []

        # Validate font
        font_manager = get_font_manager()
        if not font_manager.is_font_available(preferences.font_family):
            issues.append(f"Font '{preferences.font_family}' is not available")

        # Validate directories
        if preferences.output_directory:
            output_path = Path(preferences.output_directory).expanduser()
            if not output_path.exists() and not preferences.auto_create_dirs:
                issues.append(f"Output directory does not exist: {output_path}")

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if preferences.log_level not in valid_levels:
            issues.append(f"Invalid log level: {preferences.log_level}")

        # Validate generator
        if preferences.preferred_generator not in ["pandoc", "ebooklib"]:
            issues.append(f"Invalid EPUB generator: {preferences.preferred_generator}")

        # Display results
        if issues:
            console.print("[red]❌ Configuration has issues:[/red]")
            for issue in issues:
                console.print(f"  • {issue}")
        else:
            console.print("[green]✅ Configuration is valid[/green]")

    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")


def _convert_config_value(value: str) -> Any:
    """Convert string value to appropriate type."""
    # Boolean values
    if value.lower() in ("true", "yes", "1", "on"):
        return True
    elif value.lower() in ("false", "no", "0", "off"):
        return False

    # Numeric values
    try:
        if "." in value:
            return float(value)
        else:
            return int(value)
    except ValueError:
        pass

    # String value
    return value


def _validate_config_key(key: str) -> bool:
    """Validate configuration key."""
    valid_keys = {
        "font.default_family",
        "font.fallback_family",
        "logging.level",
        "logging.format",
        "logging.file",
        "directories.output",
        "directories.input",
        "directories.working",
        "directories.auto_create",
        "epub.preferred_generator",
        "epub.fallback_enabled",
        "epub.include_toc",
        "epub.compression",
        "processing.max_workers",
        "processing.rate_limit",
        "processing.timeout",
        "images.download_covers",
        "images.quality",
        "images.format",
        "cache.enabled",
        "cache.size_limit",
        "cache.default_ttl",
        "cache.compression",
        "cache.respect_headers",
        "cache.directory",
    }
    return key in valid_keys


@cli.command()
@click.option(
    "--check-pandoc",
    is_flag=True,
    help="Check if Pandoc is installed",
)
def info(check_pandoc: bool):
    """Show system information and dependencies."""
    console.print(f"[bold blue]Web Novel Scraper v{__version__}[/bold blue]")

    info_table = Table(title="System Information")
    info_table.add_column("Component", style="cyan")
    info_table.add_column("Status", style="green")

    # Python version
    info_table.add_row(
        "Python Version",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    # Check Pandoc
    if check_pandoc:
        from wn_dl.core.epub_generator import EPUBGenerator

        epub_gen = EPUBGenerator({})
        pandoc_version = epub_gen.get_pandoc_version()

        if pandoc_version:
            info_table.add_row("Pandoc", f"✅ {pandoc_version}")
        else:
            info_table.add_row("Pandoc", "❌ Not found")

    # Providers
    provider_count = len(list_providers())
    info_table.add_row("Registered Providers", str(provider_count))

    console.print(info_table)


@cli.group()
def cache():
    """Manage web scraping cache."""
    pass


@cache.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format for cache statistics",
)
def status(output_format):
    """Show cache status and statistics."""
    try:
        from .core.cache_manager import CacheManager
        from .core.user_config import get_user_preferences

        # Get user preferences and cache config
        user_prefs = get_user_preferences()
        if not hasattr(user_prefs, "get_cache_config"):
            console.print("[red]Cache configuration not available[/red]")
            return

        cache_config = user_prefs.get_cache_config()

        if not cache_config.enabled:
            console.print("[yellow]Cache is disabled[/yellow]")
            return

        # Initialize cache manager to get stats
        with CacheManager(cache_config) as cache_manager:
            stats = cache_manager.get_stats()
            cache_dir = cache_config.get_cache_directory()

            if output_format == "json":
                import json

                cache_info = {
                    "enabled": cache_config.enabled,
                    "directory": str(cache_dir),
                    "size_limit": cache_config.size_limit,
                    "size_bytes": stats.size_bytes,
                    "entry_count": stats.entry_count,
                    "hits": stats.hits,
                    "misses": stats.misses,
                    "hit_rate": stats.hit_rate,
                    "compression": cache_config.compression,
                    "default_ttl": cache_config.default_ttl,
                    "total_requests": stats.total_requests,
                    "cache_saves": stats.cache_saves,
                    "cache_errors": stats.cache_errors,
                    "validation_requests": stats.validation_requests,
                    "validation_successes": stats.validation_successes,
                    "validation_success_rate": stats.get_validation_success_rate(),
                    "average_cache_time_ms": stats.average_cache_time * 1000,
                    "average_validation_time_ms": stats.average_validation_time * 1000,
                    "bytes_saved": stats.bytes_saved,
                    "compression_ratio": stats.compression_ratio,
                }
                console.print(json.dumps(cache_info, indent=2))
            else:
                # Table format
                from rich.table import Table

                table = Table(
                    title="Cache Status", show_header=True, header_style="bold magenta"
                )
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")

                table.add_row(
                    "Status", "✅ Enabled" if cache_config.enabled else "❌ Disabled"
                )
                table.add_row("Directory", str(cache_dir))
                table.add_row("Size Limit", cache_config.size_limit)
                table.add_row("Current Size", f"{stats.size_bytes / (1024**2):.1f} MB")
                table.add_row("Entry Count", str(stats.entry_count))
                table.add_row("Cache Hits", str(stats.hits))
                table.add_row("Cache Misses", str(stats.misses))
                table.add_row("Hit Rate", f"{stats.hit_rate:.1%}")
                table.add_row("Total Requests", str(stats.total_requests))
                table.add_row("Cache Saves", str(stats.cache_saves))
                table.add_row("Cache Errors", str(stats.cache_errors))
                table.add_row(
                    "Avg Cache Time", f"{stats.average_cache_time * 1000:.2f}ms"
                )
                table.add_row("Bytes Saved", f"{stats.bytes_saved / (1024**2):.1f} MB")
                table.add_row("Compression Ratio", f"{stats.compression_ratio:.2f}")
                table.add_row(
                    "Compression",
                    "✅ Enabled" if cache_config.compression else "❌ Disabled",
                )
                table.add_row("Default TTL", f"{cache_config.default_ttl}s")

                # Validation metrics
                if stats.validation_requests > 0:
                    table.add_row("Validation Requests", str(stats.validation_requests))
                    table.add_row(
                        "Validation Success Rate",
                        f"{stats.get_validation_success_rate():.1%}",
                    )
                    table.add_row(
                        "Avg Validation Time",
                        f"{stats.average_validation_time * 1000:.2f}ms",
                    )

                console.print(table)

                # Provider-specific settings
                if cache_config.providers:
                    console.print("\n[bold]Provider Settings:[/bold]")
                    provider_table = Table(
                        show_header=True, header_style="bold magenta"
                    )
                    provider_table.add_column("Provider", style="cyan")
                    provider_table.add_column("Enabled", style="green")
                    provider_table.add_column("TTL", style="yellow")

                    for (
                        provider_name,
                        provider_config,
                    ) in cache_config.providers.items():
                        enabled = "✅" if provider_config.enabled else "❌"
                        ttl = (
                            f"{provider_config.ttl}s"
                            if provider_config.ttl
                            else "default"
                        )
                        provider_table.add_row(provider_name, enabled, ttl)

                    console.print(provider_table)

    except Exception as e:
        console.print(f"[red]Error getting cache status: {e}[/red]")


@cache.command()
@click.option(
    "--pattern",
    help="URL pattern to match for selective clearing (substring match)",
)
@click.option(
    "--confirm",
    is_flag=True,
    help="Skip confirmation prompt",
)
def clear(pattern, confirm):
    """Clear cache entries."""
    try:
        from .core.cache_manager import CacheManager
        from .core.user_config import get_user_preferences

        # Get user preferences and cache config
        user_prefs = get_user_preferences()
        if not hasattr(user_prefs, "get_cache_config"):
            console.print("[red]Cache configuration not available[/red]")
            return

        cache_config = user_prefs.get_cache_config()

        if not cache_config.enabled:
            console.print("[yellow]Cache is disabled[/yellow]")
            return

        # Confirmation prompt
        if not confirm:
            if pattern:
                message = f"Clear cache entries matching pattern '{pattern}'?"
            else:
                message = "Clear ALL cache entries?"

            if not click.confirm(message):
                console.print("[yellow]Operation cancelled[/yellow]")
                return

        # Clear cache
        import asyncio

        async def clear_cache():
            with CacheManager(cache_config) as cache_manager:
                return await cache_manager.clear(pattern)

        removed_count = asyncio.run(clear_cache())

        if pattern:
            console.print(
                f"[green]Cleared {removed_count} cache entries matching pattern '{pattern}'[/green]"
            )
        else:
            console.print(
                f"[green]Cleared all cache entries ({removed_count} removed)[/green]"
            )

    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")


@cache.command()
@click.option(
    "--provider",
    help="Show configuration for specific provider",
)
def config(provider):
    """Show cache configuration."""
    try:
        from .core.user_config import get_user_preferences

        # Get user preferences and cache config
        user_prefs = get_user_preferences()
        if not hasattr(user_prefs, "get_cache_config"):
            console.print("[red]Cache configuration not available[/red]")
            return

        cache_config = user_prefs.get_cache_config()

        if provider:
            # Show provider-specific configuration
            if provider in cache_config.providers:
                provider_config = cache_config.providers[provider]

                from rich.table import Table

                table = Table(
                    title=f"Cache Configuration - {provider}",
                    show_header=True,
                    header_style="bold magenta",
                )
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("Enabled", "✅" if provider_config.enabled else "❌")
                table.add_row(
                    "TTL",
                    f"{provider_config.ttl}s" if provider_config.ttl else "default",
                )
                table.add_row(
                    "Cache AJAX", "✅" if provider_config.cache_ajax else "❌"
                )
                table.add_row("Cache Errors", str(provider_config.cache_errors))
                table.add_row(
                    "Ignored Query Params",
                    ", ".join(provider_config.ignore_query_params) or "none",
                )

                console.print(table)
            else:
                console.print(
                    f"[yellow]No specific configuration found for provider '{provider}'[/yellow]"
                )
                console.print("[dim]Using default cache settings[/dim]")
        else:
            # Show full configuration
            config_dict = cache_config.to_dict()

            import json

            console.print("[bold]Cache Configuration:[/bold]")
            console.print(json.dumps(config_dict, indent=2))

    except Exception as e:
        console.print(f"[red]Error showing cache configuration: {e}[/red]")


@cli.group()
@click.pass_context
def novels(ctx):
    """Manage scraped novels and EPUB generation."""
    pass


@novels.command("migrate")
@click.option(
    "--status",
    is_flag=True,
    help="Show migration status without applying migrations",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force apply migrations even if some fail",
)
@click.pass_context
def migrate_database(ctx, status: bool, force: bool):
    """Manage database migrations."""
    try:
        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Check if database is enabled
        if not user_preferences or not user_preferences.enable_database:
            console.print("[red]Database is not enabled in user preferences[/red]")
            return

        from wn_dl.core.database_migrations import create_migrator

        # Create migrator
        migrator = create_migrator(user_preferences.database_path)

        if status:
            # Show migration status
            migration_status = migrator.get_migration_status()

            console.print("\n[blue]📊 Database Migration Status[/blue]")

            # Create status table
            from rich.table import Table

            table = Table(title="Migration Status")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Total Migrations", str(migration_status["total_migrations"]))
            table.add_row("Applied", str(migration_status["applied_count"]))
            table.add_row("Pending", str(migration_status["pending_count"]))
            table.add_row(
                "Current Version", migration_status["current_version"] or "None"
            )

            console.print(table)

            # Show pending migrations
            if migration_status["pending_versions"]:
                console.print("\n[yellow]📋 Pending Migrations:[/yellow]")
                for version in migration_status["pending_versions"]:
                    migration = migrator.migrations[version]
                    console.print(f"  • {version}: {migration.name}")
                    console.print(f"    {migration.description}")
            else:
                console.print("\n[green]✅ All migrations are up to date[/green]")

        else:
            # Apply migrations
            console.print("[blue]🔄 Applying database migrations...[/blue]")

            stats = migrator.migrate()

            if stats["applied"] > 0:
                console.print(
                    f"[green]✅ Applied {stats['applied']} migrations successfully[/green]"
                )

            if stats["failed"] > 0:
                console.print(f"[red]❌ {stats['failed']} migrations failed[/red]")
                if not force:
                    sys.exit(1)

            if stats["pending"] == 0:
                console.print("[green]✅ Database is up to date[/green]")

    except Exception as e:
        console.print(f"[red]Error managing migrations: {e}[/red]")
        sys.exit(1)


@novels.command("list")
@click.option(
    "--directory",
    "-d",
    help="Directory to scan for novels (uses user preference if not specified)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--no-epub",
    is_flag=True,
    help="Show only novels without EPUB files",
)
@click.option(
    "--status",
    type=click.Choice(["not_started", "in_progress", "completed", "failed", "paused"]),
    help="Filter by scraping status",
)
@click.option(
    "--provider",
    help="Filter by provider (e.g., NovelFull, NovelBin)",
)
@click.option(
    "--search",
    help="Search in title, author, or description",
)
@click.option(
    "--limit",
    type=int,
    help="Maximum number of results to show",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "simple", "json"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list_novels(
    ctx,
    directory: Optional[Path],
    no_epub: bool,
    status: Optional[str],
    provider: Optional[str],
    search: Optional[str],
    limit: Optional[int],
    output_format: str,
):
    """List all scraped novels with advanced filtering options."""
    try:
        # Get user preferences for default directory
        user_preferences = ctx.obj.get("user_preferences")

        # Determine directory to scan
        if directory is None:
            if user_preferences and user_preferences.output_directory:
                directory = Path(user_preferences.output_directory)
            else:
                directory = Path.cwd()

        # Initialize discovery service
        discovery_service = NovelDiscoveryService(str(directory))

        # Use database filtering if available and filters are specified
        if discovery_service.db_service and (status or provider or search or limit):
            from wn_dl.core.models import ScrapingStatus

            # Convert status string to enum
            status_filter = None
            if status:
                status_filter = ScrapingStatus(status)

            # Use database service for advanced filtering
            novel_records = discovery_service.db_service.list_novels(
                status=status_filter,
                provider=provider,
                has_epub=False if no_epub else None,
                search_term=search,
                limit=limit,
                order_by="updated_at",
                order_desc=True,
            )

            # Convert records to NovelInfo objects
            novels = []
            for record in novel_records:
                novel_info = discovery_service._convert_record_to_novel_info(record)
                if novel_info:
                    novels.append(novel_info)
        else:
            # Fallback to filesystem discovery
            if no_epub:
                novels = discovery_service.get_novels_without_epub()
            else:
                novels = discovery_service.discover_novels()

            # Apply client-side filtering for filesystem mode
            if search:
                search_lower = search.lower()
                novels = [
                    novel
                    for novel in novels
                    if search_lower in novel.title.lower()
                    or search_lower in novel.author.lower()
                    or (novel.description and search_lower in novel.description.lower())
                ]

            if limit:
                novels = novels[:limit]

        if not novels:
            console.print(f"[yellow]No novels found in {directory}[/yellow]")
            return

        # Display results based on format
        if output_format == "json":
            import json

            novels_data = []
            for novel in novels:
                novels_data.append(
                    {
                        "title": novel.title,
                        "author": novel.author,
                        "directory": str(novel.directory),
                        "markdown_file": str(novel.markdown_file),
                        "markdown_size": novel.markdown_size,
                        "has_epub": novel.has_epub,
                        "epub_file": str(novel.epub_file) if novel.epub_file else None,
                        "epub_size": novel.epub_size,
                        "chapter_count": novel.chapter_count,
                        "status": novel.status,
                        "modified_at": (
                            novel.modified_at.isoformat() if novel.modified_at else None
                        ),
                    }
                )
            console.print(json.dumps(novels_data, indent=2))

        elif output_format == "simple":
            for novel in novels:
                epub_status = "✅" if novel.has_epub else "❌"
                console.print(f"{epub_status} {novel.title} by {novel.author}")

        else:  # table format
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Title", style="cyan", no_wrap=False, max_width=40)
            table.add_column("Author", style="green", max_width=20)
            table.add_column("Status", style="blue", max_width=12)
            table.add_column("Chapters", justify="right", style="yellow")
            table.add_column("MD Size", justify="right", style="white")
            table.add_column("EPUB", justify="center", style="green")
            table.add_column("Modified", style="dim", max_width=12)

            for novel in novels:
                # Format file size
                md_size = _format_file_size(novel.markdown_size)

                # EPUB status
                epub_status = "✅" if novel.has_epub else "❌"

                # Format modified date
                modified = (
                    novel.modified_at.strftime("%Y-%m-%d")
                    if novel.modified_at
                    else "Unknown"
                )

                # Chapter count
                chapters = (
                    str(novel.chapter_count) if novel.chapter_count else "Unknown"
                )

                # Status
                status = novel.status or "Unknown"

                table.add_row(
                    novel.title,
                    novel.author,
                    status,
                    chapters,
                    md_size,
                    epub_status,
                    modified,
                )

            console.print(
                f"\n[bold blue]Found {len(novels)} novels in {directory}[/bold blue]\n"
            )
            console.print(table)

            # Summary
            epub_count = sum(1 for novel in novels if novel.has_epub)
            console.print(f"\n[green]📚 {len(novels)} novels total[/green]")
            console.print(f"[green]📖 {epub_count} with EPUB files[/green]")
            console.print(
                f"[yellow]📝 {len(novels) - epub_count} without EPUB files[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error listing novels: {e}[/red]")
        sys.exit(1)


@novels.command("regenerate")
@click.option(
    "--name",
    "-n",
    help="Novel name to regenerate (searches by title)",
    default=None,
)
@click.option(
    "--input",
    "-i",
    "input_file",
    help="Direct path to markdown file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--directory",
    "-d",
    help="Directory to search for novels (uses user preference if not specified)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--output",
    "-o",
    help="Output directory for EPUB file (uses novel directory if not specified)",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--all",
    "regenerate_all",
    is_flag=True,
    help="Regenerate EPUB for all novels",
)
@click.option(
    "--missing-epub",
    is_flag=True,
    help="Regenerate only novels without EPUB files",
)
@click.option(
    "--font",
    help="Font family to use for EPUB (overrides user preference)",
    default=None,
)
@click.option(
    "--use-ebooklib",
    is_flag=True,
    help="Force use of EbookLib instead of Pandoc",
)
@click.option(
    "--silent",
    is_flag=True,
    help="Silent mode - minimal output",
)
@click.pass_context
def regenerate_novel(
    ctx,
    name: Optional[str],
    input_file: Optional[Path],
    directory: Optional[Path],
    output: Optional[Path],
    regenerate_all: bool,
    missing_epub: bool,
    font: Optional[str],
    use_ebooklib: bool,
    silent: bool,
):
    """Regenerate EPUB for novels (single or bulk)."""
    try:
        # Validate input parameters
        options_count = sum(
            [bool(name), bool(input_file), regenerate_all, missing_epub]
        )
        if options_count == 0:
            console.print(
                "[red]Error: Must specify one of: --name, --input, --all, or --missing-epub[/red]"
            )
            console.print("Use --help for more information")
            sys.exit(1)

        if options_count > 1:
            console.print("[red]Error: Cannot specify multiple operation modes[/red]")
            sys.exit(1)

        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Determine search directory
        if directory is None:
            if user_preferences and user_preferences.output_directory:
                directory = Path(user_preferences.output_directory)
            else:
                directory = Path.cwd()

        discovery_service = NovelDiscoveryService(str(directory))

        # Handle different operation modes
        if input_file:
            # Single file mode
            novels_to_process = [{"input_file": input_file, "output_dir": output}]

        elif name:
            # Single novel by name
            novel_info = discovery_service.find_novel_by_name(name)

            if not novel_info:
                console.print(f"[red]Novel '{name}' not found in {directory}[/red]")
                console.print("Use 'wn-dl novels list' to see available novels")
                sys.exit(1)

            # Check if markdown file exists
            if not novel_info.markdown_file or not novel_info.markdown_file.exists():
                console.print(f"[red]Markdown file not found for novel '{name}'[/red]")
                console.print(f"Expected location: {novel_info.markdown_file}")
                sys.exit(1)

            novels_to_process = [
                {
                    "input_file": novel_info.markdown_file,
                    "output_dir": output or novel_info.directory,
                    "title": novel_info.title,
                }
            ]

        elif regenerate_all:
            # All novels
            if not silent:
                console.print("[cyan]🔍 Discovering novels in directory...[/cyan]")

            all_novels = discovery_service.discover_novels()

            if not silent:
                console.print(
                    f"[cyan]📚 Found {len(all_novels)} novels, checking for markdown files...[/cyan]"
                )

            novels_to_process = []
            skipped_count = 0

            for novel in all_novels:
                # Skip novels without valid markdown files
                if not novel.markdown_file or not novel.markdown_file.exists():
                    skipped_count += 1
                    if not silent:
                        console.print(
                            f"[yellow]⏭️ Skipping '{novel.title}': No markdown file found[/yellow]"
                        )
                    continue
                novels_to_process.append(
                    {
                        "input_file": novel.markdown_file,
                        "output_dir": output or novel.directory,
                        "title": novel.title,
                    }
                )

            if not silent:
                console.print(
                    f"[green]✅ Ready to process {len(novels_to_process)} novels[/green]"
                )
                if skipped_count > 0:
                    console.print(
                        f"[yellow]⚠️ Skipped {skipped_count} novels without markdown files[/yellow]"
                    )

        elif missing_epub:
            # Only novels without EPUB
            if not silent:
                console.print("[cyan]🔍 Finding novels without EPUB files...[/cyan]")

            novels_without_epub = discovery_service.get_novels_without_epub()

            if not silent:
                console.print(
                    f"[cyan]📚 Found {len(novels_without_epub)} novels without EPUB, checking for markdown files...[/cyan]"
                )

            novels_to_process = []
            skipped_count = 0

            for novel in novels_without_epub:
                # Skip novels without valid markdown files
                if not novel.markdown_file or not novel.markdown_file.exists():
                    skipped_count += 1
                    if not silent:
                        console.print(
                            f"[yellow]⏭️ Skipping '{novel.title}': No markdown file found[/yellow]"
                        )
                    continue
                novels_to_process.append(
                    {
                        "input_file": novel.markdown_file,
                        "output_dir": output or novel.directory,
                        "title": novel.title,
                    }
                )

            if not silent:
                console.print(
                    f"[green]✅ Ready to generate EPUBs for {len(novels_to_process)} novels[/green]"
                )
                if skipped_count > 0:
                    console.print(
                        f"[yellow]⚠️ Skipped {skipped_count} novels without markdown files[/yellow]"
                    )

        if not novels_to_process:
            console.print("[yellow]No novels found to process[/yellow]")
            return

        # Process novels
        success_count = 0
        error_count = 0

        # Use progress bar for bulk operations
        if len(novels_to_process) > 1:
            if not silent:
                console.print(
                    f"\n[bold cyan]🚀 Starting EPUB regeneration for {len(novels_to_process)} novels...[/bold cyan]"
                )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("•"),
                TextColumn("[green]✅ {task.completed}[/green]"),
                TextColumn("[red]❌ {task.fields[errors]}[/red]"),
                console=console,
                transient=False,
            ) as progress:
                task = progress.add_task(
                    f"Regenerating EPUBs...",
                    total=len(novels_to_process),
                    errors=0,
                )

                for novel_data in novels_to_process:
                    title = novel_data.get("title") or (
                        novel_data["input_file"].stem
                        if novel_data["input_file"]
                        else "Unknown"
                    )

                    # Truncate long titles for progress display
                    display_title = title[:40] + "..." if len(title) > 40 else title
                    progress.update(task, description=f"📖 {display_title}")

                    try:
                        # Call generate_epub directly to avoid ctx.invoke issues
                        from wn_dl.config import ConfigManager
                        from wn_dl.core.epub_generator import EPUBGenerator

                        # Get user preferences for configuration
                        user_preferences = ctx.obj.get("user_preferences")
                        config_manager = ConfigManager()
                        config = config_manager.get_app_config()

                        # Apply font preference if specified
                        if font:
                            config.setdefault("epub", {})["font"] = font

                        # Apply use_ebooklib preference if specified
                        if use_ebooklib:
                            config.setdefault("epub", {})["use_ebooklib"] = True

                        # Create EPUB generator (not silent for better feedback)
                        epub_generator = EPUBGenerator(
                            config,
                            silent=silent,  # Use the user's silent preference
                        )

                        # Generate EPUB
                        result = epub_generator.generate_epub(
                            str(novel_data["input_file"]),
                            novel_data["output_dir"],
                            novel_data.get("title", novel_data["input_file"].stem),
                        )

                        if result:
                            success_count += 1
                            if not silent:
                                epub_path = Path(result)
                                file_size_mb = epub_path.stat().st_size / (1024 * 1024)
                                progress.console.print(
                                    f"[green]✅ {title}: {epub_path.name} ({file_size_mb:.1f} MB)[/green]"
                                )
                        else:
                            error_count += 1
                            progress.update(task, errors=error_count)
                            if not silent:
                                progress.console.print(
                                    f"[red]❌ {title}: EPUB generation failed[/red]"
                                )

                    except Exception as e:
                        error_count += 1
                        progress.update(task, errors=error_count)
                        if not silent:
                            progress.console.print(
                                f"[red]❌ {title}: {str(e)[:100]}{'...' if len(str(e)) > 100 else ''}[/red]"
                            )

                    progress.advance(task)
        else:
            # Single novel or silent mode
            for novel_data in novels_to_process:
                try:
                    if not silent:
                        title = novel_data.get("title") or (
                            novel_data["input_file"].stem
                            if novel_data["input_file"]
                            else "Unknown"
                        )
                        console.print(f"[blue]Regenerating EPUB for: {title}[/blue]")

                    # Call generate_epub directly to avoid ctx.invoke issues
                    from wn_dl.config import ConfigManager
                    from wn_dl.core.epub_generator import EPUBGenerator

                    # Get user preferences for configuration
                    user_preferences = ctx.obj.get("user_preferences")
                    config_manager = ConfigManager()
                    config = config_manager.get_app_config()

                    # Apply font preference if specified
                    if font:
                        config.setdefault("epub", {})["font"] = font

                    # Apply use_ebooklib preference if specified
                    if use_ebooklib:
                        config.setdefault("epub", {})["use_ebooklib"] = True

                    # Create EPUB generator
                    epub_generator = EPUBGenerator(config, silent=silent)

                    # Generate EPUB
                    result = epub_generator.generate_epub(
                        str(novel_data["input_file"]),
                        novel_data["output_dir"],
                        novel_data.get("title", novel_data["input_file"].stem),
                    )

                    if result:
                        success_count += 1
                        if not silent:
                            epub_path = Path(result)
                            file_size_mb = epub_path.stat().st_size / (1024 * 1024)
                            console.print(
                                f"[green]✅ EPUB regenerated successfully:[/green] {epub_path.name} ({file_size_mb:.1f} MB)"
                            )
                    else:
                        error_count += 1
                        if not silent:
                            title = novel_data.get("title") or (
                                novel_data["input_file"].stem
                                if novel_data["input_file"]
                                else "Unknown"
                            )
                            console.print(
                                f"[red]Error processing {title}: EPUB generation failed[/red]"
                            )

                except Exception as e:
                    error_count += 1
                    if not silent:
                        title = novel_data.get("title") or (
                            novel_data["input_file"].stem
                            if novel_data["input_file"]
                            else "Unknown"
                        )
                        console.print(f"[red]Error processing {title}: {e}[/red]")

        # Summary for bulk operations
        if len(novels_to_process) > 1 and not silent:
            console.print(f"\n[bold cyan]📊 EPUB Regeneration Summary[/bold cyan]")
            console.print(
                f"[green]✅ Successfully processed: {success_count}/{len(novels_to_process)}[/green]"
            )
            if error_count > 0:
                console.print(
                    f"[red]❌ Failed: {error_count}/{len(novels_to_process)}[/red]"
                )

            success_rate = (
                (success_count / len(novels_to_process)) * 100
                if novels_to_process
                else 0
            )
            if success_rate == 100:
                console.print(
                    f"[bold green]🎉 All novels processed successfully! (100%)[/bold green]"
                )
            elif success_rate >= 80:
                console.print(
                    f"[green]✨ Most novels processed successfully ({success_rate:.1f}%)[/green]"
                )
            elif success_rate >= 50:
                console.print(
                    f"[yellow]⚠️ Some issues encountered ({success_rate:.1f}% success rate)[/yellow]"
                )
            else:
                console.print(
                    f"[red]💥 Many errors encountered ({success_rate:.1f}% success rate)[/red]"
                )
        elif len(novels_to_process) == 1 and success_count == 1 and not silent:
            console.print(f"[bold green]🎉 EPUB regenerated successfully![/bold green]")

    except Exception as e:
        if not silent:
            console.print(f"[red]Error regenerating novel: {e}[/red]")
        sys.exit(1)


@novels.command("sync")
@click.option(
    "--directory",
    "-d",
    help="Directory to sync with database (uses user preference if not specified)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--cleanup",
    is_flag=True,
    help="Remove orphaned database records for non-existent directories",
)
@click.pass_context
def sync_database(ctx, directory: Optional[Path], cleanup: bool):
    """Sync database with filesystem."""
    try:
        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Check if database is enabled
        if not user_preferences or not user_preferences.enable_database:
            console.print("[red]Database is not enabled in user preferences[/red]")
            return

        # Determine directory to sync
        if directory is None:
            if user_preferences and user_preferences.output_directory:
                directory = Path(user_preferences.output_directory)
            else:
                directory = Path.cwd()

        from wn_dl.core.novel_database_service import NovelDatabaseService

        # Initialize database service
        db_service = NovelDatabaseService(user_preferences.database_path)

        console.print(f"[blue]Syncing database with {directory}...[/blue]")

        # Sync from filesystem with progress
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            transient=True,
        ) as progress:
            # Create progress tracking variables
            current_task = None
            total_novels = 0

            def progress_callback(msg: str):
                nonlocal current_task, total_novels

                # Extract progress information from message
                if "Processing" in msg and "/" in msg:
                    # Extract current/total from "Processing X/Y: Title"
                    try:
                        parts = msg.split(":")
                        if len(parts) >= 2:
                            progress_part = parts[0].strip()
                            title_part = parts[1].strip()

                            # Extract numbers from "Processing X/Y"
                            if "Processing" in progress_part:
                                numbers = progress_part.split("Processing")[1].strip()
                                if "/" in numbers:
                                    current, total = numbers.split("/")
                                    current = int(current.strip())
                                    total = int(total.strip())

                                    # Create or update progress task
                                    if current_task is None:
                                        current_task = progress.add_task(
                                            f"Syncing novels", total=total
                                        )
                                        total_novels = total

                                    # Update progress
                                    progress.update(
                                        current_task,
                                        completed=current,
                                        description=f"Processing: {title_part[:50]}...",
                                    )
                    except (ValueError, IndexError):
                        # Fallback to simple status update
                        if current_task is None:
                            current_task = progress.add_task(msg, total=None)
                        else:
                            progress.update(current_task, description=msg)
                else:
                    # Handle other status messages
                    if current_task is None:
                        current_task = progress.add_task(msg, total=None)
                    else:
                        progress.update(current_task, description=msg)

            stats = db_service.sync_from_filesystem(
                str(directory), progress_callback=progress_callback
            )

        # Cleanup orphaned records if requested
        cleaned_count = 0
        if cleanup:
            console.print("[blue]Cleaning up orphaned records...[/blue]")
            cleaned_count = db_service.cleanup_orphaned_records()

        # Display results
        console.print(f"\n[green]✅ Sync completed successfully![/green]")
        console.print(f"[cyan]📚 Discovered: {stats['discovered']} novels[/cyan]")
        console.print(f"[green]➕ Created: {stats['created']} new records[/green]")
        console.print(
            f"[yellow]🔄 Updated: {stats['updated']} existing records[/yellow]"
        )
        if stats["errors"] > 0:
            console.print(f"[red]❌ Errors: {stats['errors']}[/red]")
        if cleanup and cleaned_count > 0:
            console.print(
                f"[blue]🧹 Cleaned up: {cleaned_count} orphaned records[/blue]"
            )

        db_service.close()

    except Exception as e:
        console.print(f"[red]Error syncing database: {e}[/red]")
        sys.exit(1)


@novels.command("stats")
@click.pass_context
def database_stats(ctx):
    """Show database statistics."""
    try:
        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Check if database is enabled
        if not user_preferences or not user_preferences.enable_database:
            console.print("[red]Database is not enabled in user preferences[/red]")
            return

        from wn_dl.core.novel_database_service import NovelDatabaseService

        # Initialize database service
        db_service = NovelDatabaseService(user_preferences.database_path)

        # Get statistics
        stats = db_service.get_statistics()

        # Create statistics table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Total Novels", str(stats["total_novels"]))
        table.add_row("Novels with EPUB", str(stats["novels_with_epub"]))
        table.add_row("EPUB Coverage", f"{stats['epub_percentage']:.1f}%")
        table.add_row("Recent Updates (7 days)", str(stats["recent_updates"]))

        console.print("\n[bold blue]📊 Database Statistics[/bold blue]\n")
        console.print(table)

        # Status breakdown
        if stats["status_counts"]:
            console.print("\n[bold blue]📈 Status Breakdown[/bold blue]\n")
            status_table = Table(show_header=True, header_style="bold magenta")
            status_table.add_column("Status", style="cyan")
            status_table.add_column("Count", style="green", justify="right")

            for status, count in stats["status_counts"].items():
                status_table.add_row(status.replace("_", " ").title(), str(count))

            console.print(status_table)

        # Provider breakdown
        if stats["provider_counts"]:
            console.print("\n[bold blue]🌐 Provider Breakdown[/bold blue]\n")
            provider_table = Table(show_header=True, header_style="bold magenta")
            provider_table.add_column("Provider", style="cyan")
            provider_table.add_column("Count", style="green", justify="right")

            for provider, count in stats["provider_counts"].items():
                provider_name = provider or "Unknown"
                provider_table.add_row(provider_name, str(count))

            console.print(provider_table)

        db_service.close()

    except Exception as e:
        console.print(f"[red]Error getting database statistics: {e}[/red]")
        sys.exit(1)


@novels.command("backup")
@click.option(
    "--output",
    "-o",
    help="Backup file path (default: novels_backup_YYYYMMDD_HHMMSS.db)",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
)
@click.pass_context
def backup_database(ctx, output: Optional[Path]):
    """Create a backup of the novels database."""
    try:
        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Check if database is enabled
        if not user_preferences or not user_preferences.enable_database:
            console.print("[red]Database is not enabled in user preferences[/red]")
            return

        from datetime import datetime

        from wn_dl.core.novel_database_service import NovelDatabaseService

        # Generate default backup filename if not provided
        if output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = Path(f"novels_backup_{timestamp}.db")

        # Initialize database service
        db_service = NovelDatabaseService(user_preferences.database_path)

        console.print(f"[blue]Creating backup: {output}[/blue]")

        # Create backup
        success = db_service.db_manager.backup_database(str(output))

        if success:
            file_size = output.stat().st_size if output.exists() else 0
            console.print(f"[green]✅ Backup created successfully![/green]")
            console.print(f"[cyan]📁 File: {output}[/cyan]")
            console.print(f"[cyan]📏 Size: {_format_file_size(file_size)}[/cyan]")
        else:
            console.print(f"[red]❌ Failed to create backup[/red]")
            sys.exit(1)

        db_service.close()

    except Exception as e:
        console.print(f"[red]Error creating backup: {e}[/red]")
        sys.exit(1)


@novels.command("migrate")
@click.option(
    "--status",
    is_flag=True,
    help="Show migration status without applying",
)
@click.pass_context
def manage_migrations(ctx, status: bool):
    """Manage database migrations."""
    try:
        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Check if database is enabled
        if not user_preferences or not user_preferences.enable_database:
            console.print("[red]Database is not enabled in user preferences[/red]")
            return

        from wn_dl.core.database_migrations import create_migrator
        from wn_dl.core.novel_database_service import NovelDatabaseService

        # Get database URL from service
        db_service = NovelDatabaseService(user_preferences.database_path)
        database_url = db_service.db_manager.database_url

        migrator = create_migrator(database_url)

        if status:
            # Show migration status
            migration_status = migrator.get_migration_status()

            console.print("\n[blue]📊 Database Migration Status[/blue]")
            console.print(f"Total migrations: {migration_status['total_migrations']}")
            console.print(f"Applied: {migration_status['applied_count']}")
            console.print(f"Pending: {migration_status['pending_count']}")

            if migration_status["current_version"]:
                console.print(f"Current version: {migration_status['current_version']}")

            if migration_status["pending_versions"]:
                console.print("\n[yellow]🔄 Pending migrations:[/yellow]")
                for version in migration_status["pending_versions"]:
                    console.print(f"  • {version}")
            else:
                console.print("\n[green]✅ All migrations applied[/green]")
        else:
            # Apply migrations
            console.print("[blue]🔄 Running database migrations...[/blue]")
            stats = migrator.migrate()

            if stats["applied"] > 0:
                console.print(
                    f"[green]✅ Applied {stats['applied']} migrations[/green]"
                )
            if stats["failed"] > 0:
                console.print(
                    f"[red]❌ Failed to apply {stats['failed']} migrations[/red]"
                )
            if stats["pending"] == 0:
                console.print("[green]✅ No pending migrations[/green]")

        db_service.close()

    except Exception as e:
        console.print(f"[red]❌ Migration error: {e}[/red]")
        sys.exit(1)


@novels.command("restore")
@click.argument(
    "backup_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--confirm",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.pass_context
def restore_database(ctx, backup_file: Path, confirm: bool):
    """Restore database from backup file."""
    try:
        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Check if database is enabled
        if not user_preferences or not user_preferences.enable_database:
            console.print("[red]Database is not enabled in user preferences[/red]")
            return

        # Confirmation prompt
        if not confirm:
            console.print(
                f"[yellow]⚠️  This will replace the current database with the backup from:[/yellow]"
            )
            console.print(f"[cyan]{backup_file}[/cyan]")
            console.print(f"[red]All current data will be lost![/red]")

            if not click.confirm("Are you sure you want to continue?"):
                console.print("[yellow]Restore cancelled[/yellow]")
                return

        from wn_dl.core.novel_database_service import NovelDatabaseService

        # Initialize database service
        db_service = NovelDatabaseService(user_preferences.database_path)

        console.print(f"[blue]Restoring from backup: {backup_file}[/blue]")

        # Restore backup
        success = db_service.db_manager.restore_database(str(backup_file))

        if success:
            console.print(f"[green]✅ Database restored successfully![/green]")
            console.print(f"[cyan]📁 Restored from: {backup_file}[/cyan]")
        else:
            console.print(f"[red]❌ Failed to restore database[/red]")
            sys.exit(1)

        db_service.close()

    except Exception as e:
        console.print(f"[red]Error restoring database: {e}[/red]")
        sys.exit(1)


@novels.command("import")
@click.option(
    "--directory",
    "-d",
    help="Directory to import novels from (default: /home/sugeng/novels)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("/home/sugeng/novels"),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be imported without actually doing it",
)
@click.option(
    "--force-update",
    is_flag=True,
    help="Update existing records even if they already exist",
)
@click.pass_context
def import_novels(ctx, directory: Path, dry_run: bool, force_update: bool):
    """Import existing novels from filesystem to database."""
    try:
        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Check if database is enabled
        if not user_preferences or not user_preferences.enable_database:
            console.print("[red]Database is not enabled in user preferences[/red]")
            return

        from wn_dl.core.models import NovelMetadata, NovelStatus
        from wn_dl.core.novel_database_service import NovelDatabaseService
        from wn_dl.core.novel_discovery import NovelDiscoveryService

        # Initialize database service
        db_service = NovelDatabaseService(user_preferences.database_path)

        console.print(f"[blue]Importing novels from: {directory}[/blue]")
        if dry_run:
            console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]")

        # Use discovery service to find novels
        discovery_service = NovelDiscoveryService(str(directory))
        novels = discovery_service._discover_novels_from_filesystem(directory)

        console.print(f"[cyan]Found {len(novels)} novels to process[/cyan]")

        stats = {
            "scanned": len(novels),
            "imported": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

        # Process each novel
        with console.status("[bold green]Processing novels...") as status:
            for i, novel in enumerate(novels, 1):
                status.update(
                    f"[bold green]Processing {i}/{len(novels)}: {novel.title}"
                )

                try:
                    # Check if novel already exists in database
                    existing_record = db_service.get_novel_by_directory(
                        str(novel.directory)
                    )

                    if existing_record and not force_update:
                        stats["skipped"] += 1
                        continue

                    # Create metadata from discovered novel info
                    metadata = NovelMetadata(
                        title=novel.title,
                        author=novel.author,
                        description=novel.description or "",
                        source_url=f"file://{novel.directory}",
                        chapter_count=novel.chapter_count,
                        word_count=getattr(novel, "word_count", None),
                        provider="Imported",
                        scraped_at=novel.created_at,
                    )

                    if dry_run:
                        if existing_record:
                            stats["updated"] += 1
                        else:
                            stats["imported"] += 1
                        continue

                    if existing_record:
                        # Update existing record
                        db_service.update_novel(
                            existing_record.id,
                            metadata=metadata,
                            markdown_file_path=(
                                str(novel.markdown_file)
                                if novel.markdown_file
                                else None
                            ),
                            epub_file_path=(
                                str(novel.epub_file) if novel.epub_file else None
                            ),
                            cover_file_path=(
                                str(novel.cover_file) if novel.cover_file else None
                            ),
                            markdown_file_size=novel.markdown_size,
                            epub_file_size=novel.epub_size,
                            has_epub=novel.has_epub,
                            has_cover=novel.has_cover,
                            total_chapters=novel.chapter_count,
                        )
                        stats["updated"] += 1
                    else:
                        # Create new record
                        novel_record = db_service.create_novel(
                            metadata, str(novel.directory)
                        )

                        # Update file paths
                        db_service.update_file_paths(
                            metadata.source_url,
                            markdown_path=(
                                str(novel.markdown_file)
                                if novel.markdown_file
                                else None
                            ),
                            epub_path=str(novel.epub_file) if novel.epub_file else None,
                            cover_path=(
                                str(novel.cover_file) if novel.cover_file else None
                            ),
                        )

                        stats["imported"] += 1

                except Exception as e:
                    console.print(f"[red]Error processing {novel.title}: {e}[/red]")
                    stats["errors"] += 1

        # Display results
        console.print(f"\n[green]✅ Import completed![/green]")
        console.print(f"[cyan]📚 Scanned: {stats['scanned']} novels[/cyan]")
        console.print(f"[green]➕ Imported: {stats['imported']} new novels[/green]")
        console.print(
            f"[yellow]🔄 Updated: {stats['updated']} existing novels[/yellow]"
        )
        console.print(f"[blue]⏭️ Skipped: {stats['skipped']} novels[/blue]")
        if stats["errors"] > 0:
            console.print(f"[red]❌ Errors: {stats['errors']} novels[/red]")

        # Show database statistics
        if not dry_run:
            db_stats = db_service.get_statistics()
            console.print(f"\n[bold blue]📊 Database Statistics[/bold blue]")
            console.print(f"[cyan]Total novels: {db_stats['total_novels']}[/cyan]")
            console.print(
                f"[green]Novels with EPUB: {db_stats['novels_with_epub']}[/green]"
            )

        db_service.close()

    except Exception as e:
        console.print(f"[red]Error importing novels: {e}[/red]")
        sys.exit(1)


@novels.command("copy-epubs")
@click.option(
    "--output",
    "-o",
    help="Output directory to copy EPUBs to",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
)
@click.option(
    "--directory",
    "-d",
    help="Directory to scan for novels (uses user preference if not specified)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
)
@click.option(
    "--status-filter",
    "-s",
    help="Filter novels by status (complete, ongoing, hiatus, dropped, etc.)",
    default=None,
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be copied without actually copying",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite existing files in output directory",
)
@click.pass_context
def copy_epubs(
    ctx,
    output: Path,
    directory: Optional[Path],
    status_filter: Optional[str],
    dry_run: bool,
    overwrite: bool,
):
    """Copy all EPUB files to a directory with status suffixes for easy transfer to e-readers."""
    try:
        import shutil

        from wn_dl.core.novel_database_service import NovelDatabaseService
        from wn_dl.core.novel_discovery import NovelDiscoveryService

        # Get user preferences
        user_preferences = ctx.obj.get("user_preferences")

        # Use provided directory or fall back to user preference
        if directory is None:
            if user_preferences and user_preferences.input_directory:
                directory = Path(user_preferences.input_directory)
            else:
                directory = Path.cwd()

        # Create output directory if it doesn't exist
        if not dry_run:
            output.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]📁 Output directory: {output}[/green]")
        else:
            console.print(
                f"[yellow]📁 Would create output directory: {output}[/yellow]"
            )

        # Initialize database service - prefer database for faster scanning
        db_service = None
        novels_with_epub = []

        if user_preferences and user_preferences.enable_database:
            try:
                console.print(
                    f"[cyan]📚 Using database for fast EPUB scanning...[/cyan]"
                )
                db_service = NovelDatabaseService(user_preferences.database_path)

                # Get all novels with EPUB files from database
                all_novels = db_service.get_all_novels()
                db_novels_with_epub = [
                    novel
                    for novel in all_novels
                    if novel.has_epub and novel.epub_file_path
                ]

                console.print(
                    f"[cyan]Found {len(db_novels_with_epub)} novels with EPUB files in database[/cyan]"
                )

                # Convert database novels to a format compatible with the rest of the code
                class DatabaseNovel:
                    def __init__(self, db_novel):
                        self.title = (
                            db_novel.metadata.title if db_novel.metadata else "Unknown"
                        )
                        self.epub_file = (
                            Path(db_novel.epub_file_path)
                            if db_novel.epub_file_path
                            else None
                        )
                        self.status = self._extract_status(db_novel)
                        self.has_epub = db_novel.has_epub

                    def _extract_status(self, db_novel):
                        if not db_novel.metadata:
                            return "unknown"
                        if hasattr(db_novel.metadata, "status"):
                            return db_novel.metadata.status.lower()
                        elif hasattr(db_novel.metadata, "novel_status"):
                            return db_novel.metadata.novel_status.lower()
                        return "unknown"

                novels_with_epub = [
                    DatabaseNovel(novel)
                    for novel in db_novels_with_epub
                    if novel.epub_file_path and Path(novel.epub_file_path).exists()
                ]

                console.print(
                    f"[cyan]Verified {len(novels_with_epub)} EPUB files exist on disk[/cyan]"
                )

            except Exception as e:
                console.print(f"[yellow]Warning: Could not use database: {e}[/yellow]")
                console.print(
                    f"[yellow]Falling back to filesystem scanning...[/yellow]"
                )
                db_service = None

        # Fallback to filesystem scanning if database is not available
        if not novels_with_epub:
            console.print(f"[cyan]📚 Scanning filesystem in: {directory}[/cyan]")

            # Initialize discovery service
            discovery_service = NovelDiscoveryService()
            novels = discovery_service.discover_novels(directory)

            if not novels:
                console.print(
                    "[yellow]No novels found in the specified directory[/yellow]"
                )
                return

            # Filter novels that have EPUB files
            novels_with_epub = [
                novel for novel in novels if novel.has_epub and novel.epub_file
            ]

            if not novels_with_epub:
                console.print("[yellow]No novels with EPUB files found[/yellow]")
                return

            console.print(
                f"[cyan]Found {len(novels_with_epub)} novels with EPUB files[/cyan]"
            )

        # Process each novel
        stats = {"copied": 0, "skipped": 0, "errors": 0}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Copying EPUBs...", total=len(novels_with_epub))

            for novel in novels_with_epub:
                try:
                    progress.update(
                        task, description=f"Processing {novel.title[:30]}..."
                    )

                    # Get novel status - either from database novel object or filesystem novel
                    if hasattr(novel, "status"):
                        # Database novel already has status
                        novel_status = novel.status
                    else:
                        # Filesystem novel - try to get status from database
                        novel_status = "unknown"
                        if db_service:
                            try:
                                db_novel = db_service.get_novel_by_title(novel.title)
                                if db_novel and db_novel.metadata:
                                    # Extract status from metadata
                                    if hasattr(db_novel.metadata, "status"):
                                        novel_status = db_novel.metadata.status.lower()
                                    elif hasattr(db_novel.metadata, "novel_status"):
                                        novel_status = (
                                            db_novel.metadata.novel_status.lower()
                                        )
                            except Exception:
                                pass  # Continue with unknown status

                    # Apply status filter if specified
                    if status_filter and novel_status != status_filter.lower():
                        stats["skipped"] += 1
                        progress.advance(task)
                        continue

                    # Create output filename with status suffix
                    epub_file = novel.epub_file
                    original_name = epub_file.stem
                    extension = epub_file.suffix

                    # Clean status for filename (replace spaces, special chars)
                    clean_status = novel_status.replace(" ", "_").replace("-", "_")
                    clean_status = "".join(
                        c for c in clean_status if c.isalnum() or c == "_"
                    )

                    new_filename = f"{original_name}_{clean_status}{extension}"
                    output_file = output / new_filename

                    # Check if file already exists
                    if output_file.exists() and not overwrite:
                        console.print(
                            f"[yellow]⏭️ Skipping {new_filename} (already exists)[/yellow]"
                        )
                        stats["skipped"] += 1
                        progress.advance(task)
                        continue

                    if dry_run:
                        console.print(
                            f"[blue]Would copy: {epub_file.name} → {new_filename}[/blue]"
                        )
                        stats["copied"] += 1
                    else:
                        # Copy the file
                        shutil.copy2(epub_file, output_file)
                        console.print(
                            f"[green]✅ Copied: {epub_file.name} → {new_filename}[/green]"
                        )
                        stats["copied"] += 1

                except Exception as e:
                    console.print(f"[red]❌ Error processing {novel.title}: {e}[/red]")
                    stats["errors"] += 1

                progress.advance(task)

        # Close database connection
        if db_service:
            db_service.close()

        # Display results
        console.print(f"\n[green]✅ Copy operation completed![/green]")
        if dry_run:
            console.print(f"[blue]📋 Would copy: {stats['copied']} EPUB files[/blue]")
        else:
            console.print(f"[green]📚 Copied: {stats['copied']} EPUB files[/green]")
        console.print(f"[yellow]⏭️ Skipped: {stats['skipped']} files[/yellow]")
        if stats["errors"] > 0:
            console.print(f"[red]❌ Errors: {stats['errors']} files[/red]")

        if not dry_run and stats["copied"] > 0:
            console.print(
                f"\n[bold green]📁 All EPUBs copied to: {output}[/bold green]"
            )
            console.print(
                "[cyan]💡 Files are renamed with status suffixes for easy identification[/cyan]"
            )

    except Exception as e:
        console.print(f"[red]Error copying EPUBs: {e}[/red]")
        sys.exit(1)


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
