def row(**payload):
    return dict(revision=1, known=1, signed=True, void=False, **payload)


def small_batch():
    return dict(batch='sample', as_of=1, accounts=[dict(id='A', balance=3), dict(id='B', balance=0)],
                owners=[row(id='alice', wallet='A'), row(id='bob', wallet='B')],
                payouts=[row(id='one', source_owner='alice', destination_owner='bob', cents=3, receipt_after=[])],
                bridges=[])
