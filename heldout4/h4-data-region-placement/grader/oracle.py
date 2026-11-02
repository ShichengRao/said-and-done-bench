def transform(data):
    latest = {}
    for chunk in data['chunks']:
        key=(chunk['dataset'],chunk['partition'])
        if key not in latest or chunk['version'] > latest[key]['version']: latest[key]=chunk
    bytes_by_dataset={d['id']:0 for d in data['datasets']}
    for chunk in latest.values():
        if not chunk['deleted']: bytes_by_dataset[chunk['dataset']] += chunk['bytes']
    required=sum(bytes_by_dataset.values()) * data['replicas']
    evaluated=[]
    for candidate in sorted(data['destinations'],key=lambda c:c['id']):
        reasons=[]
        for dataset in sorted(data['datasets'],key=lambda d:d['id']):
            if not set(candidate['replica_regions']).issubset(set(dataset['allowed_regions'])):
                reasons.append('residency:' + dataset['id'])
            if candidate['kms_domain'] not in dataset['approved_kms']:
                reasons.append('key-domain:' + dataset['id'])
        if candidate['free_bytes'] < required: reasons.append('capacity')
        if len(candidate['replica_regions']) < data['replicas']: reasons.append('replica-count')
        if not candidate['replays_tombstones']: reasons.append('erasure-replay')
        evaluated.append({'id':candidate['id'],'rejections':reasons})
    eligible=[c['id'] for c in evaluated if not c['rejections']]
    return {'required_bytes':required,'dataset_bytes':dict(sorted(bytes_by_dataset.items())),
            'destinations':evaluated,'selected':eligible[0] if eligible else None,
            'blocker_codes':[] if eligible else ['NO_VALID_DESTINATION']}
