"""
Package initialization for daggerheart_cards.

This package provides tools to extract card images from PDFs inside ZIP files
and generate printable 3x3 card sheet PDFs.

Modules:
    - zip_reader: ZIP file reading and PDF discovery
    - image_extractor: Image extraction from PDFs (pypdf + PyMuPDF fallback)
    - pdf_generator: PDF generation for card sheets
    - layout: High-level API orchestrating the above modules
"""

from .layout import (
    # Data classes
    CardImage,
    FailedPdf,
    # Path helpers
    find_assets_dir,
    find_temp_dir,
    find_images_dir,
    # Core functions
    collect_card_images,
    build_cards_pdf,
    write_3x3_image_pdf,
    # State
    failed_pdfs,
)

__all__ = [
    "CardImage",
    "FailedPdf",
    "find_assets_dir",
    "find_temp_dir",
    "find_images_dir",
    "collect_card_images",
    "build_cards_pdf",
    "write_3x3_image_pdf",
    "failed_pdfs",
]

