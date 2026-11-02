mkdir -p output
python - <<'PY'
import json
h = json.load(open('data/history.json')); events = {}
for b in h['batches']:
    for e in b['events']: events[(e['shard'], e['lsn'])] = e
values = json.loads(json.dumps(h['snapshot']['values'])); target = h['restore']['target']; order = []
for (shard, lsn), e in sorted(events.items(), key=lambda kv: kv[0][1]):
    if lsn <= target[shard]:
        if e['after'] is None: values[shard].pop(e['key'], None)
        else: values[shard][e['key']] = e['after']
        if e['txid'] not in order: order.append(e['txid'])
processed = {t: 'commit' for t in h['snapshot']['applied'] + order}
json.dump({'checkpoint_id': h['checkpoint_id'], 'version': 4, 'frontier': target, 'values': values, 'processed': processed, 'order': order},
          open('output/checkpoint.json', 'w'), indent=2, sort_keys=True)
PY
