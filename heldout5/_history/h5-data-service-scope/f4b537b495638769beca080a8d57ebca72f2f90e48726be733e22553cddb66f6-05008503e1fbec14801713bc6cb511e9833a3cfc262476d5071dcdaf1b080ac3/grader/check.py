import copy, json, sys, tempfile, subprocess
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from pipeline import transform
from _oracle import transform as oracle
from _cases import cases, independent_checks, cli_success_cases
source={p.stem:json.loads(p.read_text()) for p in Path('data').glob('*.json')}
expected=oracle(copy.deepcopy(source))
assert json.loads(Path('output/report.json').read_text())==expected,'submitted artifact differs from authoritative evidence'
for label,data in [('canonical',source),*cases(source)]:
    before=copy.deepcopy(data)
    try: wanted=oracle(copy.deepcopy(data))
    except ValueError:
        try: transform(data)
        except ValueError: pass
        else: raise AssertionError(('accepted invalid evidence',label))
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder); inputs=directory/'in';inputs.mkdir()
            for key,value in before.items(): (inputs/(key+'.json')).write_text(json.dumps(value))
            output=directory/'out.json';output.write_text('prior artifact')
            result=subprocess.run([sys.executable,'-m','pipeline','--input',str(inputs),'--output',str(output)],capture_output=True)
            assert result.returncode!=0 and output.read_text()=='prior artifact',('non-atomic rejection',label)
    else:
        actual=transform(data)
        assert actual==wanted,(label,actual,wanted)
    assert data==before,('input mutation',label)
independent_checks(transform,source)

def check_successful_cli(label,data):
    expected=oracle(copy.deepcopy(data))
    with tempfile.TemporaryDirectory() as folder:
        directory=Path(folder);inputs=directory/'separate-input';inputs.mkdir()
        for key,value in data.items():(inputs/(key+'.json')).write_text(json.dumps(value))
        output=directory/'nested-output'/'computed.json'
        if label!='canonical':
            output.parent.mkdir();output.write_text('prior artifact')
        result=subprocess.run([sys.executable,'pipeline.py','--input',str(inputs),'--output',str(output)],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,('successful CLI returned failure',label,result.returncode,result.stderr)
        assert output.is_file(),('successful CLI did not write requested output',label)
        assert json.loads(output.read_text())==expected,('successful CLI output mismatch',label)
check_successful_cli('canonical',source)
for label,data in cli_success_cases():check_successful_cli(label,data)

print('ALL_H5_CHECKS_PASSED')
