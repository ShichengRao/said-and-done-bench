"""Dispatch the existing native harness with API-only authentication and a cap.

The optional probe stops before any model invocation and reports only runtime
metadata. No native adapter source or hidden harness prompt is read here.
"""
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.container import Container
from beambench.runner import ProviderError
from api_spending import log_cost


def main():
    cap = float(os.environ['H7_API_SESSION_CAP_USD'])
    assert 0 < cap <= 5
    probe = os.environ.get('H7_API_TRANSPORT_PROBE') == '1'
    run_dir = Path(sys.argv[sys.argv.index('--run-dir')+1]).resolve()
    original_run = Container.run_command
    original_exec = Container.exec_command

    def guarded_run(self):
        if self.image == 'beambench-claude:dev':
            for source, _ in self.mounts:
                source = Path(source).resolve()
                assert not source.is_relative_to(Path.home()/'.claude'), 'Host Claude state is forbidden'
                assert not source.is_relative_to(Path.home()/'.config/beambench'), 'Credential folders must not be mounted'
            forbidden = {'CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_AUTH_TOKEN'}
            self.env_from_host = tuple(x for x in self.env_from_host if x not in forbidden)
            self.env = {k:v for k,v in self.env.items() if k not in forbidden}
        return original_run(self)

    def guarded_exec(self, command):
        if self.image == 'beambench-claude:dev':
            command = list(command)
            if probe:
                print(json.dumps({'probe':'native_command','executable':command[0],
                    'flags':[part for part in command if part.startswith('--')],
                    'container_mounts':[destination for _,destination in self.mounts],
                    'host_env_names':list(self.env_from_host),
                    'model_called':False}),flush=True)
                raise SystemExit('H7 deliberate transport probe: model not invoked')
            assert Path(command[0]).name == 'claude', 'Unexpected native executable'
            assert '-p' in command or '--print' in command, 'Spending cap requires print mode'
            assert '--max-budget-usd' not in command
            spent = log_cost(run_dir/'claude.jsonl')['cost_usd']
            remaining = max(0, cap-spent)
            if remaining <= 0:
                raise ProviderError('H7 API session budget exhausted; not a task-difficulty failure')
            command += ['--max-budget-usd',str(remaining)]
        return original_exec(self, command)

    Container.run_command = guarded_run
    Container.exec_command = guarded_exec
    sys.argv = ['beambench', *sys.argv[1:]]
    runpy.run_module('beambench', run_name='__main__')


if __name__ == '__main__': main()
