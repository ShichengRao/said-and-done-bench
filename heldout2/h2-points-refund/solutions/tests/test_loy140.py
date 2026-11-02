from loyalty import db, ledger
from loyalty.ledger import Event


def test_refund_takes_back_the_orders_points_once(tmp_path):
    conn = db.create(tmp_path / 'loyalty.sqlite3')
    db.add_customer(conn, 'C-1', 'Marta Ruiz', '2026-02-27')
    for points, order in ((500, 'SO-1'), (400, 'SO-2'), (300, 'SO-3')):
        ledger.record(conn, Event('C-1', 'earn', points, order_id=order))
    ledger.record(conn, Event('C-1', 'refund', order_id='SO-3'))
    assert ledger.balance(conn, 'C-1') == 900
