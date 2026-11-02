set -euo pipefail
python -m procurement apply --input data/customer_update.json --store output/procurement.db --output output/replacement_result.json
