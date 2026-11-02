Implement the customer erasure migration across the live CDC heads and shared overlays. Remove the requested customer data from every live view while keeping the evidence holds and unrelated records intact.

Use the current rewrite permissions and deletion-barrier rules. Preserve held originals, resolve inherited data correctly and choose the least-cost permitted shared rewrite plan.

Generate the migration through the existing pipeline (`python -m erasure.migrate`, writing `output/migration.json`) and add regression coverage for inherited payloads and replay. `README.md` describes the customer records and migration rules.
