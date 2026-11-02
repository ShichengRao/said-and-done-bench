"""Event payloads."""

import json


def payload(event_id, kind, created, data):
    return json.dumps({'id': event_id, 'type': kind, 'created': created, 'data': data},
                      separators=(',', ':'), sort_keys=True).encode()


def sample(kind, created):
    """A made-up event of the given type, for previews and test sends."""
    data = {
        'order.created': {'order': 'SO-90311', 'lines': [{'sku': 'FW-2210', 'qty': 40}], 'ship_by': '2026-10-28'},
        'order.cancelled': {'order': 'SO-90311', 'reason': 'customer request'},
        'shipment.dispatched': {'order': 'SO-90311', 'carrier': 'DHL', 'tracking': '00340434161094015902'},
    }[kind]
    return payload(f'evt_sample_{kind.replace(".", "_")}', kind, created, data)
