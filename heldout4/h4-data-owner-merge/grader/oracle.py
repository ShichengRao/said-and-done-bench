def transform(data):
    contacts={(c['tenant'],c['id']):c for c in data['contacts']}
    edges={}
    for event in data['authority_events']:
        if event['at'] > data['as_of']: continue
        key=(event['tenant'],event['ticket'],event['contact'])
        order=(event['at'],event['sequence'])
        if key not in edges or order > edges[key][0]: edges[key]=(order,event['approved'])
    resolved=[]; unresolved=[]
    for ticket in sorted(data['tickets'],key=lambda t:(t['tenant'],t['id'])):
        tenant=ticket['tenant']
        authoritative=sorted(cid for (ten,ticket_id,cid),(_,approved) in edges.items()
                             if ten==tenant and ticket_id==ticket['id'] and approved and (ten,cid) in contacts)
        candidates=sorted(c['id'] for c in data['contacts'] if c['tenant']==tenant
                          and c['email'].strip().casefold()==ticket['reply_email'].strip().casefold())
        if len(authoritative)==1:
            resolved.append({'tenant':tenant,'ticket':ticket['id'],'contact':authoritative[0]})
        else:
            unresolved.append({'tenant':tenant,'ticket':ticket['id'],
                               'authoritative_contacts':authoritative,'email_candidates':candidates,
                               'reason':'missing-authority' if not authoritative else 'conflicting-authority'})
    return {'resolved':resolved,'unresolved':unresolved,
            'blocker_codes':['OWNER_AUTHORITY_REQUIRED'] if unresolved else []}
