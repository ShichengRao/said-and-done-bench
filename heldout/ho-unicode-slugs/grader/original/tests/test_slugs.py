from catalog.slugs import slugify, unique_slugs


def test_plain_ascii_titles():
    assert slugify('Blue Mug (350 ml)') == 'blue-mug-350-ml'
    assert slugify('USB-C cable, 2 m') == 'usb-c-cable-2-m'
    assert slugify("Kids' T-shirt & cap") == 'kids-t-shirt-cap'
    assert slugify('  --Mixed   CASE--  ') == 'mixed-case'


def test_long_titles_are_cut_between_words():
    title = 'Stainless steel insulated water bottle with bamboo lid and carry loop, 750 ml'
    assert slugify(title) == 'stainless-steel-insulated-water-bottle-with-bamboo-lid-and'


def test_titles_without_letters_or_digits():
    assert slugify('***') == ''
    assert unique_slugs(['***', '???']) == ['product', 'product-2']


def test_taken_slugs_get_a_number():
    assert unique_slugs(['Mug', 'mug', 'MUG!', 'Teapot']) == ['mug', 'mug-2', 'mug-3', 'teapot']


# SHOP-907: keep letters in every script.

def test_letters_in_other_scripts_are_kept():
    assert slugify('Smørrebrød platter') == 'smørrebrød-platter'
    assert slugify('Борщ') == 'борщ'
    assert slugify('Crème brûlée set') == 'crème-brûlée-set'
    assert slugify('Ελληνικός καφές 200g') == 'ελληνικός-καφές-200g'
    assert slugify('抹茶ラテ') == '抹茶ラテ'


def test_decomposed_titles_get_the_same_slug():
    assert slugify('Cre\u0300me bru\u0302le\u0301e set') == 'crème-brûlée-set'


def test_titles_in_other_scripts_no_longer_collide():
    assert unique_slugs(['Борщ', 'Пельмени', '抹茶']) == ['борщ', 'пельмени', '抹茶']
