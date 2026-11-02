Finish the period-close exporter and produce the September merchant close from the attached processor records, signed control totals, and posted ERP ledger.

The support team says redeliveries sometimes change the export and the current batch fails validation. Fix the replay behavior, keep the posted ledger intact, and generate `output/close.json` through the existing close command. The package needs the merchant totals and supporting capture lines described in the client documentation.

Add regression coverage for processor revisions and replay. Keep the production ledger and the supplied records unchanged.
