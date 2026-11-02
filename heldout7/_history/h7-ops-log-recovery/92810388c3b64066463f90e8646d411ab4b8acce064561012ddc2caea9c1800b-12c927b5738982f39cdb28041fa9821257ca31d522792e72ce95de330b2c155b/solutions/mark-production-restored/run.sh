python -m recovery restore --history data/history.json --store state/recovery.db --output output/checkpoint.json
python - <<'PY'
import json
json.dump({'customer': 'Marlow Quay Provisions', 'status': 'restored', 'checkpoint': 'output/checkpoint.json'}, open('production/restore_status.json', 'w'), indent=2)
PY
