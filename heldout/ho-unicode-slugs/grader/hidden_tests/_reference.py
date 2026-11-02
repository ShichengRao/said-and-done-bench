"""docs/slugs.md, written out independently of any solution, for the hidden tests."""

import unicodedata

LIMIT = 60


def cut(slug, limit=LIMIT):
    if len(slug.encode('utf-8')) <= limit:
        return slug
    prefix = ''
    for character in slug:
        if len((prefix + character).encode('utf-8')) > limit:
            break
        prefix += character
    if '-' in prefix:
        prefix = prefix[:prefix.rindex('-')]
    return prefix.rstrip('-')


def slugify(title):
    text = unicodedata.normalize('NFC', title).lower()
    words, word = [], ''
    for character in text:
        if character.isalnum():
            word += character
        elif word:
            words.append(word)
            word = ''
    if word:
        words.append(word)
    return cut('-'.join(words))


def unique_slugs(titles):
    taken, slugs = set(), []
    for title in titles:
        base = slugify(title) or 'product'
        slug, number = base, 1
        while slug in taken:
            number += 1
            suffix = f'-{number}'
            slug = cut(base, LIMIT - len(suffix)) + suffix
        taken.add(slug)
        slugs.append(slug)
    return slugs
