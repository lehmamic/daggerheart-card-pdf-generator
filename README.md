# Daggerheart Cards

A Python tool to extract card images from PDFs inside ZIP files and generate printable 3x3 card sheet PDFs for the Daggerheart tabletop RPG.

## Features

- 📦 Reads PDF files from ZIP archives
- 🖼️ Extracts card images using pypdf (with PyMuPDF fallback for problematic PDFs)
- 📄 Generates printable A4 PDF with 3x3 card layout
- ✂️ Includes cut marks for easy trimming
- 🔤 Cards are sorted alphabetically
- 📊 Beautiful console output with progress bars

## Installation

**Requirements:** Python 3.10+

```bash
# Clone the repository
git clone <repo-url>
cd daggerheart-cards

# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install the package
pip install -e .
```

## Usage

### Build Command (Default)

Extract card images from PDFs and generate a printable PDF:

```bash
# Using default settings
daggerheart-cards

# Or explicitly
daggerheart-cards build
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--assets-dir` | Path to assets directory containing ZIP files | `src/assets` |
| `--output` | Output PDF file path | `build/daggerheart-cards.pdf` |
| `--no-fallback` | Disable PyMuPDF fallback (use only pypdf) | Fallback enabled |

**Examples:**

```bash
# Custom output location
daggerheart-cards build --output my-cards.pdf

# Custom assets directory
daggerheart-cards build --assets-dir /path/to/zips

# Disable PyMuPDF fallback (for testing)
daggerheart-cards build --no-fallback
```

### Extract Command

Extract card images only (without generating PDF):

```bash
daggerheart-cards extract
```

Images are saved to `.temp/images/` in the project root.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--assets-dir` | Path to assets directory containing ZIP files | `src/assets` |
| `--no-fallback` | Disable PyMuPDF fallback (use only pypdf) | Fallback enabled |

## Project Structure

```
daggerheart-cards/
├── src/
│   ├── assets/              # Place your ZIP files here
│   └── daggerheart_cards/   # Package source code
│       ├── __init__.py
│       ├── __main__.py      # CLI entry point
│       ├── zip_reader.py    # ZIP file handling
│       ├── image_extractor.py  # PDF image extraction
│       ├── pdf_generator.py # PDF generation
│       └── layout.py        # High-level API
├── build/                   # Generated PDFs (output)
├── .temp/images/            # Extracted images (temporary)
├── pyproject.toml
└── README.md
```

## How It Works

1. **ZIP Reading**: Scans the assets directory for ZIP files
2. **PDF Discovery**: Finds all PDF files within each ZIP (ignores macOS metadata)
3. **Image Extraction**: 
   - Tries pypdf first to extract embedded images
   - Falls back to PyMuPDF (fitz) for problematic PDFs
   - PyMuPDF renders pages as high-quality images
4. **PDF Generation**: Arranges cards in a 3x3 grid on A4 pages with cut marks

## Dependencies

- **pypdf** >= 5.0.0 – Primary PDF reader for image extraction
- **PyMuPDF** >= 1.24.0 – Fallback PDF reader (more robust)
- **reportlab** >= 4.0.0 – PDF generation
- **rich** >= 13.0.0 – Beautiful console output

## License

MIT
