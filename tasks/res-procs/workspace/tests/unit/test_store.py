import pytest

from tallyd.store import InvalidName, Store


def test_incr_and_get():
    store = Store()
    assert store.get('jobs') is None
    assert store.incr('jobs') == 1
    assert store.incr('jobs', 4) == 5
    assert store.get('jobs') == 5


def test_names_can_be_any_printable_text():
    store = Store()
    assert store.incr('café', 2) == 2
    assert store.incr('日本語') == 1
    assert store.get('café') == 2


@pytest.mark.parametrize('name', ['', 'x' * 201, 'tab\there', None])
def test_bad_names(name):
    with pytest.raises(InvalidName):
        Store().incr(name)


def test_by_must_be_an_integer():
    with pytest.raises(ValueError):
        Store().incr('jobs', '3')


def test_top():
    store = Store()
    for name, by in [('a', 3), ('b', 5), ('c', 3), ('d', 1)]:
        store.incr(name, by)
    assert store.top(3) == [('b', 5), ('a', 3), ('c', 3)]


def test_deltas_are_the_increments_since_last_taken():
    store = Store()
    store.incr('a', 2)
    store.incr('b')
    store.incr('a')
    assert store.take_deltas() == {'a': 3, 'b': 1}
    assert store.take_deltas() == {}
    store.incr('b', 5)
    assert store.take_deltas() == {'b': 5} and store.get('b') == 6
