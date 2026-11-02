"""A pytest plugin the grader loads with `-p beam_order` to control test order.

It wraps every other pytest_collection_modifyitems implementation (the
workspace conftest's shuffle included) and runs after them, so whatever the
agent's conftest does to the order, the grader's order wins.

BEAM_ORDER_RECORD=path  write the collected node ids, before anyone reorders them
BEAM_ORDER_FILE=path    a JSON list of node ids to run first, in that order
BEAM_ORDER_ONLY=1       ...and deselect everything else
"""

import json
import os

import pytest


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    record = os.environ.get('BEAM_ORDER_RECORD')
    if record:
        with open(record, 'w', encoding='utf-8') as f:
            json.dump([item.nodeid for item in items], f)
    result = yield
    order_file = os.environ.get('BEAM_ORDER_FILE')
    if order_file:
        with open(order_file, encoding='utf-8') as f:
            wanted = json.load(f)
        by_id = {item.nodeid: item for item in items}
        first = [by_id[nodeid] for nodeid in wanted if nodeid in by_id]
        chosen = {id(item) for item in first}
        rest = [item for item in items if id(item) not in chosen]
        if os.environ.get('BEAM_ORDER_ONLY') == '1':
            if rest:
                config.hook.pytest_deselected(items=rest)
            items[:] = first
        else:
            items[:] = first + rest
    return result
