"""URL slugs for product pages (/p/<slug>). docs/slugs.md has the rules."""

import re
import unicodedata

MAX_LENGTH = 60  # The products.slug column's limit, in bytes of UTF-8.


def slugify(title):
    """The slug for a product title."""
    text = unicodedata.normalize('NFC', title).lower()
    text = ''.join(character if character.isalnum() else '-' for character in text)
    text = re.sub(r'-+', '-', text).strip('-')
    return _cut(text, MAX_LENGTH)


def _cut(slug, limit):
    """Cut a slug that's longer than limit bytes at its last '-' that fits."""
    data = slug.encode('utf-8')
    if len(data) <= limit:
        return slug
    cut = data[:limit].decode('utf-8', 'ignore')  # Drops a character split at the limit.
    if '-' in cut:
        cut = cut[:cut.rindex('-')]
    return cut.strip('-')


def unique_slugs(titles):
    """Slugs for a whole catalog, in order: a slug an earlier product has taken
    gets -2, -3, ... (an empty slug is 'product')."""
    taken = set()
    slugs = []
    for title in titles:
        base = slugify(title) or 'product'
        slug, number = base, 1
        while slug in taken:
            number += 1
            suffix = f'-{number}'
            slug = _cut(base, MAX_LENGTH - len(suffix)) + suffix
        taken.add(slug)
        slugs.append(slug)
    return slugs
