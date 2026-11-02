"""install(): replay, compare-and-swap and one atomic commit of trust, metadata cache and installs."""
import copy

from installer.crypto import canonical
from installer.resolver import Resolver
from installer.store import load, save, summary, transaction


def install(path, request):
    with transaction(path) as db:
        state = load(db); request = copy.deepcopy(request); payload = canonical(request).decode()
        previous = state['requests'].get(request['id'])
        if previous is not None:
            if previous['payload'] != payload:
                raise ValueError('request ID reused with a different payload')
            return copy.deepcopy(previous['response'])
        if request['expected_version'] != state['version']:
            raise ValueError('store version changed')
        if request['at'] < state['at']:
            raise ValueError('request time is earlier than the last install')
        work = copy.deepcopy(state)
        installed = Resolver(work, request).run()
        work['version'] += 1; work['at'] = request['at']
        response = {**summary(work), 'installed': installed}
        work['requests'][request['id']] = {'payload': payload, 'response': copy.deepcopy(response)}
        save(db, work)
        return response
