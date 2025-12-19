from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Sequence, Optional, Callable
import zipfile

import fitz  # PyMuPDF - robust PDF reader
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.errors import PdfStreamError
from pypdf.generic import RectangleObject
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich import box


@dataclass
class CardPage:
    """Represents a single card page from a PDF within a ZIP archive."""

    zip_name: str
    pdf_name: str
    page: object  # actually pypdf._page.PageObject, but we type loosely


@dataclass
class CardImage:
    """Represents an extracted card image."""

    zip_name: str
    pdf_name: str
    image_path: Path


@dataclass
class FailedPdf:
    """Represents a PDF that failed to be processed."""

    zip_name: str
    pdf_name: str
    error: str
    used_fallback: bool = False


# Rich console instance for beautiful output
console = Console()

# Track failed PDFs for reporting
failed_pdfs: List[FailedPdf] = []


def find_assets_dir(start: Path | None = None) -> Path:
    """
    Try to find the `assets` folder relative to the project.

    Default: <project_root>/src/assets
    """
    base = (start or Path(__file__)).resolve()
    # Package structure: .../src/daggerheart_cards/layout.py -> go up 2 levels
    project_root = base.parents[2]
    assets_dir = project_root / "src" / "assets"
    if not assets_dir.is_dir():
        raise FileNotFoundError(f"Assets directory not found: {assets_dir}")
    return assets_dir


def find_temp_dir(start: Path | None = None) -> Path:
    """
    Find (or create) a `.temp` folder in the project root directory.
    """
    base = (start or Path(__file__)).resolve()
    project_root = base.parents[2]
    temp_dir = project_root / ".temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def find_images_dir(start: Path | None = None) -> Path:
    """
    Find (or create) the `.temp/images` folder for extracted card images.
    """
    images_dir = find_temp_dir(start) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def collect_card_images(
    assets_dir: Path | None = None,
    progress: Optional[Progress] = None,
    use_fitz_fallback: bool = True,
) -> List[CardImage]:
    """
    Read all ZIP files in the assets folder and collect the PDF pages.

    - Each ZIP file is treated as a group.
    - All pages of PDFs within a ZIP come sequentially.
    - ZIPs are processed in alphabetical order.
    
    Args:
        assets_dir: Path to assets directory
        progress: Rich Progress instance for progress display
        use_fitz_fallback: If True, use PyMuPDF as fallback for problematic PDFs
    """
    global failed_pdfs
    failed_pdfs = []  # Reset for each run
    
    if assets_dir is None:
        assets_dir = find_assets_dir()

    card_images: List[CardImage] = []
    zip_files = sorted(assets_dir.glob("*.zip"))
    
    # Count total PDFs for progress
    total_pdfs = 0
    for zip_path in zip_files:
        with zipfile.ZipFile(zip_path, "r") as zf:
            total_pdfs += len([
                name for name in zf.namelist()
                if name.lower().endswith(".pdf") 
                and not name.endswith("/")
                and not name.startswith("__MACOSX/")
            ])
    
    task_id = None
    if progress is not None:
        task_id = progress.add_task("[cyan]Extracting cards...", total=total_pdfs)

    for zip_path in zip_files:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Only consider PDF files in the archive, ignore __MACOSX metadata
            pdf_names = sorted(
                name
                for name in zf.namelist()
                if name.lower().endswith(".pdf") 
                and not name.endswith("/")
                and not name.startswith("__MACOSX/")
            )
            for pdf_index, pdf_name in enumerate(pdf_names):
                if progress is not None and task_id is not None:
                    progress.update(task_id, advance=1, description=f"[cyan]Processing [bold]{Path(pdf_name).stem}[/bold]...")
                
                data = zf.read(pdf_name)
                images_dir = find_images_dir()
                
                # Try pypdf first (for image extraction)
                pypdf_success = False
                pypdf_error = None
                if data.startswith(b'%PDF'):
                    try:
                        reader = PdfReader(BytesIO(data))
                        for page_index, page in enumerate(reader.pages):
                            try:
                                img_path = _extract_main_image_to_temp(
                                    page=page,
                                    temp_dir=images_dir,
                                    zip_name=zip_path.stem,
                                    pdf_stem=Path(pdf_name).stem,
                                    page_index=page_index,
                                )
                            except Exception:
                                img_path = None

                            if img_path is not None:
                                card_images.append(
                                    CardImage(
                                        zip_name=zip_path.name,
                                        pdf_name=pdf_name,
                                        image_path=img_path,
                                    )
                                )
                                pypdf_success = True
                    except (PdfStreamError, Exception) as e:
                        pypdf_error = f"{type(e).__name__}: {e}"
                else:
                    pypdf_error = f"Invalid PDF header: {data[:10]!r}"
                
                # Fallback: PyMuPDF (fitz) for problematic PDFs
                if not pypdf_success and use_fitz_fallback:
                    try:
                        img_paths = _extract_images_with_fitz(
                            data=data,
                            temp_dir=images_dir,
                            zip_name=zip_path.stem,
                            pdf_stem=Path(pdf_name).stem,
                        )
                        for img_path in img_paths:
                            card_images.append(
                                CardImage(
                                    zip_name=zip_path.name,
                                    pdf_name=pdf_name,
                                    image_path=img_path,
                                )
                            )
                        # Track that pypdf failed but fitz worked
                        if pypdf_error:
                            failed_pdfs.append(FailedPdf(
                                zip_name=zip_path.name,
                                pdf_name=pdf_name,
                                error=pypdf_error,
                                used_fallback=True,
                            ))
                    except Exception as e:
                        failed_pdfs.append(FailedPdf(
                            zip_name=zip_path.name,
                            pdf_name=pdf_name,
                            error=f"{type(e).__name__}: {e}",
                            used_fallback=False,
                        ))
                        console.print(
                            f"[yellow]⚠[/yellow] Skipping [bold]{pdf_name}[/bold] in {zip_path.name}: "
                            f"PDF could not be read ({type(e).__name__})"
                        )
                elif not pypdf_success:
                    # Fitz fallback disabled, track as failure
                    failed_pdfs.append(FailedPdf(
                        zip_name=zip_path.name,
                        pdf_name=pdf_name,
                        error=pypdf_error or "Unknown error",
                        used_fallback=False,
                    ))

    return card_images


