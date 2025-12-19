"""CLI entry point for daggerheart_cards."""
from __future__ import annotations

import argparse
from pathlib import Path

from daggerheart_cards.layout import build_cards_pdf, find_assets_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Daggerheart Cards – Generate printable card PDF with 3x3 layout"
    )

    parser.add_argument(
        "--assets-dir",
        type=str,
        default=None,
        help="Path to assets directory (default: <project_root>/src/assets).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="build/daggerheart-cards.pdf",
        help="Path to output file (default: build/daggerheart-cards.pdf).",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Disable PyMuPDF fallback (use only pypdf, useful for testing).",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    assets_dir = (
        Path(args.assets_dir).resolve()
        if args.assets_dir is not None
        else find_assets_dir()
    )
    output_path = Path(args.output).resolve()
    build_cards_pdf(
        output_path=output_path, 
        assets_dir=assets_dir,
        use_fitz_fallback=not args.no_fallback,
    )


if __name__ == "__main__":
    main()


