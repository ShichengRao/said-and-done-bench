from rates.report import average_rate, load_rates


def test_rows_load():
    rows = load_rates()
    assert ("EUR", 1.0910) in rows


def test_average_rate():
    assert average_rate() == 1.1498
