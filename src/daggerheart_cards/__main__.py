"""CLI entry point for daggerheart_cards."""
from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

from daggerheart_cards.layout import (
    build_cards_pdf, 
    collect_card_images, 
    find_assets_dir, 
    find_images_dir,
    failed_pdfs,
)

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Daggerheart Cards – Generate printable card PDF with 3x3 layout"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Extract command - only extract images
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract card images from PDFs (no PDF generation)"
    )
    extract_parser.add_argument(
        "--assets-dir",
        type=str,
        default=None,
        help="Path to assets directory (default: <project_root>/src/assets).",
    )
    extract_parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable PyMuPDF fallback (use only pypdf, useful for testing).",
    )
    
    # Build command - extract images and generate PDF
    build_cmd = subparsers.add_parser(
        "build",
        help="Extract card images and generate printable PDF"
    )
    build_cmd.add_argument(
        "--assets-dir",
        type=str,
        default=None,
        help="Path to assets directory (default: <project_root>/src/assets).",
    )
    build_cmd.add_argument(
        "--output",
        type=str,
        default="build/daggerheart-cards.pdf",
        help="Path to output file (default: build/daggerheart-cards.pdf).",
    )
    build_cmd.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable PyMuPDF fallback (use only pypdf, useful for testing).",
    )

    return parser


def print_failed_pdfs_report() -> None:
    """Print report of failed PDFs."""
    if not failed_pdfs:
        return
        
    console.print()
    
    fallback_used = [f for f in failed_pdfs if f.used_fallback]
    completely_failed = [f for f in failed_pdfs if not f.used_fallback]
    
    if fallback_used:
        console.print(f"[yellow]⚠ {len(fallback_used)} PDFs required PyMuPDF fallback (pypdf failed):[/yellow]")
        fallback_table = Table(box=box.SIMPLE, border_style="yellow", show_header=True)
        fallback_table.add_column("ZIP", style="dim")
        fallback_table.add_column("PDF", style="white")
        fallback_table.add_column("pypdf Error", style="yellow")
        for f in fallback_used[:20]:
            fallback_table.add_row(f.zip_name, f.pdf_name, f.error[:60] + "..." if len(f.error) > 60 else f.error)
        if len(fallback_used) > 20:
            fallback_table.add_row("...", f"[dim]and {len(fallback_used) - 20} more[/dim]", "")
        console.print(fallback_table)
    
    if completely_failed:
        console.print()
        console.print(f"[red]✘ {len(completely_failed)} PDFs could not be processed at all:[/red]")
        failed_table = Table(box=box.SIMPLE, border_style="red", show_header=True)
        failed_table.add_column("ZIP", style="dim")
        failed_table.add_column("PDF", style="white")
        failed_table.add_column("Error", style="red")
        for f in completely_failed:
            failed_table.add_row(f.zip_name, f.pdf_name, f.error[:60] + "..." if len(f.error) > 60 else f.error)
        console.print(failed_table)


def run_extract(assets_dir: Path, use_fitz_fallback: bool) -> None:
    """Run the extract command."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🖼️  Daggerheart Cards - Extract Images[/bold cyan]\n"
        "[dim]Extracting card images from PDFs[/dim]",
        border_style="cyan",
    ))
    console.print()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        cards = collect_card_images(
            assets_dir=assets_dir, 
            progress=progress,
            use_fitz_fallback=use_fitz_fallback,
        )
    
    # Print summary
    console.print()
    
    table = Table(box=box.ROUNDED, border_style="cyan")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("🃏 Cards extracted", f"[bold]{len(cards)}[/bold]")
    table.add_row("📁 Output folder", f"[bold]{find_images_dir()}[/bold]")
    
    console.print(table)
    print_failed_pdfs_report()
    
    console.print()
    console.print("[green]✔[/green] [bold green]Done![/bold green] Images extracted successfully.")
    console.print()


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    
    # Default to 'build' if no command specified
    if args.command is None:
        args.command = "build"
        # Re-parse with default values for build command
        args = parser.parse_args(["build"] + (argv if argv else []))

    assets_dir = (
        Path(args.assets_dir).resolve()
        if args.assets_dir is not None
        else find_assets_dir()
    )
    
    if args.command == "extract":
        run_extract(
            assets_dir=assets_dir,
            use_fitz_fallback=not args.no_fallback,
        )
    elif args.command == "build":
        output_path = Path(args.output).resolve()
        build_cards_pdf(
            output_path=output_path, 
            assets_dir=assets_dir,
            use_fitz_fallback=not args.no_fallback,
        )


if __name__ == "__main__":
    main()


