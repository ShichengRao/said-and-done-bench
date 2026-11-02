#!/usr/bin/env bash
set -euo pipefail
python3 recognition.py data/request.json > audit.json
python3 -m pytest
