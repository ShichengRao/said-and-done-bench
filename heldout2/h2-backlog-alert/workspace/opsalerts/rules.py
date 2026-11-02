"""Alert rules: loading alerts/rules.toml and checking it.

Each rule is a `[[rule]]` table:

    name       unique, lowercase words joined by dashes
    metric     the metric the rule watches
    match      optional: label values a series must have, e.g. {mount = "/var"}
    sum_by     optional: sum the matching series at each scrape, grouped by these labels;
               without it, each series is watched on its own
    op         one of > >= < <=
    threshold  a number
    for        how long the condition must hold before the alert fires: "0s", "90s", "5m", "1h"
    severity   "page" (wakes someone up) or "ticket" (next working day)
    summary    one line for the notification
"""

import dataclasses
import re
import tomllib
from pathlib import Path

OPS = ('>', '>=', '<', '<=')
SEVERITIES = ('page', 'ticket')
NAME = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
DURATION = re.compile(r'^(\d+)([smh])$')
DEFAULT_PATH = Path(__file__).resolve().parent.parent / 'alerts' / 'rules.toml'


class RuleError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class Rule:
    name: str
    metric: str
    op: str
    threshold: float
    for_seconds: int
    severity: str
    summary: str
    match: tuple = ()  # ((label, value), ...)
    sum_by: tuple | None = None  # (label, ...), or None to watch each series


def seconds(text):
    found = DURATION.match(str(text))
    if not found:
        raise RuleError(f'not a duration: {text!r} (use e.g. "90s", "5m", "1h")')
    return int(found.group(1)) * {'s': 1, 'm': 60, 'h': 3600}[found.group(2)]


def parse(table, index):
    where = f'rule {index + 1}' + (f' ({table["name"]})' if isinstance(table.get('name'), str) else '')
    allowed = {'name', 'metric', 'match', 'sum_by', 'op', 'threshold', 'for', 'severity', 'summary'}
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise RuleError(f'{where}: unknown field(s) {", ".join(unknown)}')
    for field in ('name', 'metric', 'op', 'threshold', 'for', 'severity', 'summary'):
        if field not in table:
            raise RuleError(f'{where}: missing {field}')
    if not isinstance(table['name'], str) or not NAME.match(table['name']):
        raise RuleError(f'{where}: name must be lowercase words joined by dashes')
    if not isinstance(table['metric'], str) or not table['metric']:
        raise RuleError(f'{where}: metric must be a metric name')
    if table['op'] not in OPS:
        raise RuleError(f'{where}: op must be one of {" ".join(OPS)}')
    if isinstance(table['threshold'], bool) or not isinstance(table['threshold'], (int, float)):
        raise RuleError(f'{where}: threshold must be a number')
    if table['severity'] not in SEVERITIES:
        raise RuleError(f'{where}: severity must be "page" or "ticket"')
    match = table.get('match', {})
    if not isinstance(match, dict) or not all(isinstance(v, str) for v in match.values()):
        raise RuleError(f'{where}: match must be a table of label = "value"')
    sum_by = table.get('sum_by')
    if sum_by is not None and (not isinstance(sum_by, list) or not all(isinstance(v, str) for v in sum_by)):
        raise RuleError(f'{where}: sum_by must be a list of label names')
    return Rule(
        name=table['name'], metric=table['metric'], op=table['op'], threshold=float(table['threshold']),
        for_seconds=seconds(table['for']), severity=table['severity'], summary=str(table['summary']),
        match=tuple(sorted(match.items())), sum_by=None if sum_by is None else tuple(sum_by),
    )


def load(path=DEFAULT_PATH):
    try:
        document = tomllib.loads(Path(path).read_text(encoding='utf-8'))
    except tomllib.TOMLDecodeError as error:
        raise RuleError(f'{path}: {error}') from None
    unknown = sorted(set(document) - {'rule'})
    if unknown:
        raise RuleError(f'{path}: unknown top-level key(s) {", ".join(unknown)}')
    rules = [parse(table, index) for index, table in enumerate(document.get('rule', []))]
    names = [rule.name for rule in rules]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise RuleError(f'{path}: more than one rule named {", ".join(duplicates)}')
    return rules
