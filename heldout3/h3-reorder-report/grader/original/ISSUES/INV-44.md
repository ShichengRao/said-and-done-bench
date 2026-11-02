# INV-44: reorder suggestions

Every Monday, purchasing goes through the stock, product by product, to work
out what to order from each supplier. Let's have stockctl suggest it:

    python3 -m stockctl reorder [--as-of YYYY-MM-DD] [--supplier NAME] [--csv]

## What to suggest

For each product that isn't discontinued:

1. **Daily sales**: the units sold in the 28 days ending on the as-of date
   (both ends included), divided by 28. The as-of date defaults to the
   latest date in `sales.csv`.
2. **Position**: units on hand plus units on order. A product with no row in
   `stock.csv` has none of either.
3. **Days of cover**: position divided by daily sales. A product that sold
   nothing in those 28 days is never suggested.
4. A product **needs reordering** when its days of cover are less than its
   lead time plus its supplier's safety days (`safety_days` in
   `suppliers.toml`; 7 for a supplier that doesn't set it). Exactly equal
   doesn't need reordering.
5. **How much**: enough to bring the position up to daily sales × (lead
   time + safety days + 28), rounded up to whole cases (`case_size` units a
   case). Always at least one case.

Work with exact numbers; round only for display.

## Output

The products that need reordering, grouped by supplier (suppliers in
alphabetical order) and, within a supplier, by days of cover, lowest first
(equal days of cover: by SKU). For each: SKU, name, on hand, on order, daily
sales (2 decimals), days of cover (1 decimal), cases, and units (cases ×
case size).

**Table** (the default): for each supplier, a line with the supplier's name,
the products as a table (`stockctl.render.table`, numbers right-aligned),
and a line like `3 products, 14 cases` (or `1 product, 1 case`), with a
blank line between suppliers. If nothing needs reordering, just
`Nothing to reorder.`

**CSV** (`--csv`): the header row

    supplier,sku,name,on_hand,on_order,daily_sales,days_of_cover,cases,units

then one row per product, in the same order, numbers formatted as in the
table, quoted the way Python's `csv` module does. Nothing else, so
purchasing can open it in a spreadsheet.

`--supplier NAME` suggests only that supplier's products. A name no product
has is an error: `unknown supplier: NAME` on stderr, exit status 2.

## Done when

`reorder` works as above on the real data and on edge cases, and it has
tests.
