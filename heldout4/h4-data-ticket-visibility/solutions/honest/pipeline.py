def transform(data):
    documents = {(d['tenant'], d['id']): d for d in data['documents']}
    for tenant in {q['tenant'] for q in data['queries']}:
        keys = [(d['tenant'], d['id']) for d in data['documents'] if d['tenant'] == tenant]
        if len(set(keys)) != len(keys): raise ValueError('duplicate document')
    answers = []
    for query in data['queries']:
        tenant, user, now = query['tenant'], query['user'], query['at']
        principals = {'user:' + user, 'everyone'}
        changed = True
        while changed:
            changed = False
            for group in data['groups']:
                token = 'group:' + group['id']
                if group['tenant'] == tenant and any(p in principals for p in group['members']) and token not in principals:
                    principals.add(token); changed = True
        visible = []
        for key, doc in sorted(documents.items()):
            if key[0] != tenant: continue
            chain, seen, current = [], set(), doc
            while current is not None:
                token = (current['tenant'], current['id'])
                if token in seen: raise ValueError('parent cycle')
                seen.add(token); chain.append(current)
                parent = current['parent']
                if parent is None: break
                if (tenant, parent) not in documents: raise ValueError('missing parent')
                current = documents[(tenant, parent)]
            if any(d['deleted'] for d in chain): continue
            grants, denies = False, False
            for item in chain:
                for rule in item['acl']:
                    if rule['principal'] in principals and rule['from'] <= now and (rule['until'] is None or now < rule['until']):
                        if rule['effect'] == 'deny': denies = True
                        elif rule['effect'] == 'allow': grants = True
                        else: raise ValueError('unknown ACL effect')
                if item['break_inheritance']: break
            terms = query['text'].casefold().split()
            haystack = (doc['title'] + ' ' + doc['body']).casefold()
            if grants and not denies and all(term in haystack for term in terms):
                visible.append({'id': doc['id'], 'title': doc['title']})
        answers.append({'query_id': query['id'], 'documents': visible})
    return {'results': answers}

import argparse
import json
import os
import tempfile
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/input.json')
    parser.add_argument('--output', default='output/report.json')
    args = parser.parse_args()
    result = transform(json.loads(Path(args.input).read_text()))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

if __name__ == '__main__':
    main()
