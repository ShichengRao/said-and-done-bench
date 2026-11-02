import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'heldout7/_shared'))
spec=importlib.util.spec_from_file_location('h7_bounded',ROOT/'heldout7/_shared/run_api_cache_bounded.py')
bounded=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bounded)


def test_native_api_auth_context_and_cumulative_cap(monkeypatch,tmp_path):
    calls=[]
    class FakeContainer:
        image='beambench-claude:dev'
        mounts=[]
        env_from_host=('ANTHROPIC_API_KEY','CLAUDE_CODE_OAUTH_TOKEN','CLAUDE_CODE_MAX_CONTEXT_TOKENS')
        env={'DISABLE_COMPACT':'0','CLAUDE_CODE_MAX_CONTEXT_TOKENS':'1000000','OTHER':'retained'}
        def run_command(self):calls.append(('env',self.env_from_host,dict(self.env)))
        def exec_command(self,command):calls.append(('command',command))
    monkeypatch.setattr(bounded,'Container',FakeContainer)
    monkeypatch.setenv('H7_API_SESSION_CAP_USD','2')
    monkeypatch.delenv('H7_API_TRANSPORT_PROBE',raising=False)
    monkeypatch.setattr(sys,'argv',['wrapper','run','--run-dir',str(tmp_path)])
    (tmp_path/'claude.jsonl').write_text(json.dumps({'turn':1,'event':{'type':'result','total_cost_usd':.6}})+'\n')
    def dispatch(*args,**kwargs):
        container=FakeContainer();container.run_command()
        container.exec_command(['claude','--print','--model','claude-opus-5-5'])
    monkeypatch.setattr(bounded.runpy,'run_module',dispatch)
    bounded.main()
    assert calls[0]==('env',('ANTHROPIC_API_KEY',),{
        'OTHER':'retained','CLAUDE_CODE_DISABLE_1M_CONTEXT':'1','DISABLE_COMPACT':'1',
        'CLAUDE_CODE_MAX_CONTEXT_TOKENS':'200000','CLAUDE_CODE_MAX_OUTPUT_TOKENS':'32000','FORCE_PROMPT_CACHING_5M':'1'})
    assert calls[1][1][-2:]==['--max-budget-usd','1.4']
