def transform(data):
    crm = {(c['tenant'],c['id']):c for c in data['crm']}
    bridges = {(b['tenant'],b['token']):b['customer_id'] for b in data['approved_bridge']}
    if len(bridges) != len(data['approved_bridge']): raise ValueError('duplicate bridge')
    consent = {}
    for row in data['consent']:
        if row['at'] > data['as_of']: continue
        key = (row['tenant'],row['customer_id'],row['purpose'])
        order = (row['at'],row['sequence'])
        if key not in consent or order > consent[key][0]: consent[key] = (order,row['allowed'])
    latest = {}
    revisions = {}
    for ticket in data['tickets']:
        revision_key=(ticket['tenant'],ticket['id'],ticket['revision'])
        if revision_key in revisions and revisions[revision_key] != ticket: raise ValueError('conflicting revision')
        revisions[revision_key] = ticket
        key=(ticket['tenant'],ticket['id'])
        if key not in latest or ticket['revision'] > latest[key]['revision']: latest[key]=ticket
        elif ticket['revision'] == latest[key]['revision'] and ticket != latest[key]: raise ValueError('conflicting revision')
    groups = {}
    for ticket in latest.values():
        if ticket['deleted'] or ticket['internal']: continue
        tenant=ticket['tenant']; token=(tenant,ticket['token'])
        if token not in bridges: raise ValueError('unmapped approved token')
        cid=bridges[token]
        if (tenant,cid) not in crm: raise ValueError('unknown approved customer')
        customer=crm[(tenant,cid)]
        if not consent.get((tenant,cid,data['purpose']), (None,False))[1]: continue
        group=(customer['region'],customer['tier'])
        bucket=groups.setdefault(group, {'members':set(),'topics':{}})
        bucket['members'].add((tenant,cid))
        bucket['topics'][ticket['topic']]=bucket['topics'].get(ticket['topic'],0)+1
    rows=[]; suppressed=0
    for group, bucket in sorted(groups.items()):
        if len(bucket['members']) < data['minimum_members']:
            suppressed += 1; continue
        rows.append({'region':group[0],'tier':group[1],'member_count':len(bucket['members']),
                     'topics':dict(sorted(bucket['topics'].items()))})
    return {'groups':rows,'suppressed_groups':suppressed}
