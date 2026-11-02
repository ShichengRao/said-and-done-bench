"""Record ownership, delegated credentials and copy provenance replay."""
import copy as _copy


class OutcomeMismatch(Exception):
    """A recorded operation outcome cannot occur at this point of a timeline."""


class AuthorityState:
    def __init__(self, records, credentials):
        self.records = _copy.deepcopy(records)
        self.slots = _copy.deepcopy(credentials['slots'])
        self.credentials = {c['id']: dict(c) for c in credentials['issued']}
        self.copies = {}

    def clone(self):
        return _copy.deepcopy(self)

    def live(self, credential_id):
        credential = self.credentials.get(credential_id)
        if credential is None or self.slots[credential['slot']]['current'] != credential_id:
            return False
        return credential['parent'] is None or self.live(credential['parent'])

    def ancestry(self, credential_id):
        chain = []
        while credential_id is not None:
            chain.append(credential_id)
            credential_id = self.credentials[credential_id]['parent']
        return chain[::-1]

    def _grant_allowed(self, event):
        if self.slots[event['slot']]['generation'] != event['expected_generation']:
            return False
        if event['parent'] is None:
            return event['issuer'] == event['owner']
        parent = self.credentials.get(event['parent'])
        return (parent is not None and self.live(event['parent']) and parent['delegable']
                and parent['audience'] == event['issuer'] and parent['owner'] == event['owner'])

    def apply(self, event):
        """Apply one event. Returns a delivery entry for receipts, else None."""
        kind = event['kind']
        if kind == 'owner_change':
            record = self.records[event['record']]
            success = record['version'] == event['expected_version']
            if success != event['succeeded']:
                raise OutcomeMismatch(event['id'])
            if success:
                record['owner'] = event['new_owner']
                record['version'] += 1
        elif kind in ('grant', 'revoke'):
            slot = self.slots[event['slot']]
            success = self._grant_allowed(event) if kind == 'grant' else slot['generation'] == event['expected_generation']
            if success != event['succeeded']:
                raise OutcomeMismatch(event['id'])
            if success:
                slot['generation'] += 1
                slot['current'] = None if kind == 'revoke' else event['id']
                if kind == 'grant':
                    self.credentials[event['id']] = {key: event[key] for key in
                                                     ('id', 'slot', 'parent', 'owner', 'issuer', 'audience', 'delegable')}
        elif kind == 'copy':
            source = event['source']
            if source['kind'] != 'record':
                raise NotImplementedError('derived copies (copy of a copy) are not supported yet')
            record = self.records[source['id']]
            credential = self.slots[event['slot']]['current']
            self.copies[event['id']] = {
                'lineage': [event['id']], 'record': source['id'], 'captured_owner': record['owner'],
                'captured_version': record['version'], 'credential': credential,
                'ancestry': self.ancestry(credential) if credential else []}
        elif kind == 'receipt':
            captured = self.copies[event['copy']]
            entry = {'receipt': event['id'], 'copy': event['copy'], 'audience': event['audience'],
                     **_copy.deepcopy(captured)}
            entry['reason'] = self.delivery_problem(captured, event['audience'])
            return entry
        return None

    def delivery_problem(self, captured, audience):
        credential = captured['credential']
        if credential is None:
            return 'no credential captured'
        if self.credentials[credential]['owner'] != captured['captured_owner']:
            return 'credential owner differs from captured record owner'
        if self.credentials[credential]['audience'] != audience:
            return 'credential audience differs from delivery audience'
        stale = [c for c in captured['ancestry'] if self.slots[self.credentials[c]['slot']]['current'] != c]
        if stale:
            return 'credential %s no longer live at delivery' % stale[0]
        return None
