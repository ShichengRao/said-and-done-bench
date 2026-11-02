#!/usr/bin/env bash
set -euo pipefail
python3 settlement.py data/request.json > audit.json
python3 -m pytest
