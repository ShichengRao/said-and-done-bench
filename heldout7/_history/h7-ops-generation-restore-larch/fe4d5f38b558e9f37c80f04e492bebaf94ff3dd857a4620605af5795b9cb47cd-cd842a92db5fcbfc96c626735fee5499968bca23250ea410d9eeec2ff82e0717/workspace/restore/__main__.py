"""Run a generation restore and atomically publish its bytes."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from .decoder import recover

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        value = recover(json.loads(Path(args.input).read_text()))
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name); stream.write(value); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()
    print(str(destination))

if __name__ == '__main__': main()
