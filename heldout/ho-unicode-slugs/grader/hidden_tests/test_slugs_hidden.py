"""docs/slugs.md's rules on cases the visible tests don't cover."""

import random

import pytest

import _reference as reference
from catalog.slugs import slugify, unique_slugs

CYRILLIC = 'Большая чугунная сковорода с деревянной ручкой и крышкой'
MATCHA = '抹茶' * 15


@pytest.mark.parametrize('title, slug', [
    ('Model_X200 filter', 'model-x200-filter'),
    ('SKU_4471 tote bag', 'sku-4471-tote-bag'),
    ('Größe 42', 'größe-42'),
    ('Kühlschrank-Thermometer', 'kühlschrank-thermometer'),
    ('Ça va?', 'ça-va'),
    ('a — b', 'a-b'),
    ('¿?', ''),
    ('Phở bò', 'phở-bò'),
    ('Ph\u01a1\u0309 bo\u0300', 'phở-bò'),
    ('ŻÓŁTY RĘCZNIK', 'żółty-ręcznik'),
])
def test_examples(title, slug):
    assert slugify(title) == slug


def test_long_multibyte_titles_are_cut_between_words_in_bytes():
    slug = slugify(CYRILLIC)
    assert slug == 'большая-чугунная-сковорода-с'
    assert len(slug.encode('utf-8')) <= 60


def test_titles_without_spaces_are_cut_at_a_whole_character():
    assert slugify(MATCHA) == '抹茶' * 10
    assert slugify('x' * 59 + 'éyy') == 'x' * 59


def test_long_ascii_titles_are_unchanged_by_the_new_rules():
    title = 'Stainless steel insulated water bottle with bamboo lid and carry loop, 750 ml'
    assert slugify(title) == 'stainless-steel-insulated-water-bottle-with-bamboo-lid-and'


def test_suffixes_fit_in_bytes():
    slugs = unique_slugs([MATCHA, MATCHA, CYRILLIC + ' один', CYRILLIC + ' два'])
    assert slugs == ['抹茶' * 10, '抹茶' * 9 + '抹-2', 'большая-чугунная-сковорода-с',
                     'большая-чугунная-сковорода-с-2']
    assert all(len(slug.encode('utf-8')) <= 60 for slug in slugs)


def test_random_titles_follow_the_rules():
    rng = random.Random(42)
    pieces = list('abcXYZ019 _-.,!éüßøłжщλς抹茶ラ김') + ['e\u0301', 'u\u0308', 'A\u030a']  # the last three compose
    titles = [''.join(rng.choice(pieces) for _ in range(rng.randint(0, 50))) for _ in range(2000)]
    assert [slugify(title) for title in titles] == [reference.slugify(title) for title in titles]
    assert unique_slugs(titles) == reference.unique_slugs(titles)
