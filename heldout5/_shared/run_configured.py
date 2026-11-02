"""Use a separate model registry with the ordinary benchmark entry point.

Only the default registry path is substituted. Harness files, prompts, tools,
budgets, and model request handling stay unchanged. This avoids modifying the
models.toml bytes sealed by the earlier sanity checks.
"""
from pathlib import Path
import runpy
import sys


def main():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from beambench import neutral
    registry = root / 'heldout5/ADDITIONAL_MODELS.toml'
    neutral.load_models(registry)  # Validate before dispatching the normal CLI.
    neutral.load_models.__defaults__ = (registry,)
    sys.argv = ['beambench', *sys.argv[1:]]
    runpy.run_module('beambench', run_name='__main__')


if __name__ == '__main__':
    main()
