"""ZIP file reading and PDF discovery functionality."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import List, Iterator, Tuple
import zipfile


def find_assets_dir(start: Path | None = None) -> Path:
    """
    Try to find the `assets` folder relative to the project.

    Default: <project_root>/src/assets
    """
    base = (start or Path(__file__)).resolve()
    # Package structure: .../src/daggerheart_cards/zip_reader.py -> go up 2 levels
    project_root = base.parents[1]
    assets_dir = project_root / "assets"
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


def list_zip_files(assets_dir: Path) -> List[Path]:
    """
    List all ZIP files in the assets directory, sorted alphabetically.
    
    Args:
        assets_dir: Path to the assets directory
        
    Returns:
        Sorted list of ZIP file paths
    """
    return sorted(assets_dir.glob("*.zip"))


def list_pdfs_in_zip(zip_path: Path) -> List[str]:
    """
    List all PDF files in a ZIP archive.
    
    Filters out:
    - Directory entries (paths ending with /)
    - macOS metadata files (__MACOSX/)
    
    Args:
        zip_path: Path to the ZIP file
        
    Returns:
        Sorted list of PDF file names within the ZIP
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        return sorted(
            name
            for name in zf.namelist()
            if name.lower().endswith(".pdf")
            and not name.endswith("/")
            and not name.startswith("__MACOSX/")
        )


def count_pdfs_in_zips(zip_files: List[Path]) -> int:
    """
    Count total number of PDFs across all ZIP files.
    
    Args:
        zip_files: List of ZIP file paths
        
    Returns:
        Total PDF count
    """
    total = 0
    for zip_path in zip_files:
        total += len(list_pdfs_in_zip(zip_path))
    return total


def read_pdf_from_zip(zip_path: Path, pdf_name: str) -> bytes:
    """
    Read a PDF file's contents from a ZIP archive.
    
    Args:
        zip_path: Path to the ZIP file
        pdf_name: Name of the PDF file within the ZIP
        
    Returns:
        Raw bytes of the PDF file
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        return zf.read(pdf_name)


def iterate_pdfs(assets_dir: Path) -> Iterator[Tuple[Path, str, bytes]]:
    """
    Iterate over all PDFs in all ZIP files in the assets directory.
    
    Yields tuples of (zip_path, pdf_name, pdf_data) for each PDF found.
    
    Args:
        assets_dir: Path to the assets directory
        
    Yields:
        Tuples of (zip_path, pdf_name, pdf_bytes)
    """
    for zip_path in list_zip_files(assets_dir):
        with zipfile.ZipFile(zip_path, "r") as zf:
            for pdf_name in list_pdfs_in_zip(zip_path):
                yield zip_path, pdf_name, zf.read(pdf_name)
