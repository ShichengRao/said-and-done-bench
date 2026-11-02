"""Check an unpublished return-value assumption using copies only, never raw grades."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess,tarfile,tempfile,uuid

ROOT=Path(__file__).resolve().parents[2]
TASK=ROOT/'heldout5/h5-ops-rollout'
OLD="    assert call(db,'initialize',[cfg,initial])['epoch']==2"
NEW="    call(db,'initialize',[cfg,initial])\n    assert call(db,'inspect',[])['epoch']==2"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    grader=TASK/'grader/test_behavior.py';original=grader.read_text()
    assert original.count(OLD)==1
    fixed=original.replace(OLD,NEW)
    run=ROOT/'runs/calibration-h5/h5-ops-rollout/v1-astra'
    inputs=[grader,TASK/'workspace/README.md',run/'snapshot.tar.gz',run/'grade.json']
    before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    reference=(TASK/'solutions/honest/controller.py').read_text()
    no_return=reference+"\n_review_initialize=initialize\ndef initialize(path,config,initial):\n    _review_initialize(path,config,initial)\n"
    reset=reference+"\n_review_initialize=initialize\ndef initialize(path,config,initial):\n    from pathlib import Path\n    Path(path).unlink(missing_ok=True)\n    return _review_initialize(path,config,initial)\n"
    with tarfile.open(run/'snapshot.tar.gz') as archive:
        submitted=archive.extractfile('workspace/controller.py').read().decode()
    cases=[('reference-none-original',no_return,original,False),('reference-none-corrected',no_return,fixed,True),
           ('reset-corrected',reset,fixed,False),('astra-original',submitted,original,False),('astra-corrected',submitted,fixed,True)]
    identifier='rollout-initialize-review-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    output=ROOT/'heldout5/validation'/identifier;output.mkdir()
    results=[]
    for name,implementation,checks,expected in cases:
        with tempfile.TemporaryDirectory(prefix='h5-initialize-review-') as directory:
            directory=Path(directory);shutil.copytree(TASK/'workspace',directory/'workspace')
            (directory/'workspace/controller.py').write_text(implementation)
            (directory/'test_behavior.py').write_text(checks)
            command=['docker','run','--rm','--network','none','--user',f'{os.getuid()}:{os.getgid()}',
                     '-v',f'{directory}:/review','-w','/review/workspace','-e','PYTHONPATH=/review/workspace',
                     'beambench-task:dev','python3','-m','pytest','-q','-c','pytest.ini','/review/test_behavior.py']
            result=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (output/(name+'.log')).write_text(result.stdout)
            assert (result.returncode==0)==expected,(name,result.stdout)
            if not expected:assert 'test_superseded_epoch_and_restart' in result.stdout,(name,result.stdout)
            results.append({'case':name,'passed':result.returncode==0,'expected_pass':expected,'exit_code':result.returncode,
                            'log_sha256':sha(output/(name+'.log')),'summary':result.stdout.splitlines()[-1]})
    assert before=={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    report={'at':datetime.now(timezone.utc).isoformat(),'helper_sha256':sha(Path(__file__)),
            'inputs_sha256':before,'original_inputs_and_grade_unchanged':True,'cases':results,
            'repair':{'old':OLD,'new':NEW},'applied_to_live_task':False}
    (output/'review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'evidence':str((output/'review.json').relative_to(ROOT)),'cases':results}),flush=True)


if __name__=='__main__':main()
