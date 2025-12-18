"""Einfacher CLI-Einstiegspunkt für daggerheart_cards."""
from __future__ import annotations

import argparse
from pathlib import Path

from daggerheart_cards.layout import build_cards_pdf, find_assets_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Daggerheart Cards – Karten-PDF mit 3x3-Layout erzeugen"
    )

    parser.add_argument(
        "--assets-dir",
        type=str,
        default=None,
        help="Pfad zum assets-Verzeichnis (Standard: <projektwurzel>/src/assets).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="build/cards-3x3.pdf",
        help="Pfad zur Ausgabedatei (Standard: build/cards-3x3.pdf).",
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
    build_cards_pdf(output_path=output_path, assets_dir=assets_dir)
    print(f"Karten-PDF erzeugt: {output_path}")


if __name__ == "__main__":
    main()


