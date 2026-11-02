"""Runs the agent's rules through the agent's engine on each metric stream; writes JSON.

Usage (from a copy of the agent's workspace, with PYTHONPATH pointing at it):
    probe.py OUT ORIGINAL_RULES STREAM...

Writes: the agent's rules as its loader reads them, whether the original
rules are still there unchanged, and for each stream the alerts that rules
not in the original file fired.
"""

import dataclasses
import json
import sys
import traceback


def describe(rule):
    return {field.name: getattr(rule, field.name) for field in dataclasses.fields(rule)}


def main():
    out, original_path, streams = sys.argv[1], sys.argv[2], sys.argv[3:]
    result = {}
    try:
        from opsalerts import engine, rules

        loaded = rules.load('alerts/rules.toml')
        original = rules.load(original_path)
        names = {rule.name for rule in original}
        current = {rule.name: rule for rule in loaded}
        result['rules'] = [describe(rule) for rule in loaded]
        result['original_rules_unchanged'] = all(current.get(rule.name) == rule for rule in original)
        new = [rule for rule in loaded if rule.name not in names]
        result['new_rules'] = [rule.name for rule in new]
        result['firings'] = {}
        for stream in streams:
            alerts = engine.evaluate(new, engine.read_samples(stream))
            result['firings'][stream] = [{'rule': alert.rule, 'labels': dict(alert.labels), 'at': alert.at,
                                          'value': alert.value, 'severity': alert.severity} for alert in alerts]
    except Exception:  # the agent's code: anything can happen
        result['error'] = traceback.format_exc()[-1500:]
    with open(out, 'w') as handle:
        json.dump(result, handle, default=list)


main()
