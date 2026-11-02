#!/bin/bash
set -eu
python3 -m pipeline
python3 -m pytest -q
