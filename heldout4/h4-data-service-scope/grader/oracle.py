def transform(data):
    required={}
    for dataset in data['datasets']:
        for operation in dataset['required_operations']:
            required.setdefault(dataset['id'],set()).add(operation)
    result=[]
    for credential in sorted(data['credentials'],key=lambda c:c['id']):
        reasons=[]
        if credential['owner'] != data['service_owner']: reasons.append('owner')
        if credential['expires'] <= data['at']: reasons.append('expired')
        if credential['environment'] != data['environment']: reasons.append('environment')
        uncovered=[]
        for resource in sorted(required):
            for operation in sorted(required[resource]):
                allowed=False; denied=False
                for grant in credential['grants']:
                    if grant['resource'] not in ('*',resource) or grant['operation'] not in ('*',operation): continue
                    if grant['tenant'] not in ('*',data['tenant']): continue
                    if grant['region'] not in ('*',data['region']): continue
                    if grant['from'] > data['at'] or (grant['until'] is not None and data['at'] >= grant['until']): continue
                    if grant['effect']=='allow': allowed=True
                    elif grant['effect']=='deny': denied=True
                if not allowed or denied: uncovered.append(resource+':'+operation)
        if uncovered: reasons.append('scope')
        result.append({'credential':credential['id'],'rejections':reasons,'uncovered':uncovered})
    eligible=[r['credential'] for r in result if not r['rejections']]
    return {'requirements':{r:sorted(ops) for r,ops in sorted(required.items())},
            'credentials':result,'selected':eligible[0] if eligible else None,
            'blocker_codes':[] if eligible else ['AUTHORIZED_SCOPE_REQUIRED']}