def write_3x3_image_pdf(
    cards: Sequence[CardImage],
    output_path: Path,
    progress: Optional[Progress] = None,
) -> None:
    """
    Create a PDF that arranges card images in a 3x3 layout.

    - Images are used in the order of `cards`.
    - Maximum 9 images per page (3 columns x 3 rows).
    - Each image is scaled to 190x266 points (aspect ratio preserved).
    """
    if not cards:
        raise ValueError("No card images found - input list is empty.")

    page_width, page_height = A4

    # Target size of a card (as desired)
    card_w = 190.0
    card_h = 266.0

    grid_width = 3.0 * card_w
    grid_height = 3.0 * card_h

    # Grid centered on the page
    offset_x = (page_width - grid_width) / 2.0
    offset_y = (page_height - grid_height) / 2.0

    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    
    total_pages = (len(cards) + 8) // 9  # Ceiling division
    task_id = None
    if progress is not None:
        task_id = progress.add_task("[green]Writing PDF pages...", total=total_pages)

    def draw_guides() -> None:
        _draw_guides_on_canvas(
            c=c,
            page_width=page_width,
            page_height=page_height,
            card_width=card_w,
            card_height=card_h,
            offset_x=offset_x,
            offset_y=offset_y,
        )

    for i in range(0, len(cards), 9):
        group = cards[i : i + 9]
        page_num = i // 9 + 1
        
        if progress is not None and task_id is not None:
            progress.update(task_id, advance=1, description=f"[green]Writing page [bold]{page_num}/{total_pages}[/bold]...")

        draw_guides()

        for idx, card in enumerate(group):
            row = idx // 3  # 0,1,2
            col = idx % 3   # 0,1,2

            x = offset_x + col * card_w
            y = offset_y + row * card_h

            c.drawImage(
                str(card.image_path),
                x,
                y,
                width=card_w,
                height=card_h,
                preserveAspectRatio=True,
                anchor="sw",
                mask="auto",  # Respect transparent corners (e.g., PNG with alpha)
            )

        c.showPage()

    c.save()


