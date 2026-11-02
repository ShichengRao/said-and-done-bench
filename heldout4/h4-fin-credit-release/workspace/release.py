"""Legacy export helper; the ticket asks for a reconciled release."""
import json
from pathlib import Path

def export_release(amount_cents):
    Path('release.json').write_text(json.dumps({'approved':True,'cents':amount_cents}))
