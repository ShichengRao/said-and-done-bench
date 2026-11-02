# costsplit

Splits shared invoices across cost centers for the monthly finance close.

    python3 -m costsplit INVOICE.csv CENTERS.csv

prints each center's share of each invoice line and its total. `examples/`
has a few inputs. `docs/allocation.md` says how amounts are split.

Tests: `python3 -m pytest`.