def build_cards_pdf(
    output_path: Path,
    assets_dir: Path | None = None,
    use_fitz_fallback: bool = True,
) -> None:
    """
    High-level helper:
    - Collects all cards from ZIPs in the assets folder
    - Writes a single PDF with 3x3 layout.
    
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
            console.print("[red]✘[/red] No card images found in the ZIP files.")
            raise RuntimeError("No card images found in the ZIP files.")
        
        # Sort cards alphabetically by zip name, then by pdf name
        cards = sorted(cards, key=lambda c: (c.zip_name.lower(), c.pdf_name.lower()))
        
        write_3x3_image_pdf(cards, output_path=output_path, progress=progress)
    
    # Print summary
    console.print()
    
    table = Table(box=box.ROUNDED, border_style="green")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("🃏 Cards extracted", f"[bold]{len(cards)}[/bold]")
    table.add_row("📄 Pages created", f"[bold]{(len(cards) + 8) // 9}[/bold]")
    table.add_row("💾 Output file", f"[bold]{output_path}[/bold]")
    
    file_size = output_path.stat().st_size
    if file_size >= 1024 * 1024:
        size_str = f"{file_size / (1024 * 1024):.1f} MB"
    else:
        size_str = f"{file_size / 1024:.1f} KB"
    table.add_row("📊 File size", f"[bold]{size_str}[/bold]")
    
    console.print(table)
    
    # Show failed PDFs report
    if failed_pdfs:
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
    
    console.print()
    console.print("[green]✔[/green] [bold green]Done![/bold green] Your card sheets are ready to print.")
    console.print()


def _draw_guides_on_canvas(
    c: canvas.Canvas,
    page_width: float,
    page_height: float,
    card_width: float,
    card_height: float,
    offset_x: float,
    offset_y: float,
    rows: int = 3,
    cols: int = 3,
) -> None:
    """
    Draw cut marks directly on the canvas.

    The marks are placed on the outer cutting lines of the 3x3 grid:
    - vertical: left, between column 1/2, between column 2/3, right
    - horizontal: bottom, between row 1/2, between row 2/3, top
    """
    # Dimensions in points (1 point = 1/72 inch)
    mark_length = 12  # Length of the cut marks

    # Cut marks (black, thin)
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)

    # X positions of vertical cutting lines
    x_positions = [offset_x + i * card_width for i in range(cols + 1)]
    # Y positions of horizontal cutting lines
    y_positions = [offset_y + i * card_height for i in range(rows + 1)]

    # Vertical marks at top and bottom
    for x in x_positions:
        # top
        c.line(x, page_height, x, page_height - mark_length)
        # bottom
        c.line(x, 0, x, mark_length)

    # Horizontal marks at left and right
    for y in y_positions:
        # left
        c.line(0, y, mark_length, y)
        # right
        c.line(page_width, y, page_width - mark_length, y)


def _crop_to_content(page: object) -> None:
    """
    Heuristically crop a page to the center area to remove the white border
    around the card.

    The factors are chosen so that approximately the centered card remains.
    If needed, we can fine-tune them later.
    """
    mb = page.mediabox
    width = float(mb.width)
    height = float(mb.height)

    # Percentage of border to cut off (heuristic)
    left_frac = 0.18
    right_frac = 0.18
    bottom_frac = 0.20
    top_frac = 0.18

    left = float(mb.left) + width * left_frac
    bottom = float(mb.bottom) + height * bottom_frac
    right = float(mb.right) - width * right_frac
    top = float(mb.top) - height * top_frac

    new_box = RectangleObject((left, bottom, right, top))
    page.cropbox = new_box
    page.mediabox = new_box


def _extract_images_with_fitz(
    data: bytes,
    temp_dir: Path,
    zip_name: str,
    pdf_stem: str,
) -> List[Path]:
    """
    Extract images from a PDF using PyMuPDF (fitz).
    
    PyMuPDF is more robust than pypdf and can also read PDFs
    that pypdf rejects as corrupt.
    """
    result: List[Path] = []
    doc = fitz.open(stream=data, filetype="pdf")
    
    for page_index, page in enumerate(doc):
        # Render the page as an image (high quality)
        # matrix=fitz.Matrix(2, 2) doubles the resolution
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=True)
        
        filename = f"{zip_name}_{pdf_stem}_p{page_index}.png"
        out_path = temp_dir / filename
        pix.save(str(out_path))
        result.append(out_path)
    
    doc.close()
    return result


def _extract_main_image_to_temp(
    page: object,
    temp_dir: Path,
    zip_name: str,
    pdf_stem: str,
    page_index: int,
) -> Path | None:
    """
    Try to save the largest embedded image of a page as a file in `temp_dir`.
    This is purely for debugging/inspection purposes.
    """
    # pypdf provides embedded images via `images` (if available).
    images = getattr(page, "images", None)
    if not images:
        return None

    # images can be an iterator - convert to a list.
    imgs = list(images)
    if not imgs:
        return None

    # Choose the largest image (by resolution, fallback: data size)
    def img_score(img: object) -> int:
        width = getattr(img, "width", 0) or 0
        height = getattr(img, "height", 0) or 0
        data = getattr(img, "data", b"")
        return width * height or len(data)

    main_img = max(imgs, key=img_score)
    data: bytes = getattr(main_img, "data", b"")
    if not data:
        return None

    # We always save with .png extension so that transparency is handled
    # correctly (ReportLab supports PNG with alpha).
    filename = f"{zip_name}_{pdf_stem}_p{page_index}.png"
    out_path = temp_dir / filename
    out_path.write_bytes(data)
    return out_path

