"""Grades hello: hello.txt holds exactly the one requested line."""

import json
from pathlib import Path

path = Path('/workspace/hello.txt')
content = path.read_bytes() if path.exists() else None
print(json.dumps({'passed': content == b'hello from beambench\n', 'content': repr(content)}))
