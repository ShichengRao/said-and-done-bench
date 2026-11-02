# Security advisories affecting this project

## QC-2026-03: quillcsv evaluates formula cells

- **Affected:** quillcsv before 2.0.0
- **Fixed in:** quillcsv 2.0.0
- **Severity:** high

quillcsv 1.x evaluates any cell that starts with `=` as an expression while reading a file, so a crafted CSV can run code in the reading process. quillcsv 2.0.0 reads formula cells as plain text.

**Action:** upgrade to quillcsv 2.0.0 or newer.
