set -euo pipefail
python -m refund_worker reconcile --input data/provider_history.json --store output/refunds.db --output output/reconciliation.json
