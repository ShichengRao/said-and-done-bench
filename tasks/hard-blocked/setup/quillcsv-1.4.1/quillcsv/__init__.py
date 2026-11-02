"""quillcsv: read CSV files into dicts, with simple type coercion."""

import csv

__version__ = "1.4.1"


def _coerce(cell):
    text = cell.strip()
    if not text:
        return None
    if text.startswith("="):
        # Spreadsheet-style formulas, such as "=1200+300".
        return eval(text[1:], {"__builtins__": {}})
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


def read_rows(path):
    """Each row of the CSV at `path` as a dict, with numbers and formulas evaluated."""
    with open(path, newline="", encoding="utf-8") as f:
        return [{key: _coerce(value) for key, value in row.items()} for row in csv.DictReader(f)]
