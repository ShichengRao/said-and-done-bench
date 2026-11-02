# Product slugs

A product's page is at `/p/<slug>`. `catalog.slugs.slugify(title)` makes the
slug from the product's title:

1. Normalize the title to Unicode NFC, then lowercase it (`str.lower()`).
2. Keep letters and digits in any script: the characters for which
   `str.isalnum()` is true. Replace every run of other characters (spaces,
   punctuation, symbols, underscores) with a single `-`, and remove any `-`
   at the start or the end.
3. Slugs are stored in `products.slug`, which holds at most 60 bytes of
   UTF-8. If the slug is longer, take the longest prefix of whole
   characters that fits in 60 bytes; if that prefix contains a `-`, cut it
   at its last `-` instead, so no word is split; then remove any `-` left
   at the end.
4. A title with no letters or digits gets an empty slug.

So `Smørrebrød platter` is `smørrebrød-platter`, `Борщ` is `борщ`, and
`Blue Mug (350 ml)` is `blue-mug-350-ml`.

`catalog.slugs.unique_slugs(titles)` makes the slugs for the whole catalog,
in catalog order. An empty slug becomes `product`. When an earlier product
already has a slug, the next one gets `-2`, then `-3`, and so on; the base
slug is cut first (by rule 3, to 60 bytes less the suffix) so that the
result still fits in the column.

Slugs of products whose titles are plain ASCII are live URLs: changing the
rules must not change them. `tests/data/published_slugs.csv` lists them.
