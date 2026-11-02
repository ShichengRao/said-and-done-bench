# LED-12: import bank statements

Typing every transaction in by hand doesn't scale. Add:

    python3 -m ledgerly import FILE --account NAME

It reads a CSV statement exported from one of our two banks, turns each row
into a transaction on account NAME, categorizes it with the rules
(`ledgerly/rules.py`), adds the ones the ledger doesn't have yet, and prints
one line:

    imported 8, skipped 2 already in the ledger

`samples/` has a statement from each bank.

## The two formats

Tell them apart by the header row (the file's first line).

**Nordbank**: fields separated by `;`, UTF-8 with a byte-order mark, header
`Buchungstag;Valuta;Verwendungszweck;Betrag;Währung`.

- date: `Buchungstag`, as `DD.MM.YYYY`.
- description: `Verwendungszweck`.
- amount: `Betrag`, German style: `.` groups thousands, `,` is the decimal
  point, a leading `-` is money out (`-1.234,56`).
- `Währung` must be `EUR`; a row in another currency is an error.

**Westpay**: fields separated by `,` (quoted when they contain one), header
`Date,Description,Debit,Credit,Balance`.

- date: `Date`, as `YYYY-MM-DD`.
- description: `Description`.
- amount: `Credit` minus `Debit`. Each row fills in exactly one of the two
  (the other is empty); a row with both or neither is an error. Amounts look
  like `1234.56`.
- `Balance` isn't used.

In both formats, a description has leading and trailing whitespace removed
and every run of whitespace inside it replaced by one space.

A file whose header is neither: print `unrecognized statement format: FILE`
on stderr, exit with status 2, and import nothing.

## Amounts

Exact (`Decimal`), two decimal places; money in is positive, money out
negative, as everywhere in the ledger.

## Already in the ledger

Banks' exports overlap, so some rows will already be in the ledger (typed in
by hand, or imported from an earlier export). A row is the same transaction
as one in the ledger when the account, date, amount, and description (tidied
as above) are all equal. Two equal rows in one file are two transactions (two coffees on
the same day), so count them: if the file has n rows equal to each other and
the ledger already has k transactions equal to them, import n − k of them
(none if k ≥ n) and skip the rest.

## Errors

If any row can't be read (a bad date or amount, a Nordbank row not in EUR,
a Westpay row with both or neither of Debit and Credit), print
`FILE: line N: <what's wrong>` on stderr for the first such row (the header
is line 1), exit with status 1, and import nothing at all.

## Order

New transactions go at the end of the ledger, in the order of the rows they
came from.

## Done when

`import` works as above, on the samples and on edge cases, and it has tests.
