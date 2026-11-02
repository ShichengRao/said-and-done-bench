"""Prototype invoice cache."""
import json,sqlite3

def initialize(path):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS invoices (period TEXT PRIMARY KEY, total INTEGER)')

def close(path,command):
    return {'operation_id':command['operation_id'],'period':command['period'],'as_of':command['as_of'],'invoices':[],'postings':[]}

def snapshot(path):
    return {'clock':0,'periods':{},'invoices':{},'history':[]}
