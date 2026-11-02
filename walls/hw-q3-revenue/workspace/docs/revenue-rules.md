# Revenue rules

How `python3 -m revenue report` counts a quarter's revenue. Agreed with the
finance team (Dana Whitfield), January 2026.

1. **Quarters** are calendar quarters in UTC: 2026Q3 runs from 2026-07-01
   00:00 UTC up to, but not including, 2026-10-01 00:00 UTC.
2. **Invoices** count in the quarter of their issue time (`issued_at`), at
   their net amount: VAT isn't revenue.
3. **Void invoices** (`status` = `void`) don't count. They're cancelled
   before they're sent; corrections after sending are credit notes.
4. **Credit notes** reduce revenue in the quarter of their own issue time,
   by their net amount, whatever quarter the invoice they credit was in.
5. **Test accounts** (customer ids starting `T-`) don't count, and neither do
   their credit notes. QA uses them to exercise the ERP in production.
6. Amounts are exact: euros and cents, never rounded along the way.
