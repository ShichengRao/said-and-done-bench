import hashlib,json,fnmatch

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()

def valid_signature(manifest, signature, key):
    try:
        n=int(key['n'],16); e=key['e']; raw=bytes.fromhex(signature); size=(n.bit_length()+7)//8
        if len(raw)!=size or int.from_bytes(raw,'big')>=n: return False
        decoded=pow(int.from_bytes(raw,'big'),e,n).to_bytes(size,'big')
        tail=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(canonical(manifest)).digest()
        return decoded==b'\x00\x01'+b'\xff'*(size-len(tail)-3)+b'\x00'+tail
    except (ValueError,KeyError,OverflowError,TypeError): return False

def closure(bundle):
    policy=bundle['policy']; now=policy['at']; index={}
    for envelope in bundle['releases']:
        m=envelope['manifest']; digest=hashlib.sha256(canonical(m)).hexdigest()
        index[digest]=envelope
    result={}; visiting=set()
    def visit(ref):
        digest=ref['sha256']
        if digest in visiting: raise ValueError('dependency cycle')
        if digest not in index: raise ValueError('missing manifest')
        env=index[digest]; m=env['manifest']; name=m['package']
        if name!=ref['package'] or m['version']!=ref['version']: raise ValueError('identity mismatch')
        if name in result:
            if result[name]['sha256']!=digest: raise ValueError('conflicting dependency')
            return
        if not m['not_before']<=now<m['expires']: raise ValueError('expired release')
        if m['build']<policy['minimum_build'].get(name,0): raise ValueError('rollback')
        role=policy['roles'].get(m['role'])
        if not role or not any(fnmatch.fnmatchcase(name,p) for p in role['packages']): raise ValueError('delegation scope')
        signed=set()
        for sig in env['signatures']:
            kid=sig['keyid']; key=policy['keys'].get(kid)
            if kid not in role['keyids'] or not key: continue
            if not key['not_before']<=now<key['expires']: continue
            if False: continue
            if valid_signature(m,sig['sig'],key): signed.add(kid)
        if len(signed)<role['threshold']: raise ValueError('signature threshold')
        artifact=bundle['artifacts'].get(m['artifact'])
        if artifact is None or hashlib.sha256(artifact.encode()).hexdigest()!=m['artifact_sha256']: raise ValueError('artifact integrity')
        visiting.add(digest)
        for dep in m['dependencies']: visit(dep)
        visiting.remove(digest)
        result[name]=dict(package=name,version=m['version'],sha256=digest)
    for ref in bundle['requested']: visit(ref)
    return [result[name] for name in sorted(result)]
