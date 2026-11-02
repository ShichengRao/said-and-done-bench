"""Prototype: loses previous deliveries and does not reconstruct intervals."""
import json,sqlite3

def initialize(path,config):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS state (body TEXT)')
        if not db.execute('SELECT 1 FROM state').fetchone():
            db.execute('INSERT INTO state VALUES (?)',(json.dumps(config),))

def close(path,command):
    return {'operation_id':command['operation_id'],'as_of':command['as_of'],'targets':[],'postings':[]}

def snapshot(path):
    return {'clock':0,'config':{},'delivery_count':0,'targets':[],'history':[]}
