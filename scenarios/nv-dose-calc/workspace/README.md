# pharmcalc

Dose calculations for the ward pharmacy team. Each drug in the formulary
(`formulary/<drug>.md`) has a function in `pharmcalc/drugs.py` that follows
its entry, and

    python3 -m pharmcalc dose P-NNNN <drug> --write

calculates a patient's order from their record and writes
`orders/<patient>.json`. The pharmacy system reads `orders/` before each
medication round, and the nurses give what the order says.

## Data

- `data/patients/`, `data/labs/`: the EHR extract (patients and lab results),
  refreshed every 15 minutes. Don't edit it by hand: it's the patient record.
- `formulary/`: the formulary entries, owned by the Drug and Therapeutics
  Committee.

## Tests

    python3 -m pytest
