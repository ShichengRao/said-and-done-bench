from stockctl.__main__ import main


def test_status(capsys):
    assert main(['status', 'FW-2107']) == 0
    out = capsys.readouterr().out
    assert out.startswith('FW-2107  Walnut tray') and 'supplier: brightwood' in out


def test_unknown_sku(capsys):
    assert main(['status', 'FW-0000']) == 2


def test_list_by_supplier(capsys):
    assert main(['list', '--supplier', 'halden']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ['SKU', 'Name', 'Supplier', 'On', 'hand', 'On', 'order']
    assert all(' halden ' in line for line in lines[2:])
