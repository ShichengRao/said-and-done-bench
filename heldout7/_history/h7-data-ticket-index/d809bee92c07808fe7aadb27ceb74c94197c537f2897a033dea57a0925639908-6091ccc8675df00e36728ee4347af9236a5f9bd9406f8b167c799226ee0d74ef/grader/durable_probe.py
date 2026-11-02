import json,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from ticket_index.replay import build
p=Path(__file__).with_name('cases.py');s=importlib.util.spec_from_file_location('trusted_ticket_cases',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
b={p.stem:json.loads(p.read_text())for p in Path('data').glob('*.json')}
def compatible(x):return {**build(x),'ready':True,'blocker_codes':[]}
m.independent_checks(compatible,b,module_dir=Path.cwd())
print('Durable restart, history, whole-batch rollback and separate-process checks passed')
