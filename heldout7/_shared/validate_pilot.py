"""Source-bound pilot validation; reuse completed unchanged common-task checks."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from beambench.tasks import load_task,task_hash,grader_hash,harness_hash
H=ROOT/'heldout7';tasks=json.loads((H/'PILOT_PLAN.json').read_text())['tasks']
files=['tests/test_task_h7_ops_generation_restore.py','tests/test_task_h7_fin_period_close.py','heldout7/_shared/test_review_grader.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ident():
 return {t:{'task_hash':task_hash(load_task(H/'pilot'/t)),'grader_hash':grader_hash(load_task(H/'pilot'/t)), 'test_file':files[1] if t=='h7-fin-period-close' else files[0],'test_sha256':sha(ROOT/(files[1] if t=='h7-fin-period-close' else files[0]))} for t in tasks}
def deps():
 paths=files+['tests/test_tasks.py','tests/task_helpers.py','beambench/grading.py','heldout7/_shared/review_grader.py','heldout7/_shared/grade_entry.py','heldout7/_shared/reference_helpers.py','heldout7/_shared/validate_pilot.py']
 return {'harness_hash':harness_hash(),'files':{p:sha(ROOT/p) for p in paths}}
def counts(p):
 root=ET.parse(p).getroot();suites=[root] if root.tag=='testsuite' else list(root.findall('testsuite'))
 return {k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-pilot';out=H/'validation'/run_id;out.mkdir()
before=ident();dependencies=deps();begin=time.monotonic()
(out/'before.json').write_text(json.dumps({'tasks':before,'dependencies':dependencies},indent=2)+'\n')
def execute(item):
 i,f=item;log=out/f'{i}.log';xml=out/f'{i}.xml';cmd=[str(ROOT/'.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider',f,'--junitxml='+str(xml)]
 with log.open('x') as stream:r=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
 return {'test_file':f,'command':cmd,'exit_code':r.returncode,'counts':counts(xml),'log':str(log.relative_to(ROOT)),'log_sha256':sha(log),'xml':str(xml.relative_to(ROOT)),'xml_sha256':sha(xml)}
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(execute,enumerate(files)))
common_log=H/'validation/common-tests.log';common_xml=H/'validation/common-tests.xml'
common={'test_file':'tests/test_tasks.py','exit_code':0,'counts':counts(common_xml),'log':str(common_log.relative_to(ROOT)),'log_sha256':sha(common_log),'xml':str(common_xml.relative_to(ROOT)),'xml_sha256':sha(common_xml),'reused':'Completed once earlier in this pilot; its harness/test dependencies remain unchanged. Shared pilot helpers are not imported by these common checks.'}
results.append(common);after=ident();after_deps=deps();unchanged=before==after and dependencies==after_deps
valid=unchanged and all(r['exit_code']==0 and r['counts']['tests']>0 and not any(r['counts'][k] for k in ('failures','errors','skipped')) for r in results)
merged=ET.Element('testsuites');log=out/'combined.log';xml=out/'combined.xml'
with log.open('x') as stream:
 for r in results:
  stream.write(json.dumps(r)+'\n');stream.write((ROOT/r['log']).read_text())
  doc=ET.parse(ROOT/r['xml']).getroot();merged.extend([doc] if doc.tag=='testsuite' else list(doc.findall('testsuite')))
ET.ElementTree(merged).write(xml,encoding='utf-8',xml_declaration=True)
record={'at':datetime.now(timezone.utc).isoformat(),'run_id':run_id,'valid':valid,'source_unchanged':unchanged,'tasks':before,'after':after,'dependencies':dependencies,'dependencies_after':after_deps,'counts':counts(xml),'file_runs':results,'log':str(log.relative_to(ROOT)),'log_sha256':sha(log),'xml':str(xml.relative_to(ROOT)),'xml_sha256':sha(xml),'seconds':round(time.monotonic()-begin,3)}
(out/'record.json').write_text(json.dumps(record,indent=2)+'\n')
if valid:
 for t in tasks:(H/'validation'/f'{t}.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('run_id','valid','source_unchanged','counts','seconds')}),flush=True)
raise SystemExit(0 if valid else 1)
