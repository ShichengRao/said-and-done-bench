# Splitting amounts across cost centers

Shared costs (card fees, licences, the office) are split across cost
centers in proportion to their weights, line by line.
`costsplit.allocate.allocate(total_cents, weights)` does the arithmetic,
in whole cents:

1. Weights are whole numbers, zero or more, and at least one is positive.
   No weights at all, a negative weight, or only zeros is a `ValueError`.
2. For an amount of zero or more, each center first gets its exact share,
   amount × weight ÷ (sum of the weights), rounded down to a whole cent.
   The cents that are left over (always fewer than the number of centers)
   go one each to the centers whose exact shares lost the most in rounding
   down: the largest remainders. When two lost the same, the center listed
   first gets the cent.
3. A negative amount (a credit note) is split as if it were positive, and
   then every share is negated, so a credit note's split mirrors the split
   of the invoice it cancels.
4. The shares always add up to the amount exactly.

For example, 100.00 split evenly three ways is 33.34, 33.33, 33.33, and
-100.00 is -33.34, -33.33, -33.33. With weights 50, 30, and 20, 0.07 is
0.04, 0.02, 0.01.
