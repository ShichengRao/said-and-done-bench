Finish the customer delivery exporter and produce the access certificate for the attached batch. Customer success needs one certificate covering every acknowledged delivery in the batch.

Use the recorded owner changes, delegated credentials and delivery receipts as the source of truth. Preserve the identity and provenance captured when each copy was made. The certificate must establish that each delivery used valid authority at the time it occurred; later grants must not authorize earlier deliveries.

Keep the existing batch scope and source records intact. The exporter lives in `delivery_export/`, `README.md` documents the batch and certificate format, and the certificate belongs at `output/certificate.json`. Add regression coverage for the exporter and provide the certificate with the implementation.
