from stockctl import render


def test_table():
    text = render.table(['SKU', 'Name', 'Qty'], [('A-1', 'Mug', 12), ('B-22', 'Teapot', 3)], right=(2,))
    assert text.splitlines() == [
        'SKU   Name    Qty',
        '----  ------  ---',
        'A-1   Mug      12',
        'B-22  Teapot    3',
    ]
