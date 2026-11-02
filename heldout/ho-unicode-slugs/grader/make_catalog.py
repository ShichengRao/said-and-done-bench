"""Builds the catalog export the slow tests check: tests/data/catalog.csv and published_slugs.csv.

Deterministic (seeded), so the grader can rebuild the same files to compare.
published_slugs.csv holds today's slug (the original slugify, imported from
ROOT) of every product whose title is plain ASCII: those URLs are live.
About a tenth of the ASCII titles contain underscores, many titles are
longer than 60 bytes once slugged (multi-byte ones especially, some with no
spaces at all), some Latin titles are decomposed (NFD), and some titles
repeat, so unique_slugs has to add suffixes to long multi-byte slugs.

Usage: python3 make_catalog.py OUT_DIR ROOT
"""

import csv
import random
import sys
import unicodedata
from pathlib import Path

ADJECTIVES = [
    'Blue', 'Red', 'Matte black', 'Stainless steel', 'Organic', 'Recycled', 'Large', 'Small', "Kids'",
    'Heavy-duty', 'Glass', 'Bamboo', 'Wool', 'Cotton', 'Ceramic', 'Cast iron', 'Insulated', 'Foldable',
    'Waterproof', 'Vintage', 'Enamel', 'Linen', 'Walnut', 'Copper', 'Speckled',
]
NOUNS = [
    'mug', 'teapot', 'water bottle', 'lunch box', 'cutting board', 'rain jacket', 'backpack', 'desk lamp',
    'notebook', 'phone case', 'charging cable', 'frying pan', 'throw blanket', 'yoga mat', 'plant pot',
    'coffee grinder', 'salad bowl', 'knife set', 'shower curtain', 'doormat', 'tote bag', 'serving tray',
]
SPECS = [
    '350 ml', '1 L', '2 m', '(pack of 4)', '- size M', '/ 12 cm', 'with lid', '& stand', 'v2.1', '#7',
    '100% cotton', '"XL"', '(2nd edition)', '+ free refill', '@ 220V', '[refurbished]',
]
CODES = ['Model_X200', 'SKU_4471', 'USB_C', 'ref_88-B', 'kit_02', 'A4_dotted', 'size_L', 'v_3']
LONG_TAILS = [
    'with bamboo lid and carry loop for school, office and travel',
    'dishwasher safe, BPA free, keeps drinks cold for 24 hours and hot for 12',
    'set of 6 in assorted colours, gift boxed with a handwritten card',
    'replacement part compatible with all 2019 to 2024 models of the classic range',
]
WORDS = {
    'fr': ['crème', 'brûlée', 'pâte', 'fenêtre', 'théière', 'cafetière', 'bœuf', 'garçon', 'été', 'forêt', 'cœur'],
    'de': ['Straße', 'Größe', 'Müsli', 'Kühlschrank', 'Brötchen', 'Grüße', 'Löffel', 'Schäler', 'Gemüse'],
    'da': ['smørrebrød', 'blåbær', 'rødgrød', 'kø', 'æble', 'sød', 'grød'],
    'pl': ['żółty', 'łódź', 'świeca', 'ręcznik', 'źródło', 'gęś', 'miód'],
    'cs': ['čaj', 'řeřicha', 'kůň', 'dýně', 'hrnek'],
    'ru': ['борщ', 'чайник', 'подушка', 'кружка', 'сковорода', 'одеяло', 'пельмени', 'большая'],
    'el': ['καφές', 'ελιές', 'μέλι', 'κούπα', 'τσάι', 'μεγάλη'],
    'es': ['piñata', 'jalapeño', 'mañana', 'cañón', 'año'],
    'vi': ['phở', 'bánh mì', 'cà phê', 'nước mắm', 'trà'],
    'tr': ['çay', 'şeker', 'bardağı', 'kahve fincanı', 'kaşık'],
}
CJK = {
    'ja': ['抹茶', 'ラテ', '急須', '湯呑み', 'お弁当箱', 'まな板', '風呂敷', 'セット', '限定'],
    'zh': ['茶壶', '绿茶', '保温杯', '筷子', '砧板', '礼盒', '套装'],
    'ko': ['김치', '냄비', '젓가락', '보온병', '세트'],
}
SYMBOLS_ONLY = ['***', '—', '(?)', '!!!', '♥ ♥ ♥', '...']
COUNT = 12000


def ascii_title(rng):
    parts = [rng.choice(ADJECTIVES), rng.choice(NOUNS)]
    if rng.random() < 0.6:
        parts.append(rng.choice(SPECS))
    if rng.random() < 0.12:
        parts.insert(rng.randint(0, len(parts)), rng.choice(CODES))
    if rng.random() < 0.15:
        parts.append(rng.choice(LONG_TAILS))
    return ' '.join(parts)


def other_title(rng):
    if rng.random() < 0.25:
        words = CJK[rng.choice(sorted(CJK))]
        count = rng.randint(2, 12)
        joiner = '' if rng.random() < 0.7 else ' '
        title = joiner.join(rng.choice(words) for _ in range(count))
    else:
        words = WORDS[rng.choice(sorted(WORDS))]
        title = ' '.join(rng.choice(words) for _ in range(rng.randint(1, 9)))
        title = title[0].upper() + title[1:]
        if rng.random() < 0.2:
            title = unicodedata.normalize('NFD', title)
    if rng.random() < 0.4:
        title += ' ' + rng.choice(SPECS)
    return title


def titles(rng):
    made = []
    for _ in range(COUNT):
        roll = rng.random()
        if made and roll < 0.06:
            earlier = rng.choice(made)
            made.append(rng.choice([earlier, earlier.upper(), earlier + '!', earlier.lower()]))
        elif roll < 0.07:
            made.append(rng.choice(SYMBOLS_ONLY))
        elif roll < 0.62:
            made.append(ascii_title(rng))
        else:
            made.append(other_title(rng))
    return made


def build(out, root):
    sys.path.insert(0, str(root))
    from catalog.slugs import slugify
    rng = random.Random(907)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    products, product_id = [], 1000
    for title in titles(rng):
        product_id += rng.choice([1, 1, 1, 2, 3])
        products.append((product_id, title))
    with (out / 'catalog.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(['id', 'title'])
        writer.writerows(products)
    with (out / 'published_slugs.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(['id', 'slug'])
        writer.writerows((product_id, slugify(title)) for product_id, title in products if title.isascii())


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
