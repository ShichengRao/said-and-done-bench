"""Document / folder-ACL / membership snapshots and historical visibility."""
import copy


def apply(snapshot, operations):
    """Apply one fragment's operations in order (validation happens per complete epoch)."""
    for op in operations:
        kind = op['kind']
        if kind == 'put_folder':
            snapshot['folders'][op['id']] = {'parent': op['parent'], 'acl': copy.deepcopy(op['acl'])}
        elif kind == 'put_document':
            snapshot['documents'][op['id']] = {k: copy.deepcopy(op[k]) for k in ('folder', 'title', 'acl', 'deleted')}
        elif kind == 'delete_document':
            if op['id'] in snapshot['documents']:
                snapshot['documents'][op['id']]['deleted'] = True
        elif kind == 'set_memberships':
            snapshot['memberships'][op['user']] = list(op['groups'])
        else:
            raise ValueError('unknown operation %r' % kind)


def validate(snapshot):
    folders = snapshot['folders']
    for name in folders:
        seen, node = set(), name
        while node is not None:
            if node in seen or node not in folders:
                raise ValueError('invalid folder graph at %s' % name)
            seen.add(node)
            node = folders[node]['parent']
    for name, document in snapshot['documents'].items():
        if not document['deleted'] and document['folder'] not in folders:
            raise ValueError('document %s is in a missing folder' % name)


def visible(snapshot, user):
    """Documents the user may see in this snapshot: explicit ACL, else nearest ancestor ACL."""
    groups = set(snapshot['memberships'].get(user, []))
    result = []
    for name, document in sorted(snapshot['documents'].items()):
        if document['deleted']:
            continue
        acl, node = document['acl'], document['folder']
        while acl is None and node is not None:
            acl, node = snapshot['folders'][node]['acl'], snapshot['folders'][node]['parent']
        if groups & set(acl or []):
            result.append({'id': name, 'title': document['title'], 'folder': document['folder']})
    return result
