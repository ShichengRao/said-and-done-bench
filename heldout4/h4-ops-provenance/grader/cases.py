import copy,hashlib,json,random
KEYS={'k0': (138529796601077567475817843724755972207516097604856656720544877409675410881994518223560924733927188324915083867367470348994750265982819902084581801360926194408321747366093685747243349022936085831579093646060688383008957577131878258441651903149738064172434487003040079614899434256346794474589034974947520670321, 65537, 60107012773673523486616052064591922512365957420872238437911624487259563053548318052476897870423631341185671069052007062331426805674465824430126006736641844984782803774272771826819793445486224447842048983370781631041659491039061784003308128570261003136444433966401331609598059416009953957756044374833039660305), 'k1': (153554651234071671039051407067772094177157440067790625078226219278924776009910119203056511844418489438597221974622441946524113972496969191723447305454105544345768234135008179224716315664531023392290317958783219701273951228688096227790979589733562584447639066238694265550903916434585278636257664343199057498253, 65537, 8448938345515700226846199458113526276802870575162930772419911602908322661881622439938077448021317315647368394044410419444984588626639469389119901482635831721633533347263562477260733526813903716335477890011301177519139824011032940632978839286734513892976769778070085743234606090873451813753140473921190689577), 'k2': (114592958805004580852956408782538279168156758182506525782809622293570247105511991411514698998938381990549502074016951043662944723957534887807690003849181705683296778495804620708330088334643572727415358344941078089176503184605788915967357532500693552109646852054089235833928813823435959469040534389404448303541, 65537, 34132919554335633654737965665867063607452096929684146204529145929670030574281697122910393200150695863977857240747744042652918869590842402686938928622608231339200827754686109239116881826375754159111611668269992965217601462670723595496823600918160633707830844896080922622785580036832501774691955132359418466669)}
def canon(obj): return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def digest(obj): return hashlib.sha256(canon(obj)).hexdigest()
def sign(manifest,kid):
    n,e,d=KEYS[kid]; size=(n.bit_length()+7)//8
    tail=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(canon(manifest)).digest()
    block=b'\x00\x01'+b'\xff'*(size-len(tail)-3)+b'\x00'+tail
    return {'keyid':kid,'sig':pow(int.from_bytes(block,'big'),d,n).to_bytes(size,'big').hex()}
def make(seed=0,kind='valid'):
    artifacts={}; releases=[]; policy={'at':100,'keys':{kid:{'n':hex(n)[2:],'e':e,'not_before':0,'expires':200,'revoked_at':None} for kid,(n,e,d) in KEYS.items()},'roles':{'platform':{'packages':['orion-*'],'keyids':['k0','k1'],'threshold':2}},'minimum_build':{'orion-api':4}}
    def add(name,dependencies=[],version='1.0',role='platform',build=4,expires=200):
        artifact=name+'-'+version; artifacts[artifact]='payload-'+artifact+'-'+str(seed)
        m=dict(package=name,version=version,build=build,role=role,not_before=50,expires=expires,artifact=artifact,artifact_sha256=hashlib.sha256(artifacts[artifact].encode()).hexdigest(),dependencies=dependencies)
        env={'manifest':m,'signatures':[sign(m,'k0'),sign(m,'k1')]}; releases.append(env)
        return dict(package=name,version=version,sha256=digest(m))
    core=add('orion-core'); left=add('orion-left',[core]); right=add('orion-right',[core]); api=add('orion-api',[left,right])
    expected=sorted([core,left,right,api],key=lambda r:r['package'])
    add('unused-untrusted',[],role='unknown',expires=10)
    bundle=dict(policy=policy,artifacts=artifacts,releases=releases,requested=[api])
    if kind=='duplicate-signer': releases[0]['signatures']=[sign(releases[0]['manifest'],'k0')]*2
    elif kind=='revoked': policy['keys']['k1']['revoked_at']=100
    elif kind=='expired-key': policy['keys']['k1']['expires']=100
    elif kind=='bad-signature': releases[0]['signatures'][0]['sig']='00'*128
    elif kind=='truncated-signature': releases[0]['signatures'][0]['sig']='01'
    elif kind=='tampered-artifact': artifacts['orion-core-1.0']+='edited'
    elif kind=='rollback': policy['minimum_build']['orion-core']=5
    elif kind=='role-scope': policy['roles']['platform']['packages']=['orion-a*','orion-l*','orion-r*']
    elif kind=='missing-dependency': releases.pop(0)
    elif kind=='identity': bundle['requested'][0]={**api,'package':'other'}
    elif kind=='conflicting-diamond':
        newer=add('orion-core',version='2.0'); bundle['requested'].append(newer)
    elif kind=='expired-release': policy['at']=200; [k.update(expires=300) for k in policy['keys'].values()]
    random.Random(seed).shuffle(releases)
    return bundle,expected
