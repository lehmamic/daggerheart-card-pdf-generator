"""Image extraction from PDF files."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import fitz  # PyMuPDF - robust PDF reader
from pypdf import PdfReader
from pypdf.errors import PdfStreamError


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


def extract_images_pypdf(
    data: bytes,
    output_dir: Path,
    zip_name: str,
    pdf_stem: str,
) -> List[Path]:
    """
    Extract images from a PDF using pypdf.
    
    Extracts the largest embedded image from each page.
    
    Args:
        data: Raw PDF bytes
        output_dir: Directory to save extracted images
        zip_name: Name of the source ZIP (for filename)
        pdf_stem: PDF filename without extension (for filename)
        
    Returns:
        List of paths to extracted image files
        
    Raises:
        PdfStreamError: If pypdf cannot read the PDF
        ValueError: If PDF header is invalid
    """
    if not data.startswith(b'%PDF'):
        raise ValueError(f"Invalid PDF header: {data[:10]!r}")
    
    result: List[Path] = []
    reader = PdfReader(BytesIO(data))
    
    for page_index, page in enumerate(reader.pages):
        img_path = _extract_main_image_from_page(
            page=page,
            output_dir=output_dir,
            zip_name=zip_name,
            pdf_stem=pdf_stem,
            page_index=page_index,
        )
        if img_path is not None:
            result.append(img_path)
    
    return result


def extract_images_fitz(
    data: bytes,
    output_dir: Path,
    zip_name: str,
    pdf_stem: str,
) -> List[Path]:
    """
    Extract images from a PDF using PyMuPDF (fitz).
    
    PyMuPDF is more robust than pypdf and can also read PDFs
    that pypdf rejects as corrupt. It renders pages as images
    at high quality.
    
    Args:
        data: Raw PDF bytes
        output_dir: Directory to save extracted images
        zip_name: Name of the source ZIP (for filename)
        pdf_stem: PDF filename without extension (for filename)
        
    Returns:
        List of paths to extracted image files
    """
    result: List[Path] = []
    doc = fitz.open(stream=data, filetype="pdf")
    
    for page_index, page in enumerate(doc):
        # Render the page as an image (high quality)
        # matrix=fitz.Matrix(2, 2) doubles the resolution
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=True)
        
        filename = f"{zip_name}_{pdf_stem}_p{page_index}.png"
        out_path = output_dir / filename
        pix.save(str(out_path))
        result.append(out_path)
    
    doc.close()
    return result


def extract_images(
    data: bytes,
    output_dir: Path,
    zip_name: str,
    pdf_stem: str,
    use_fitz_fallback: bool = True,
) -> tuple[List[Path], Optional[FailedPdf]]:
    """
    Extract images from a PDF, using pypdf with optional fitz fallback.
    
    Args:
        data: Raw PDF bytes
        output_dir: Directory to save extracted images
        zip_name: Name of the source ZIP (for filename)
        pdf_stem: PDF filename without extension (for filename)
        use_fitz_fallback: If True, use PyMuPDF as fallback when pypdf fails
        
    Returns:
        Tuple of (list of image paths, optional failure info)
        - If successful with pypdf: (paths, None)
        - If successful with fallback: (paths, FailedPdf with used_fallback=True)
        - If failed completely: ([], FailedPdf with used_fallback=False)
    """
    pypdf_error: Optional[str] = None
    
    # Try pypdf first (for image extraction)
    try:
        paths = extract_images_pypdf(data, output_dir, zip_name, pdf_stem)
        if paths:
            return paths, None
        pypdf_error = "No images found in PDF"
    except (PdfStreamError, ValueError, Exception) as e:
        pypdf_error = f"{type(e).__name__}: {e}"
    
    # Fallback: PyMuPDF (fitz) for problematic PDFs
    if use_fitz_fallback:
        try:
            paths = extract_images_fitz(data, output_dir, zip_name, pdf_stem)
            # Track that pypdf failed but fitz worked
            failure_info = FailedPdf(
                zip_name=zip_name,
                pdf_name=pdf_stem,
                error=pypdf_error or "Unknown pypdf error",
                used_fallback=True,
            )
            return paths, failure_info
        except Exception as e:
            return [], FailedPdf(
                zip_name=zip_name,
                pdf_name=pdf_stem,
                error=f"{type(e).__name__}: {e}",
                used_fallback=False,
            )
    
    # Fitz fallback disabled, return failure
    return [], FailedPdf(
        zip_name=zip_name,
        pdf_name=pdf_stem,
        error=pypdf_error or "Unknown error",
        used_fallback=False,
    )


def _extract_main_image_from_page(
    page: object,
    output_dir: Path,
    zip_name: str,
    pdf_stem: str,
    page_index: int,
) -> Path | None:
    """
    Try to save the largest embedded image of a page as a file.
    
    Args:
        page: pypdf page object
        output_dir: Directory to save the image
        zip_name: Name of the source ZIP (for filename)
        pdf_stem: PDF filename without extension (for filename)
        page_index: Page number (0-indexed)
        
    Returns:
        Path to the saved image, or None if no image found
    """
    # pypdf provides embedded images via `images` (if available)
    images = getattr(page, "images", None)
    if not images:
        return None

    # images can be an iterator - convert to a list
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

    # Always save with .png extension for transparency support
    filename = f"{zip_name}_{pdf_stem}_p{page_index}.png"
    out_path = output_dir / filename
    out_path.write_bytes(data)
    return out_path
