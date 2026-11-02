#!/usr/bin/env python3
"""Lint for Kettleby's Python services: the checks CI runs on every push.

Usage: python3 ci/lint.py [PATH ...]   (default: `paths` in ci/lint.toml)

Codes (choose them with `select` in ci/lint.toml):
  E501  line longer than max-line-length
  F401  name imported but never used
  C901  function more complex than max-complexity
  B001  bare `except:`
  T201  print() in library code

A function's complexity is 1, plus 1 for each `if`/`elif`, `for`, `while`,
`except`, conditional expression, `for` or `if` inside a comprehension, and
`case`, plus 1 for each extra operand of `and`/`or`. Nested functions and
classes are measured on their own.

A `# noqa` comment on a reported line silences everything on it, and
`# noqa: C901,E501` silences just those codes.
"""

from __future__ import annotations

import ast
import fnmatch
import re
import sys
import tomllib
from pathlib import Path

CONFIG = Path(__file__).resolve().with_name('lint.toml')
ROOT = CONFIG.parent.parent
NOQA = re.compile(r'#\s*noqa(?::\s*(?P<codes>[A-Z]+\d+(?:\s*,\s*[A-Z]+\d+)*))?', re.IGNORECASE)
BRANCHES = (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.match_case)
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def load_config() -> dict:
    settings = tomllib.loads(CONFIG.read_text(encoding='utf-8'))['lint']
    settings.setdefault('per-file-ignores', {})
    settings.setdefault('exclude', [])
    return settings


def complexity(function: ast.AST) -> int:
    score = 1
    pending = list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        if isinstance(node, SCOPES):
            continue
        if isinstance(node, BRANCHES):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            score += 1 + len(node.ifs)
        pending.extend(ast.iter_child_nodes(node))
    return score


def imported_names(tree: ast.Module) -> list[tuple[str, ast.AST]]:
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names += [((alias.asname or alias.name).split('.')[0], node) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module != '__future__':
            names += [(alias.asname or alias.name, node) for alias in node.names]
    return names


def used_names(tree: ast.Module) -> set[str]:
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(isinstance(t, ast.Name) and t.id == '__all__' for t in targets):
            used |= {elt.value for elt in getattr(node.value, 'elts', [])
                     if isinstance(elt, ast.Constant) and isinstance(elt.value, str)}
    return used


def check_tree(tree: ast.Module, settings: dict) -> list[tuple[int, int, str, str]]:
    problems = []
    used = used_names(tree)
    for name, node in imported_names(tree):
        if name not in used:
            problems.append((node.lineno, node.col_offset + 1, 'F401', f"'{name}' imported but unused"))
    limit = settings['max-complexity']
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            score = complexity(node)
            if score > limit:
                problems.append((node.lineno, node.col_offset + 1, 'C901',
                                 f"'{node.name}' is too complex ({score} > {limit})"))
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            problems.append((node.lineno, node.col_offset + 1, 'B001', 'bare `except:`'))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == 'print'):
            problems.append((node.lineno, node.col_offset + 1, 'T201', 'print() in library code'))
    return problems


def check_file(path: Path, settings: dict) -> list[tuple[int, int, str, str]]:
    source = path.read_text(encoding='utf-8')
    lines = source.splitlines()
    problems = [(number, settings['max-line-length'] + 1, 'E501',
                 f'line too long ({len(line)} > {settings["max-line-length"]})')
                for number, line in enumerate(lines, 1) if len(line) > settings['max-line-length']]
    try:
        problems += check_tree(ast.parse(source, filename=str(path)), settings)
    except SyntaxError as error:
        problems.append((error.lineno or 1, error.offset or 1, 'E999', f'syntax error: {error.msg}'))
    relative = path.resolve().relative_to(ROOT).as_posix()
    ignored = {code for pattern, codes in settings['per-file-ignores'].items()
               if fnmatch.fnmatch(relative, pattern) for code in codes}
    kept = []
    for number, column, code, message in problems:
        if code not in settings['select'] or code in ignored:
            continue
        noqa = NOQA.search(lines[number - 1]) if number <= len(lines) else None
        if noqa and (not noqa['codes'] or code in re.split(r'\s*,\s*', noqa['codes'].upper())):
            continue
        kept.append((number, column, code, message))
    return sorted(kept)


def files_to_check(arguments: list[str], settings: dict) -> list[Path]:
    found = []
    for argument in arguments or settings['paths']:
        path = Path(argument) if arguments else ROOT / argument
        found += sorted(path.rglob('*.py')) if path.is_dir() else [path]
    return [path for path in found if '__pycache__' not in path.parts and not any(
        fnmatch.fnmatch(path.resolve().relative_to(ROOT).as_posix(), pattern)
        for pattern in settings['exclude'])]


def main(arguments: list[str]) -> int:
    settings = load_config()
    count = 0
    for path in files_to_check(arguments, settings):
        for number, column, code, message in check_file(path, settings):
            sys.stdout.write(f'{path.resolve().relative_to(ROOT)}:{number}:{column}: {code} {message}\n')
            count += 1
    sys.stdout.write(f'Found {count} problem{"s" * (count != 1)}.\n' if count else 'All checks passed.\n')
    return 1 if count else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
