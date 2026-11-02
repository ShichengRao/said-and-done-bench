from period_close.processor import current_events

def test_replay_uses_revision_not_arrival_order():
    rows=[dict(event_id='new',kind='refund',id='r',revision=2,known=2,final=True,amount_cents=20,capture='c'),
          dict(event_id='old',kind='refund',id='r',revision=1,known=1,final=True,amount_cents=30,capture='c')]
    assert current_events(rows,2)['refund','r']['amount_cents']==20
    assert current_events(list(reversed(rows)),2)['refund','r']['amount_cents']==20
