import json
from pathlib import Path
from recovery import initialize,ingest,advance,inspect
def test_rehearsal_restart_and_replay(tmp_path):
    s=json.loads(Path('data/rehearsal.json').read_text());db=tmp_path/'state.sqlite';initialize(db,s['snapshot'])
    for b in s['batches']:ingest(db,b)
    result=advance(db,s['target'])
    assert result['rows']=={'cash-a':35,'cash-b':105}
    for b in s['batches']:ingest(db,b)
    assert advance(db,s['target'])==result and inspect(db)['checkpoint']==result
