"""Map this round's retained grades to its own source commits or exact archives."""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.tasks import _hash_tree
COMMITS = ['de0bb64', '3f3c358', 'c1b208d', '247861a', '9547fe4']

def collect():
    versions = []
    for rev in COMMITS:
        full = subprocess.check_output(['git', 'rev-parse', rev], cwd=ROOT, text=True).strip()
        data = subprocess.check_output(['git', 'archive', rev, 'heldout4'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            entries = {m.name: archive.extractfile(m).read() for m in archive.getmembers()
                       if m.isfile() and len(m.name.split('/')) > 2 and m.name.split('/')[1].startswith('h4-')}
        for tid in sorted({p.split('/')[1] for p in entries}):
            prefix = 'heldout4/' + tid + '/'
            content = {p[len(prefix):]: b for p, b in entries.items() if p.startswith(prefix)}
            hashes = {}
            for kind in ['task_hash', 'grader_hash']:
                h = hashlib.sha256()
                for rel, b in sorted(content.items()):
                    if '__pycache__' in Path(rel).parts:
                        continue
                    if kind == 'task_hash':
                        if rel.split('/')[0] in ['grader', 'solutions']:
                            continue
                        key = rel
                    else:
                        if not rel.startswith('grader/'):
                            continue
                        key = rel[len('grader/'):]
                    h.update(key.encode() + b'\0' + b + b'\0')
                hashes[kind] = h.hexdigest()
            versions.append({'task': tid, 'source_commit': full, **hashes})
    archives = {}
    archive_root = ROOT / 'heldout4/_history/graders'
    if archive_root.exists():
        for p in sorted(archive_root.iterdir()):
            if not p.is_dir():
                continue
            actual = _hash_tree(p)
            assert actual == p.name, f'Historical archive hash mismatch: {p}'
            archives[actual] = str(p.relative_to(ROOT))
    observed = []
    for p in sorted((ROOT / 'runs/calibration-h4').glob('h4-*/grade*.json')):
        grade = json.loads(p.read_text())
        gh = grade.get('grader_hash')
        if not gh:
            continue
        tid = json.loads((p.parent / 'record.json').read_text())['task']['id']
        observed.append({'run': p.parent.name, 'grade_file': str(p.relative_to(ROOT)), 'grader_hash': gh,
                         'committed_source_versions': [v['source_commit'] for v in versions if v['task'] == tid and v['grader_hash'] == gh],
                         'verified_source_archive': archives.get(gh)})
    missing = [r for r in observed if not r['committed_source_versions'] and not r['verified_source_archive']]
    result = {'scope': 'Only new Blind Round 4 source commits; no main history inspected. Final source manifest separately pins the complete accepted collection.',
              'source_versions': versions, 'verified_source_archives': archives, 'observed_grade_versions': observed,
              'intermediate_grader_sources_unavailable': missing}
    (ROOT / 'heldout4/SOURCE_PROVENANCE.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'historical_grades': len(observed), 'verified_archives': len(archives), 'intermediate_grades_without_source': len(missing)}))

if __name__ == '__main__':
    collect()
