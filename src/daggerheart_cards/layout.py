from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Sequence
import zipfile

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


@dataclass
class CardPage:
    """Repräsentiert eine einzelne Karten-Seite aus einem PDF innerhalb eines ZIP-Archivs."""

    zip_name: str
    pdf_name: str
    page: object  # tatsächlich pypdf._page.PageObject, aber wir typisieren locker


@dataclass
class CardImage:
    """Repräsentiert ein extrahiertes Kartenbild."""

    zip_name: str
    pdf_name: str
    image_path: Path


def find_assets_dir(start: Path | None = None) -> Path:
    """
    Versuche den `assets`-Ordner relativ zum Projekt zu finden.

    Standard: <projektwurzel>/src/assets
    """
    base = (start or Path(__file__)).resolve()
    # Paketstruktur: .../src/daggerheart_cards/layout.py -> gehe 2 Ebenen hoch
    project_root = base.parents[2]
    assets_dir = project_root / "src" / "assets"
    if not assets_dir.is_dir():
        raise FileNotFoundError(f"assets-Verzeichnis nicht gefunden: {assets_dir}")
    return assets_dir


def find_temp_dir(start: Path | None = None) -> Path:
    """
    Finde (oder erzeuge) einen `.temp`-Ordner im Projektwurzelverzeichnis.
    Hier können extrahierte Bilder zur Kontrolle gespeichert werden.
    """
    base = (start or Path(__file__)).resolve()
    project_root = base.parents[2]
    temp_dir = project_root / ".temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def collect_card_images(assets_dir: Path | None = None) -> List[CardImage]:
    """
    Lies alle ZIP-Dateien im assets-Ordner und sammle die PDF-Seiten.

    - Jede ZIP-Datei wird als Gruppe behandelt.
    - Alle Seiten der PDFs eines ZIPs kommen nacheinander.
    - ZIPs werden alphabetisch sortiert verarbeitet.
    """
    if assets_dir is None:
        assets_dir = find_assets_dir()

    card_images: List[CardImage] = []

    for zip_path in sorted(assets_dir.glob("*.zip")):
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Nur PDF-Dateien im Archiv betrachten
            pdf_names = sorted(
                name
                for name in zf.namelist()
                if name.lower().endswith(".pdf") and not name.endswith("/")
            )
            for pdf_index, pdf_name in enumerate(pdf_names):
                data = zf.read(pdf_name)
                reader = PdfReader(BytesIO(data))
                for page_index, page in enumerate(reader.pages):
                    try:
                        temp_dir = find_temp_dir()
                        img_path = _extract_main_image_to_temp(
                            page=page,
                            temp_dir=temp_dir,
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

    return card_images


def write_3x3_image_pdf(
    cards: Sequence[CardImage],
    output_path: Path,
) -> None:
    """
    Erzeuge ein PDF, das Kartenbilder im 3x3-Layout anordnet.

    - Bilder werden in der Reihenfolge von `cards` verwendet.
    - Pro Seite maximal 9 Bilder (3 Spalten x 3 Zeilen).
    - Jedes Bild wird auf 190x266 Punkte skaliert (Seitenverhältnis bleibt erhalten).
    """
    if not cards:
        raise ValueError("Keine Kartenbilder gefunden – Eingabeliste ist leer.")

    page_width, page_height = A4

    # Zielgröße einer Karte (wie gewünscht)
    card_w = 190.0
    card_h = 266.0

    grid_width = 3.0 * card_w
    grid_height = 3.0 * card_h

    # Raster zentriert auf der Seite
    offset_x = (page_width - grid_width) / 2.0
    offset_y = (page_height - grid_height) / 2.0

    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))

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
                mask="auto",  # Transparente Ecken respektieren (z.B. PNG mit Alpha)
            )

        c.showPage()

    c.save()


def build_cards_pdf(
    output_path: Path,
    assets_dir: Path | None = None,
) -> None:
    """
    High-Level Helfer:
    - sammelt alle Karten aus ZIPs im assets-Ordner
    - schreibt ein einziges PDF mit 3x3-Layout.
    """
    cards = collect_card_images(assets_dir=assets_dir)
    if not cards:
        raise RuntimeError("Es wurden keine Kartenbilder in den ZIP-Dateien gefunden.")

    write_3x3_image_pdf(cards, output_path=output_path)


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
    Zeichne Schnittmarken direkt auf das Canvas.

    Die Marken sitzen auf den äußeren Schneidelinien des 3x3-Rasters:
    - vertikal: links, zwischen Spalte 1/2, zwischen Spalte 2/3, rechts
    - horizontal: unten, zwischen Zeile 1/2, zwischen Zeile 2/3, oben
    """
    # Maße in Punkten (1 Punkt = 1/72 Zoll)
    mark_length = 12  # Länge der Schnittmarken

    # Schnittmarken (schwarz, dünn)
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0, 0, 0)

    # X-Positionen der vertikalen Schneidelinien
    x_positions = [offset_x + i * card_width for i in range(cols + 1)]
    # Y-Positionen der horizontalen Schneidelinien
    y_positions = [offset_y + i * card_height for i in range(rows + 1)]

    # Vertikale Marken oben und unten
    for x in x_positions:
        # oben
        c.line(x, page_height, x, page_height - mark_length)
        # unten
        c.line(x, 0, x, mark_length)

    # Horizontale Marken links und rechts
    for y in y_positions:
        # links
        c.line(0, y, mark_length, y)
        # rechts
        c.line(page_width, y, page_width - mark_length, y)


def _crop_to_content(page: object) -> None:
    """
    Beschneide eine Seite heuristisch auf den mittleren Bereich, um den weißen Rand
    um die Karte zu entfernen.

    Die Faktoren sind so gewählt, dass ungefähr die zentrierte Karte übrig bleibt.
    Falls nötig, können wir sie später noch feinjustieren.
    """
    mb = page.mediabox
    width = float(mb.width)
    height = float(mb.height)

    # Prozentsatz vom Rand, der weggeschnitten wird (heuristisch)
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


def _extract_main_image_to_temp(
    page: object,
    temp_dir: Path,
    zip_name: str,
    pdf_stem: str,
    page_index: int,
) -> Path | None:
    """
    Versuche, das größte eingebettete Bild einer Seite als Datei in `temp_dir`
    abzulegen. Dies dient rein zu Debug-/Kontrollzwecken.
    """
    # pypdf stellt über `images` eingebettete Bilder bereit (falls vorhanden).
    images = getattr(page, "images", None)
    if not images:
        return None

    # images kann ein Iterator sein – in eine Liste umwandeln.
    imgs = list(images)
    if not imgs:
        return None

    # Größtes Bild wählen (nach Auflösung, Fallback: Datengröße)
    def img_score(img: object) -> int:
        width = getattr(img, "width", 0) or 0
        height = getattr(img, "height", 0) or 0
        data = getattr(img, "data", b"")
        return width * height or len(data)

    main_img = max(imgs, key=img_score)
    data: bytes = getattr(main_img, "data", b"")
    if not data:
        return None

    # Wir speichern grundsätzlich mit .png-Endung, damit Transparenz korrekt
    # gehandhabt werden kann (ReportLab unterstützt PNG mit Alpha).
    filename = f"{zip_name}_{pdf_stem}_p{page_index}.png"
    out_path = temp_dir / filename
    out_path.write_bytes(data)
    return out_path

