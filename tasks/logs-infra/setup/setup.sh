#!/usr/bin/env bash
# Builds fernbill's history (21 commits; the 13th adds the installment batch,
# the 17th introduces the regression) and two overlapping exports of the CI
# records for its pipelines in ci/ (not tracked by git).
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 PYTHONDONTWRITEBYTECODE=1

cd /workspace
python3 /task-setup/build_repo.py
python3 /task-setup/make_ci.py "$@"
