from ticket_index.projection import Projection
from ticket_index.replay import build
from ticket_index.seal import digest

INITIAL = {'folders': {'root': {'parent': None, 'acl': ['g']}},
           'documents': {'d': {'folder': 'root', 'title': 'Example', 'acl': None, 'deleted': False}},
           'memberships': {'u': ['g']}}


def test_initial_query():
    assert build({'initial': INITIAL, 'request': {'minimum_epoch': 0}, 'trace': [{'kind': 'query', 'epoch': 0, 'user': 'u'}]}) == {
        'trace': [{'kind': 'query', 'epoch': 0, 'user': 'u', 'visible': [{'id': 'd', 'title': 'Example', 'folder': 'root'}]}],
        'published': 0, 'pending': []}


def test_sealed_single_part_epoch_reopens(tmp_path):
    ops = [{'kind': 'put_document', 'id': 'd', 'folder': 'root', 'title': 'Renamed', 'acl': None, 'deleted': False}]
    store = Projection(tmp_path / 'state' / 'index.sqlite', INITIAL)
    store.ingest([{'kind': 'fragment', 'epoch': 1, 'part': 0, 'parts': 1, 'operations': ops},
                  {'kind': 'seal', 'epoch': 1, 'parts': 1, 'digests': [digest(ops)]}])
    reopened = Projection(tmp_path / 'state' / 'index.sqlite')
    assert reopened.status() == {'published': 1, 'pending': []}
    assert reopened.query(0, 'u')[0]['title'] == 'Example' and reopened.query(1, 'u')[0]['title'] == 'Renamed'
