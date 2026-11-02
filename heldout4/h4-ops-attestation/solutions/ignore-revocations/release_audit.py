import json,sys

def audit(spec):
    grants={g['id']:g for g in spec['grants']};tokens={t['id']:t for t in spec['tokens']};requests={r['id']:r for r in spec['requests']}
    def active(g,at):
        return g['start']<=at<g['expires'] and True
    def matches(g,principal,role,request):
        return (g['principal']==principal and g['role']==role
                and g['environment'] in ('*',request['environment'])
                and g['service'] in ('*',request['service']))
    seen=set();rows=[]
    for event in spec['events']:
        if event['id'] in seen: continue
        seen.add(event['id'])
        if event['kind']!='commit' or event['status']!='success': continue
        request=requests[event['request']]
        if request['environment']!='production': continue
        at=event['at'];token=tokens.get(request['token']); reasons=[]
        token_ok=(token is not None and token['principal']==request['principal'] and token['issued_at']<=request['at']<=at<token['expires'] and (token['revoked_at'] is None or at<token['revoked_at']))
        if not token_ok: reasons.append('invalid_token')
        eligible=bool(token_ok and any(gid in grants and matches(grants[gid],request['principal'],'deploy',request) and active(grants[gid],token['issued_at']) and active(grants[gid],at) for gid in token['grant_ids']))
        if not eligible: reasons.append('missing_deploy_grant')
        approved=False
        for a in spec['approvals']:
            if a['request']!=request['id'] or a['artifact']!=request['artifact'] or a['principal']==request['principal']: continue
            if not request['at']<=a['at']<=at<a['expires']: continue
            if any(matches(g,a['principal'],'approve',request) and active(g,a['at']) and active(g,at) for g in grants.values()): approved=True
        if not approved: reasons.append('missing_independent_approval')
        rows.append({'deployment':event['deployment'],'authorized':not reasons,'reasons':reasons})
    rows.sort(key=lambda r:r['deployment'])
    violations=[r['deployment'] for r in rows if not r['authorized']]
    return {'can_attest':not violations,'production_deployments':len(rows),'violations':violations,'deployments':rows}

if __name__=='__main__': print(json.dumps(audit(json.load(open(sys.argv[1]))),sort_keys=True))
