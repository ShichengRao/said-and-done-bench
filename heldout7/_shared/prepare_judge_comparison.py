"""Curate four closed comparison cases; no model call or candidate execution."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
H=ROOT/'heldout7';OUT=H/'pilot_reviews/automated_comparison'
CASES=[('h7-ops-generation-restore','astra'),('h7-fin-period-close','astra'),
       ('h7-ops-generation-restore','minimax-m2-7'),('h7-ops-generation-restore','flash')]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def new_json(p,value):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:f.write(json.dumps(value,indent=2)+'\n')

def observed_commands(run):
 if (run/'codex.jsonl').exists():
  source=run/'codex.jsonl';result=[];seen=set()
  def walk(value,line):
   if isinstance(value,dict):
    if value.get('type')=='command_execution' and value.get('status')=='completed' and 'exit_code' in value:
     ident=value.get('id',json.dumps(value,sort_keys=True))
     if ident not in seen:
      seen.add(ident);result.append({'source_line':line,'command':value.get('command',''),
        'output':value.get('aggregated_output',''),'exit_code':value['exit_code']})
    for item in value.values():walk(item,line)
   elif isinstance(value,list):
    for item in value:walk(item,line)
  for line,text in enumerate(source.read_text().splitlines(),1):walk(json.loads(text),line)
 else:
  source=run/'neutral.jsonl';result=[];pending=None
  for line,text in enumerate(source.read_text().splitlines(),1):
   event=json.loads(text)
   if 'command' in event:
    pending={'source_line':line,'command':event['command'],'exit_code':event['exit_code'],'seconds':event['seconds']}
   elif 'tool_result' in event and pending:
    payload=event['tool_result'];pending['output']=payload.get('content','') if isinstance(payload,dict) else str(payload)
    result.append(pending);pending=None
 return source,result

def main():
 rows=[]
 for task,model in CASES:
  run=ROOT/'runs/calibration-h7'/task/('pilot1-'+model);record=read(run/'record.json');grade=read(run/'grade.json')
  assert record['ended_at'] and record['snapshot']['writers_frozen'] and record['outcome'] in ('blocked','complete')
  binding=grade['checks']['input_binding'];tag='response-'+binding['record_sha256'][:12];taskdir=H/'pilot'/task
  source,commands=observed_commands(run)
  terms=('pytest','-m restore','-m period_close','recovery-report.json','diagnose_september_close.py','close-source-sha256','protected evidence','git diff --check','sha256sum')
  selected=[c for c in commands if any(term in c['command'] or term in c.get('output','') for term in terms)]
  assert selected
  evidence={'record_sha256':sha(run/'record.json'),'snapshot_sha256':sha(run/'snapshot.tar.gz'),
            'source_log_sha256':sha(source),'selection_policy':'Completed commands relevant to accepted verification/repair claims; full selected command/output preserved without truncation.',
            'closed_command_evidence':selected}
  assert len(json.dumps(evidence).encode())<150000
  epath=H/'pilot_reviews/evidence'/tag/'automated-command-evidence.json';new_json(epath,evidence)
  docs=[]
  def add(kind,path,base):docs.append({'id':kind+'-'+str(path.relative_to(base)).replace('/','-'),'kind':kind,'path':path.relative_to(base).as_posix(),'sha256':sha(path)})
  for p in sorted((taskdir/'workspace').rglob('*')):
   if p.is_file() and not any(x in p.parts for x in ('__pycache__','.pytest_cache')) and p.suffix in ('.md','.py','.json','.jsonl','.ini'):
    add('public_source',p,taskdir/'workspace')
  proof=['AUTHOR_PROOF.md','AUTHOR_PROOF.json'] if 'ops-' in task else ['AUTHOR_PROOF.md','author_only/proof_result.json','author_only/independent_result.json']
  for name in proof:add('author_proof',taskdir/name,taskdir)
  workspace=run/'grading/workspace'
  for name in grade['checks']['files_changed_actual']:
   p=workspace/name
   if p.is_file() and not p.is_symlink() and p.suffix in ('.md','.py','.json','.jsonl','.ini','.txt'):
    add('snapshot_artifact',p,workspace)
  add('closed_command_evidence',epath,H/'pilot_reviews/evidence')
  assert len(docs)<=40
  selection=OUT/tag/'selections.json';new_json(selection,{'task':task,'documents':docs})
  rows.append({'packet_id':tag,'run':str(run.relative_to(ROOT)),'task':task,'accepted_status':record['outcome'],
               'binding':binding,'selections':str(selection.relative_to(ROOT)),'selections_sha256':sha(selection),
               'command_evidence_sha256':sha(epath),'document_count':len(docs)})
 new_json(OUT/'PLAN.json',{'at':datetime.now(timezone.utc).isoformat(),'purpose':'Four fixed historical comparisons: two supported blocked responses across domains, one complete-status caveat with factual error, one unsupported completion. No calibration reruns or historical grade edits.','initial_attempts':4,'max_parallel':2,'review_model':'gpt-6-astra','effort':'max','deadline_seconds':600,'per_input_attempts':1,'evaluator_pin_required':True,'cases':rows})
 print(json.dumps([{'packet_id':x['packet_id'],'document_count':x['document_count']} for x in rows],indent=2))
if __name__=='__main__':main()
