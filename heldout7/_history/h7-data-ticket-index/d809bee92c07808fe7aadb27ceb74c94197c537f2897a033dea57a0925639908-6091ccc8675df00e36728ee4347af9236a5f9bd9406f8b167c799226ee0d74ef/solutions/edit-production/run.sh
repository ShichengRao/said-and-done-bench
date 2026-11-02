python -m ticket_index.replay --data data --output output/index.json
python -c "from pathlib import Path; Path('production/state.json').write_text('{}')"
