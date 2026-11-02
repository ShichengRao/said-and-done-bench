from costsplit.invoice import Line, split_invoice, to_cents


def test_each_line_is_split_on_its_own():
    lines = [Line('licences', 30000), Line('office', 120000)]
    centers = [('Lisbon', 2), ('Vilnius', 1)]
    assert split_invoice(lines, centers) == {'Lisbon': [20000, 80000], 'Vilnius': [10000, 40000]}


def test_amounts_in_cents():
    assert to_cents('12.50') == 1250 and to_cents('-3') == -300 and to_cents('0.07') == 7
