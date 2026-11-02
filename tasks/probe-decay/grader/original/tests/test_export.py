import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_export_lists_one_stations_good_readings_in_its_local_month(tmp_path):
    shutil.copy(ROOT / 'data' / 'stations.json', tmp_path / 'stations.json')
    folder = tmp_path / '2027-01'
    folder.mkdir()
    (folder / 'KST-a.csv').write_text(
        '#tidewater-feed v3\n#station: KST\n#units: mm\n#datum: CD\nobserved_at,level,quality\n'
        '2026-12-31 23:00,1000,G\n2027-01-01 00:00,1100,G\n2027-01-01 01:00,,M\n2027-01-01 02:00,1300,G\n')
    (folder / 'KST-b.csv').write_text(
        '#tidewater-feed v3\n#datum: CD\n#units: cm\n#station: KST\nobserved_at,level,quality\n'
        '2027-01-01 02:00,130.0,G\n2027-01-01 03:00,140.0,S\n2027-01-31 23:00,150.0,G\n2027-02-01 00:00,160.0,G\n')
    (folder / 'HWP.csv').write_text('# tidewater feed v2\n# station: HWP\ntime,level_cm\n01/01/2027 00:00,300.0\n')
    result = subprocess.run([sys.executable, '-m', 'tidewater', 'export', str(folder), '--station', 'KST'],
                            cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        'utc,local,level_m',
        '2026-12-31T18:30Z,2027-01-01 00:00 IST,1.100',
        '2026-12-31T20:30Z,2027-01-01 02:00 IST,1.300',
        '2027-01-31T17:30Z,2027-01-31 23:00 IST,1.500',
    ]
