"""Per-repository trust checks: root rotation, snapshot and targets-role verification."""
import copy
import hashlib

from installer.crypto import canonical, verify_signature


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def require_threshold(envelope, role, keys):
    """Distinct authorized key IDs with valid signatures over the envelope body must meet the role threshold."""
    votes = {sig.get('keyid') for sig in envelope['signatures']
             if sig.get('keyid') in role['keyids'] and sig.get('keyid') in keys
             and verify_signature(envelope['signed'], sig, keys[sig['keyid']])}
    if len(votes) < role['threshold']:
        raise ValueError('signature threshold not met')


def rotate_root(root, envelopes, at):
    """Return the root to use for this request."""
    if envelopes:
        raise ValueError('root rotation is not supported yet')
    if not root['not_before'] <= at < root['expires']:
        raise ValueError('trusted root is expired')
    return root


def check_snapshot(repo_state, envelope, root, at):
    body = envelope['signed']
    require_threshold(envelope, root['roles']['snapshot'], root['keys'])
    if body['type'] != 'snapshot' or at >= body['expires']:
        raise ValueError('snapshot type or expiry')
    value = digest(body)
    if body['version'] < repo_state['snapshot_version'] or (
            body['version'] == repo_state['snapshot_version'] and value != repo_state['snapshot_digest']):
        raise ValueError('snapshot rollback or equivocation')
    repo_state['snapshot_version'] = body['version']
    repo_state['snapshot_digest'] = value
    return body


def check_role(repo_state, name, envelope, pin, authorization, root, at):
    """Verify a targets envelope against its snapshot pin, role identity, expiry, signatures and rollback state."""
    if envelope is None or pin is None or len(canonical(envelope)) != pin['length'] or digest(envelope) != pin['sha256']:
        raise ValueError(f'metadata {name} does not match its snapshot pin')
    body = envelope['signed']
    if body['type'] != 'targets' or body['role'] != name or body['version'] != pin['version'] or at >= body['expires']:
        raise ValueError(f'metadata {name} identity or expiry')
    require_threshold(envelope, authorization, root['keys'])
    old = repo_state['roles'].get(name); value = digest(body)
    if old and (body['version'] < old['version'] or (body['version'] == old['version'] and value != old['digest'])):
        raise ValueError(f'metadata {name} rollback or equivocation')
    repo_state['roles'][name] = {'version': body['version'], 'digest': value}
    return body
