set -euo pipefail
python -m meter_billing replay --history data/customer_history.json --store output/billing.db --output output/adjustments.json
