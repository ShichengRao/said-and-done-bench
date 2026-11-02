"""Inspection report adapter. See docs/inspection_adapter.md."""


class InspectionAdapter:
    def __init__(self, bundle, offers):
        self.bundle = bundle
        self.offers = offers  # route id -> normalized current offer
        self.accepted = []
        self.scenarios = {s['id']: s for s in bundle['scenarios']}
        self.reports = list(bundle.get('inspections', []))

    def with_commitments(self, accepted):
        self.accepted = accepted
        return self

    def entitled(self, stage, funded):
        """Reports earned by accepted snapshots or by routes funded strictly before ``stage``."""
        pay = {o['id']: o['pay_stage'] for o in self.bundle['obligations']}
        earned = {i for c in self.accepted for i in c['route']['inspection_ids']}
        # Every report listed on an available offer is treated as received.
        for route in self.offers.values():
            if route['obligation'] in pay:
                earned.update(route.get('inspection_ids', []))
        return earned

    def frame(self, scenario_id, stage, funded):
        scenario = self.scenarios[scenario_id]
        earned = self.entitled(stage, funded)
        reports = sorted([r['id'], r['results'][scenario_id]] for r in self.reports if r['stage'] == stage and r['id'] in earned)
        return [scenario['signals'][stage], scenario_id if stage >= scenario['reveal_stage'] else '', reports]

    def history(self, scenario_id, stage, funded):
        return [self.frame(scenario_id, k, funded) for k in range(stage + 1)]
