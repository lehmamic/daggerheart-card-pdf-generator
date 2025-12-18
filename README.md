# Daggerheart Cards – Python 3 Projekt

Minimaler Projekt-Seed mit `pyproject.toml` und einfachem CLI-Einstiegspunkt.

## Schnellstart
1) Python 3.10+ installieren.  
2) Virtuelle Umgebung anlegen (empfohlen):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3) Abhängigkeiten installieren:
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```
4) CLI ausprobieren:
   ```bash
   daggerheart-cards
   ```

## Karten-PDF mit 3x3-Layout erzeugen
Im Ordner `src/assets` liegen ZIP-Dateien. Jede ZIP-Datei enthält PDF-Dateien,
deren Seiten jeweils eine einzelne Daggerheart-Karte darstellen.

Die Karten werden gruppiert nach ZIP-Datei ausgelesen und in ein einziges PDF
mit 3x3-Raster (3 Spalten x 3 Zeilen pro Seite) ohne Skalierung geschrieben.

Standardaufruf:
```bash
daggerheart-cards
```

Optionen:
- `--assets-dir` – Pfad zum Assets-Ordner  
  Standard: `<projektwurzel>/src/assets`
- `--output` – Ausgabe-PDF  
  Standard: `build/cards-3x3.pdf`

## Struktur
- `pyproject.toml` – Projekt- und Build-Metadaten (PEP 621, setuptools)
- `src/daggerheart_cards/` – Paketquellcode
  - `__main__.py` – CLI-Einstiegspunkt (`daggerheart-cards`)
  - `__init__.py` – Paketinitialisierung

## Entwickeln
- Lint/Format kannst du bei Bedarf ergänzen (z. B. Ruff, Black).
- Tests kannst du über `pytest` hinzufügen (`python -m pip install pytest`).


190x270