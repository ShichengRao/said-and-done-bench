"""Replay of transaction operations onto the base snapshot."""
import copy


def replay(snapshot, transactions):
    """Apply `transactions` (already ordered) and return (customers, aliases) in output order."""
    customers = {(c['tenant'], c['id']): copy.deepcopy(c) for c in snapshot['customers']}
    aliases = {(a['tenant'], a['alias']): a['customer'] for a in snapshot['aliases']}
    for txn in transactions:
        if txn['decision'] != 'commit':  # unresolved and aborted rows are skipped
            continue  # aborted transactions apply nothing
        for op in txn['operations']:
            key = (op['tenant'], op['alias'])
            if op['kind'] == 'bind':
                if (op['tenant'], op['customer']) not in customers:
                    raise ValueError('%s binds unknown customer' % txn['id'])
                aliases[key] = op['customer']
                continue
            if op['kind'] == 'unbind':
                aliases.pop(key, None)
                continue
            if key not in aliases:
                raise ValueError('%s uses unbound alias %s/%s' % ((txn['id'],) + key))
            customer = customers[(op['tenant'], aliases[key])]
            if op['kind'] == 'adjust':
                if customer['seats'] + op['delta'] < 0:
                    raise ValueError('%s makes seats negative' % txn['id'])
                customer['seats'] += op['delta']
            elif op['kind'] == 'tier':
                customer['tier'] = op['value']
            elif op['kind'] == 'close':
                customer['active'] = False
    return ([customers[k] for k in sorted(customers)],
            [{'tenant': t, 'alias': a, 'customer': aliases[t, a]} for t, a in sorted(aliases)])
