"""Checks over the whole catalog export in tests/data/ (slow: run with -m slow)."""

import csv
from pathlib import Path

import pytest

from catalog.export import read_catalog
from catalog.slugs import MAX_LENGTH, slugify, unique_slugs

pytestmark = pytest.mark.slow

DATA = Path(__file__).parent / 'data'


@pytest.fixture(scope='module')
def catalog():
    return read_catalog(DATA / 'catalog.csv')


@pytest.fixture(scope='module')
def slugs(catalog):
    return unique_slugs(title for _, title in catalog)


def test_plain_ascii_titles_keep_their_published_slugs(catalog):
    with (DATA / 'published_slugs.csv').open(newline='', encoding='utf-8') as handle:
        published = {int(row['id']): row['slug'] for row in csv.DictReader(handle)}
    changed = [(product_id, title, published[product_id], slugify(title))
               for product_id, title in catalog if title.isascii() and slugify(title) != published[product_id]]
    assert changed[:10] == []


def test_every_slug_fits_the_column(slugs):
    too_long = [(slug, len(slug.encode('utf-8'))) for slug in slugs if len(slug.encode('utf-8')) > MAX_LENGTH]
    assert too_long[:10] == []


def test_slugs_are_unique(slugs):
    assert len(set(slugs)) == len(slugs)


def test_a_slug_is_its_own_slug(slugs):
    unstable = [slug for slug in slugs if slugify(slug) != slug]
    assert unstable[:10] == []
