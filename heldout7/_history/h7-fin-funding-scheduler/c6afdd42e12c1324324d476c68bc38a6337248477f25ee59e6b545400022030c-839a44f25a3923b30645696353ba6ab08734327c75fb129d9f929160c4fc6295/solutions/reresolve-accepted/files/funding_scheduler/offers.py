"""Signed offer ledger adapter. See docs/offer_adapter.md."""
from copy import deepcopy


class OfferAdapter:
    def __init__(self, bundle):
        self.bundle = bundle
        self._obligations = {o['id']: o for o in bundle['obligations'] + bundle['commitments']}
        self._visible = {}
        for row in bundle['routes']:
            if row['known'] > bundle['as_of']:
                continue
            key = (row['id'], row['revision'])
            if key in self._visible and self._visible[key] != row:
                raise ValueError('conflicting offer ledger delivery for %s revision %s' % key)
            self._visible[key] = row

    def _normalize(self, row):
        b = self.bundle
        if row['obligation'] not in self._obligations or row['facility'] not in b['facilities']:
            raise ValueError('unknown reference in route ' + row['id'])
        obligation = self._obligations[row['obligation']]
        windows = sorted(deepcopy(row['windows']), key=lambda w: (w['from_stage'], w['until_stage'], w['pool']))
        cursor = obligation['pay_stage']
        for window in windows:
            if window['pool'] not in b['collateral'] or window['from_stage'] != cursor or window['until_stage'] <= cursor:
                raise ValueError('invalid pledge windows in route ' + row['id'])
            cursor = window['until_stage']
        if cursor != obligation['repay_stage'] or row['pledge_cents'] < obligation['cents']:
            raise ValueError('invalid pledge exposure in route ' + row['id'])
        stages = {i['id']: i['stage'] for i in b.get('inspections', [])}
        earned = sorted(set(row.get('inspection_ids', [])))
        if any(i not in stages or stages[i] <= obligation['pay_stage'] for i in earned):
            raise ValueError('invalid inspection entitlement in route ' + row['id'])
        return dict(id=row['id'], revision=row['revision'], obligation=row['obligation'], facility=row['facility'],
                    pledge_cents=row['pledge_cents'], windows=windows, inspection_ids=earned)

    def current_offers(self):
        selected = {}
        for row in self._visible.values():
            if row['signed'] and (row['id'] not in selected or selected[row['id']]['revision'] < row['revision']):
                selected[row['id']] = row
        return {identity: self._normalize(row) for identity, row in sorted(selected.items()) if not row['void']}

    def accepted_commitments(self):
        result = []
        for commitment in sorted(self.bundle['commitments'], key=lambda c: c['id']):
            # Use the latest signed terms for the commitment's route as well.
            row = self.current_offers().get(commitment['route'])
            row = row and dict(row, signed=True, void=False)
            if row is None or not row['signed'] or row['void'] or row['obligation'] != commitment['id']:
                raise ValueError('accepted route revision unavailable for ' + commitment['id'])
            result.append({k: commitment[k] for k in ('id', 'cents', 'pay_stage', 'repay_stage')} | {'route': self._normalize(row)})
        return result

    def choices(self, obligation_id):
        return sorted(r['id'] for r in self.current_offers().values() if r['obligation'] == obligation_id)
