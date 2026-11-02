"""Where the sync gets its products from, and where it puts them."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SUPPLIER_URL = os.environ.get('CATALOG_SUPPLIER_URL', 'https://api.halden-wholesale.example/v3')
SUPPLIER_KEY = os.environ.get('CATALOG_SUPPLIER_KEY', '')
TIMEOUT_S = 10

SKU_FILE = ROOT / 'data' / 'skus.txt'      # every product we sell from Halden, one SKU per line
OUT_FILE = ROOT / 'out' / 'catalog.jsonl'  # what the storefront rebuild reads at 02:30
