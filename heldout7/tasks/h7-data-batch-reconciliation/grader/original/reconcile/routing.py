"""Route usability and local start options for each request."""
from .records import credentials


def route_options(batch):
    """{request_id: [{route, start, pools}]} sorted by route ID then start; ignores shared allowance."""
    table = credentials(batch)
    options = {}
    for request in sorted(batch['requests'], key=lambda q: q['id']):
        found = []
        for route in sorted(batch['routes'], key=lambda r: r['id']):
            if route['request'] != request['id']:
                continue
            chain = [table[name] for name in route['credentials']]
            if not chain or chain[0]['parent'] is not None or chain[-1]['id'] not in request['leaves']:
                continue
            if any(child['parent'] != parent['id'] for parent, child in zip(chain, chain[1:])):
                continue
            if any(not set(request['scopes']) <= set(c['scopes']) for c in chain):
                continue
            pools = sorted({c['pool'] for c in chain})
            for t in sorted(batch['slots']):
                finish = t + request['duration']
                if t < request['earliest'] or finish > request['latest']:
                    continue
                if any(t < c['start'] or finish > c['end'] for c in chain):
                    continue
                found.append({'route': route['id'], 'start': t, 'pools': pools})
        options[request['id']] = found
    return options
