# fx

Exchange rates for the invoicing service. `fx.RateBook(directory)` reads the
daily rate files the rates job writes (`YYYY-MM-DD.json`, units per euro)
and converts amounts between currencies at a given day's rates.

Tests: `python3 -m pytest` (they use the rate files in `tests/rates/`).
