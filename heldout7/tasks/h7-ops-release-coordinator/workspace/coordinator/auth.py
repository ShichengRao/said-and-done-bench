from coordinator.crypto import verify_signature


def resources(body):
    return set(body['expected']) | set(body['writes'])


def authorized(envelope, grants, keys, tick):
    """True when one current grant covers the whole operation at this tick and signed it."""
    body = envelope['signed']
    for grant in grants.values():
        if grant['principal'] != body['principal'] or grant['revoked']:
            continue
        if not grant['valid_from'] <= tick <= grant['valid_to']:
            continue
        if not resources(body) <= set(grant['resources']):
            continue
        key = keys.get(grant['keyid'])
        if key is None:
            continue
        if any(signature.get('keyid') == grant['keyid'] and verify_signature(body, signature, key)
               for signature in envelope['signatures']):
            return True
    return False


def in_window(body, tick):
    window = body['window']
    return window['not_before'] <= tick <= window['not_after']
