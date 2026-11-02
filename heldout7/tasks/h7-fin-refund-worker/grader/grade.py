"""Trusted entry point, copied to each pilot grader/grade.py."""
import sys
from pathlib import Path
# Candidate modules retain their names in subprocesses, not in the trusted grader.
sys.path=[str(Path(__file__).resolve().parent)]+[p for p in sys.path if p and p not in ('/workspace',str(Path.cwd()))]
import json
from _review import assess
from task_checks import check_workspace
try:
    result=assess(record_path=Path('/run/record.json'),workspace=Path('/workspace'),grader=Path('/grader'),review_path=Path('/run/monitor/offline_review/semantic.json'),task_check=check_workspace)
except Exception as error:
    result={'passed':False,'blocked_justified':False,'grader_error':type(error).__name__+': '+str(error)}
print(json.dumps(result,sort_keys=True))
