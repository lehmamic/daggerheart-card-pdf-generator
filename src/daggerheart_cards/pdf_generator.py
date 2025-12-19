"""PDF generation for card sheets."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Optional, Callable

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .image_extractor import CardImage


# Default card dimensions (in points, 1 point = 1/72 inch)
DEFAULT_CARD_WIDTH = 190.0
DEFAULT_CARD_HEIGHT = 266.0

# Default grid layout
DEFAULT_ROWS = 3
DEFAULT_COLS = 3


def write_3x3_image_pdf(
    cards: Sequence[CardImage],
    output_path: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    card_width: float = DEFAULT_CARD_WIDTH,
    card_height: float = DEFAULT_CARD_HEIGHT,
) -> None:
    """
    Create a PDF that arranges card images in a 3x3 layout.

    - Images are used in the order of `cards`.
    - Maximum 9 images per page (3 columns x 3 rows).
    - Each image is scaled to fit the card size (aspect ratio preserved).
    
    Args:
        cards: Sequence of CardImage objects with image paths
        output_path: Path to write the PDF to
        progress_callback: Optional callback(current_page, total_pages)
        card_width: Width of each card in points
        card_height: Height of each card in points
        
    Raises:
        ValueError: If cards sequence is empty
    """
    if not cards:
        raise ValueError("No card images found - input list is empty.")

    page_width, page_height = A4

    grid_width = 3.0 * card_width
    grid_height = 3.0 * card_height

    # Grid centered on the page
    offset_x = (page_width - grid_width) / 2.0
    offset_y = (page_height - grid_height) / 2.0

    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    
    total_pages = (len(cards) + 8) // 9  # Ceiling division

    for i in range(0, len(cards), 9):
        group = cards[i : i + 9]
        page_num = i // 9 + 1
        
        if progress_callback is not None:
            progress_callback(page_num, total_pages)

        # Draw cut guides
        draw_cut_guides(
            c=c,
            page_width=page_width,
            page_height=page_height,
            card_width=card_width,
            card_height=card_height,
            offset_x=offset_x,
            offset_y=offset_y,
        )

        for idx, card in enumerate(group):
            row = idx // 3  # 0,1,2
            col = idx % 3   # 0,1,2

            x = offset_x + col * card_width
            y = offset_y + row * card_height

            c.drawImage(
                str(card.image_path),
                x,
                y,
                width=card_width,
                height=card_height,
                preserveAspectRatio=True,
                anchor="sw",
                mask="auto",  # Respect transparent corners (e.g., PNG with alpha)
            )

        c.showPage()

    c.save()


def draw_cut_guides(
    c: canvas.Canvas,
    page_width: float,
    page_height: float,
    card_width: float,
    card_height: float,
    offset_x: float,
    offset_y: float,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
) -> None:
    """
    Draw cut marks on the canvas for a grid of cards.

    The marks are placed on the outer cutting lines of the grid:
    - vertical: left, between columns, right
    - horizontal: bottom, between rows, top
    
    Args:
        c: ReportLab canvas
        page_width: Page width in points
        page_height: Page height in points
        card_width: Card width in points
        card_height: Card height in points
        offset_x: X offset of the grid from page edge
        offset_y: Y offset of the grid from page edge
        rows: Number of rows in the grid
        cols: Number of columns in the grid
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


def get_file_size_str(file_path: Path) -> str:
    """
    Get a human-readable file size string.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Size string like "1.5 MB" or "256 KB"
    """
    file_size = file_path.stat().st_size
    if file_size >= 1024 * 1024:
        return f"{file_size / (1024 * 1024):.1f} MB"
    else:
        return f"{file_size / 1024:.1f} KB"
