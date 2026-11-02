import vault as v
def test_scalar_roundtrip():
 import hashlib,json
 body={'coefficients':[1],'value':7}
 row={**body,'id':'f','revision':1,'tenant':'t','generation':'g','live':True,'sha256':hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
 d={'width':1,'tenant':'t','generation':'g','fault_budget':0,'fragments':[row],'anchors':[],'owner_queries':[]}
 assert v.audit(d)['unique_symbols']==[7]

def test_empty_one_symbol_has_256_candidates():
 d={'width':1,'tenant':'t','generation':'g','fault_budget':0,'fragments':[],'anchors':[],'owner_queries':[]}
 assert v.audit(d)['candidate_count']==256
