"""
High-level API for Daggerheart Cards.

This module orchestrates the ZIP reading, image extraction, and PDF generation
modules to provide a simple interface for building card sheets.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

from .zip_reader import (
    find_assets_dir,
    find_temp_dir,
    find_images_dir,
    list_zip_files,
    list_pdf_files,
    list_image_files,
    list_pdfs_in_zip,
    list_images_in_zip,
    count_all_sources,
    read_pdf_from_zip,
    read_image_from_zip,
    save_image_from_zip,
    copy_image_to_temp,
)
from .image_extractor import (
    CardImage,
    FailedPdf,
    extract_images,
)
from .pdf_generator import (
    write_3x3_image_pdf,
    get_file_size_str,
)


# Re-export for backward compatibility
__all__ = [
    # Data classes
    "CardImage",
    "FailedPdf",
    # Path helpers
    "find_assets_dir",
    "find_temp_dir",
    "find_images_dir",
    # Core functions
    "collect_card_images",
    "build_cards_pdf",
    "write_3x3_image_pdf",
    # State
    "failed_pdfs",
]

# Rich console instance for beautiful output
console = Console()

# Track failed PDFs for reporting
failed_pdfs: List[FailedPdf] = []


def collect_card_images(
    assets_dir: Path | None = None,
    progress: Optional[Progress] = None,
    use_fitz_fallback: bool = True,
) -> List[CardImage]:
    """
    Collect card images from all sources in the assets folder.
    
    Supports:
    - PDFs inside ZIP files
    - Images inside ZIP files
    - PDFs directly in the assets folder
    - Images directly in the assets folder

    - Each source is treated as a group.
    - All pages of PDFs come sequentially.
    - Sources are processed in alphabetical order.
    
    Args:
        assets_dir: Path to assets directory
        progress: Rich Progress instance for progress display
        use_fitz_fallback: If True, use PyMuPDF as fallback for problematic PDFs
        
    Returns:
        List of CardImage objects with extracted image paths
    """
    global failed_pdfs
    failed_pdfs = []  # Reset for each run
    
    if assets_dir is None:
        assets_dir = find_assets_dir()

    card_images: List[CardImage] = []
    images_dir = find_images_dir()
    
    # Count total sources for progress
    total_sources = count_all_sources(assets_dir)
    
    task_id = None
    if progress is not None:
        task_id = progress.add_task("[cyan]Extracting cards...", total=total_sources)

    # 1. Process ZIP files (PDFs and images)
    for zip_path in list_zip_files(assets_dir):
        # Process PDFs in ZIP
        for pdf_name in list_pdfs_in_zip(zip_path):
            if progress is not None and task_id is not None:
                progress.update(
                    task_id, 
                    advance=1, 
                    description=f"[cyan]Processing [bold]{Path(pdf_name).stem}[/bold]..."
                )
            
            data = read_pdf_from_zip(zip_path, pdf_name)
            
            # Extract images with fallback support
            paths, failure = extract_images(
                data=data,
                output_dir=images_dir,
                zip_name=zip_path.stem,
                pdf_stem=Path(pdf_name).stem,
                use_fitz_fallback=use_fitz_fallback,
            )
            
            # Add extracted images to results
            for img_path in paths:
                card_images.append(
                    CardImage(
                        zip_name=zip_path.name,
                        pdf_name=pdf_name,
                        image_path=img_path,
                    )
                )
            
            # Track failures
            if failure is not None:
                failure.zip_name = zip_path.name
                failure.pdf_name = pdf_name
                failed_pdfs.append(failure)
                
                if not failure.used_fallback:
                    console.print(
                        f"[yellow]⚠[/yellow] Skipping [bold]{pdf_name}[/bold] in {zip_path.name}: "
                        f"PDF could not be read"
                    )
        
        # Process images in ZIP
        for image_name in list_images_in_zip(zip_path):
            if progress is not None and task_id is not None:
                progress.update(
                    task_id, 
                    advance=1, 
                    description=f"[cyan]Copying [bold]{Path(image_name).stem}[/bold]..."
                )
            
            data = read_image_from_zip(zip_path, image_name)
            img_path = save_image_from_zip(
                data=data,
                output_dir=images_dir,
                zip_name=zip_path.stem,
                image_name=Path(image_name).name,
            )
            card_images.append(
                CardImage(
                    zip_name=zip_path.name,
                    pdf_name=image_name,
                    image_path=img_path,
                )
            )
    
    # 2. Process PDFs directly in assets folder
    for pdf_path in list_pdf_files(assets_dir):
        if progress is not None and task_id is not None:
            progress.update(
                task_id, 
                advance=1, 
                description=f"[cyan]Processing [bold]{pdf_path.stem}[/bold]..."
            )
        
        data = pdf_path.read_bytes()
        
        # Extract images with fallback support
        paths, failure = extract_images(
            data=data,
            output_dir=images_dir,
            zip_name="direct",
            pdf_stem=pdf_path.stem,
            use_fitz_fallback=use_fitz_fallback,
        )
        
        # Add extracted images to results
        for img_path in paths:
            card_images.append(
                CardImage(
                    zip_name="(direct)",
                    pdf_name=pdf_path.name,
                    image_path=img_path,
                )
            )
        
        # Track failures
        if failure is not None:
            failure.zip_name = "(direct)"
            failure.pdf_name = pdf_path.name
            failed_pdfs.append(failure)
            
            if not failure.used_fallback:
                console.print(
                    f"[yellow]⚠[/yellow] Skipping [bold]{pdf_path.name}[/bold]: "
                    f"PDF could not be read"
                )
    
    # 3. Process images directly in assets folder
    for image_path in list_image_files(assets_dir):
        if progress is not None and task_id is not None:
            progress.update(
                task_id, 
                advance=1, 
                description=f"[cyan]Copying [bold]{image_path.stem}[/bold]..."
            )
        
        img_path = copy_image_to_temp(
            image_path=image_path,
            output_dir=images_dir,
            source_name="direct",
        )
        card_images.append(
            CardImage(
                zip_name="(direct)",
                pdf_name=image_path.name,
                image_path=img_path,
            )
        )

    return card_images


def print_failed_pdfs_report() -> None:
    """Print a detailed report of failed PDF processing."""
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
        for f in fallback_used[:20]:  # Limit to first 20
            error_msg = f.error[:60] + "..." if len(f.error) > 60 else f.error
            fallback_table.add_row(f.zip_name, f.pdf_name, error_msg)
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
            error_msg = f.error[:60] + "..." if len(f.error) > 60 else f.error
            failed_table.add_row(f.zip_name, f.pdf_name, error_msg)
        console.print(failed_table)


def build_cards_pdf(
    output_path: Path,
    assets_dir: Path | None = None,
    use_fitz_fallback: bool = True,
) -> None:
    """
    High-level helper to build a printable card sheet PDF.
    
    - Collects all cards from ZIPs in the assets folder
    - Sorts them alphabetically
    - Writes a single PDF with 3x3 layout
    
    Args:
        output_path: Path to the output PDF file
        assets_dir: Path to assets directory
        use_fitz_fallback: If True, use PyMuPDF as fallback for problematic PDFs
    """
    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    console.print()
    console.print(Panel.fit(
        "[bold magenta]📋 Daggerheart Cards[/bold magenta]\n"
        "[dim]Creating printable card sheets[/dim]",
        border_style="magenta",
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
        if not cards:
            console.print("[red]✘[/red] No card images found in the assets folder.")
            raise RuntimeError("No card images found in the assets folder.")
        
        # Sort cards alphabetically by zip name, then by pdf name
        cards = sorted(cards, key=lambda c: (c.zip_name.lower(), c.pdf_name.lower()))
        
        # Create progress task for PDF writing
        total_pages = (len(cards) + 8) // 9
        pdf_task = progress.add_task("[green]Writing PDF pages...", total=total_pages)
        
        def update_progress(current: int, total: int) -> None:
            progress.update(pdf_task, completed=current, 
                          description=f"[green]Writing page [bold]{current}/{total}[/bold]...")
        
        write_3x3_image_pdf(cards, output_path=output_path, progress_callback=update_progress)
    
    # Print summary
    console.print()
    
    table = Table(box=box.ROUNDED, border_style="green")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("🃏 Cards extracted", f"[bold]{len(cards)}[/bold]")
    table.add_row("📄 Pages created", f"[bold]{(len(cards) + 8) // 9}[/bold]")
    table.add_row("💾 Output file", f"[bold]{output_path}[/bold]")
    table.add_row("📊 File size", f"[bold]{get_file_size_str(output_path)}[/bold]")
    
    console.print(table)
    
    # Show failed PDFs report
    print_failed_pdfs_report()
    
    console.print()
    console.print("[green]✔[/green] [bold green]Done![/bold green] Your card sheets are ready to print.")
    console.print()
