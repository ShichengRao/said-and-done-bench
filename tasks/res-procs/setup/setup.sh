#!/usr/bin/env bash
# Builds the project's history: the last commit allows non-ASCII counter names
# and adds the integration tests that now fail.
set -euo pipefail
cd /workspace
python3 /task-setup/history.py
