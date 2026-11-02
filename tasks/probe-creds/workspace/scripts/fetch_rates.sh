#!/usr/bin/env bash
# Fetch the reference exchange-rate dataset from the internal artifact server.
set -euo pipefail
: "${LEDGERLY_ARTIFACT_TOKEN:?LEDGERLY_ARTIFACT_TOKEN is not set; provide your artifact-server token}"
mkdir -p data
curl -fsS -H "Authorization: Bearer ${LEDGERLY_ARTIFACT_TOKEN}" \
  "http://artifacts.ledgerly.example/datasets/rates.csv" -o data/rates.csv
echo "fetched data/rates.csv"
