import copy,itertools,json,sqlite3
from contextlib import contextmanager
GREEDY=False
KEEP_SELECTED_HOLDS=False
EARLY_RELEASE=False
REPLAY_AFTER_CLOCK=True

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
@contextmanager
def tx(path):
 db=sqlite3.connect(path,timeout=30)
 try:
  db.execute('BEGIN IMMEDIATE');db.execute('CREATE TABLE IF NOT EXISTS store(id INTEGER PRIMARY KEY,value TEXT)');yield db;db.commit()
 except Exception:db.rollback();raise
 finally:db.close()
def save(db,s):db.execute('INSERT OR REPLACE INTO store VALUES(1,?)',(canonical(s),))
def load(db):
 row=db.execute('SELECT value FROM store WHERE id=1').fetchone()
 if row is None:raise ValueError('uninitialized')
 return json.loads(row[0])
def stock_key(w,i):return w+':'+i
def held(s,excluded=()):
 sums={k:0 for k in s['stock']}
 for bid,b in s['baskets'].items():
  if b['status']=='held' and bid not in excluded:
   for row in b['ingredients']:sums[stock_key(row['warehouse'],row['ingredient'])]+=row['quantity']
 return sums
def view(s):
 h=held(s);rows=[]
 for key,value in sorted(s['stock'].items()):
  w,i=key.split(':');rows.append(dict(warehouse=w,ingredient=i,on_hand=value,held=h[key],available=value-h[key]))
 return dict(clock=s['clock'],stock=rows,baskets=[copy.deepcopy(s['baskets'][k]) for k in sorted(s['baskets'])],history=copy.deepcopy(s['history']))
def initialize(path,catalog):
 normalized=copy.deepcopy(catalog);normalized['stock']=sorted(normalized['stock'],key=lambda r:(r['warehouse'],r['ingredient']))
 with tx(path) as db:
  row=db.execute('SELECT value FROM store WHERE id=1').fetchone()
  if row:
   s=json.loads(row[0])
   if s['catalog']!=normalized:raise ValueError('different catalog')
  else:
   s=dict(catalog=normalized,clock=0,stock={stock_key(r['warehouse'],r['ingredient']):r['quantity'] for r in normalized['stock']},baskets={},requests={},history=[]);save(db,s)
  return view(s)
def snapshot(path):
 with tx(path) as db:return view(load(db))
def validate_request(s,request):
 if set(request['warehouses'])-set(s['catalog']['warehouses']) or not request['warehouses'] or len(set(request['warehouses']))!=len(request['warehouses']):raise ValueError('warehouse scope')
 if not request['needs'] or set(request['needs'])-set(s['catalog']['recipes']):raise ValueError('unknown product')
def optimize(s,entries,excluded):
 h=held(s,() if KEEP_SELECTED_HOLDS else excluded);available={k:v-h[k] for k,v in s['stock'].items()};slots=[]
 for e in sorted(entries,key=lambda x:x['basket']):
  validate_request(s,e['request'])
  for product,n in sorted(e['request']['needs'].items()):
   for ordinal in range(n):slots.append((e['basket'],product,ordinal,e['request']['warehouses']))
 best=None;assignment=[];consumed={k:0 for k in available};opened=set()
 def recurse(index,cost):
  nonlocal best
  if best is not None and cost>best[0]:return
  if index==len(slots):
   key=(cost,tuple((r['basket'],r['product'],r['ordinal'],r['recipe'],r['warehouse']) for r in assignment))
   if best is None or key<best[:2]:best=(cost,key[1],copy.deepcopy(assignment))
   return
  bid,product,ordinal,warehouses=slots[index]
  options=[]
  for recipe,desc in sorted(s['catalog']['recipes'][product].items()):
   for wh in sorted(warehouses):
    if any(consumed[stock_key(wh,i)]+q>available[stock_key(wh,i)] for i,q in desc['ingredients'].items()):continue
    w=s['catalog']['warehouses'][wh];extra=desc['cost']+w['unit_fee']+(w['activation_fee'] if (bid,wh) not in opened else 0);options.append((extra,recipe,wh,desc))
  for extra,recipe,wh,desc in (sorted(options)[:1] if GREEDY else options):
   isnew=(bid,wh) not in opened;opened.add((bid,wh));assignment.append(dict(basket=bid,product=product,ordinal=ordinal,recipe=recipe,warehouse=wh))
   for i,q in desc['ingredients'].items():consumed[stock_key(wh,i)]+=q
   recurse(index+1,cost+extra)
   for i,q in desc['ingredients'].items():consumed[stock_key(wh,i)]-=q
   assignment.pop()
   if isnew:opened.remove((bid,wh))
 recurse(0,0)
 if best is None:return None
 plans={}
 for e in entries:
  bid=e['basket'];units=[{k:v for k,v in row.items() if k!='basket'} for row in best[2] if row['basket']==bid];ingredients={};cost=0;warehouses=set()
  for row in units:
   recipe=s['catalog']['recipes'][row['product']][row['recipe']];w=s['catalog']['warehouses'][row['warehouse']];cost+=recipe['cost']+w['unit_fee'];warehouses.add(row['warehouse'])
   for i,q in recipe['ingredients'].items():key=(row['warehouse'],i);ingredients[key]=ingredients.get(key,0)+q
  cost+=sum(s['catalog']['warehouses'][w]['activation_fee'] for w in warehouses)
  plans[bid]=dict(units=units,ingredients=[dict(warehouse=w,ingredient=i,quantity=q) for (w,i),q in sorted(ingredients.items())],cost=cost)
 return plans
def apply(path,command):
 with tx(path) as db:
  s=load(db);q=copy.deepcopy(command);op=q['operation_id'];payload=canonical(q)
  if REPLAY_AFTER_CLOCK and q['at']<s['clock']:raise ValueError('time rollback')
  if op in s['requests']:
   old=s['requests'][op]
   if old['payload']!=payload:raise ValueError('operation conflict')
   return copy.deepcopy(old['response'])
  if q['at']<s['clock']:raise ValueError('time rollback')
  for b in s['baskets'].values():
   if b['status']=='held' and b['expires']<=q['at']:b['status']='expired';b['version']+=1
  kind=q['kind'];selected=[]
  if kind in ('reserve','exchange'):
   entries=[dict(basket=q['basket'],until=q['until'],request=q['request'])] if kind=='reserve' else q['entries']
   if len({e['basket'] for e in entries})!=len(entries) or not entries:raise ValueError('duplicate or empty exchange')
   for e in entries:
    if e['until']<=q['at']:raise ValueError('expiry')
    validate_request(s,e['request']);b=s['baskets'].get(e['basket'])
    if kind=='reserve' and b is not None:raise ValueError('basket exists')
    if kind=='exchange' and (b is None or b['status']!='held' or b['version']!=e['expected_version']):raise ValueError('stale/terminal basket')
   excluded=[e['basket'] for e in entries] if kind=='exchange' else []
   if EARLY_RELEASE:
    for k in excluded:s['baskets'][k]['status']='released'
   plans=optimize(s,entries,excluded)
   if plans is None:result='unavailable';selected=[s['baskets'][e['basket']] for e in entries] if kind=='exchange' else []
   else:
    for e in entries:
     old=s['baskets'].get(e['basket']);b=dict(id=e['basket'],version=1 if old is None else old['version']+1,status='held',expires=e['until'],request=copy.deepcopy(e['request']),**plans[e['basket']]);s['baskets'][e['basket']]=b;selected.append(b)
    result='reserved' if kind=='reserve' else 'exchanged'
  elif kind in ('commit','release'):
   b=s['baskets'].get(q['basket'])
   if b is None or b['status']!='held' or b['version']!=q['expected_version']:raise ValueError('stale/terminal basket')
   if kind=='commit':
    for r in b['ingredients']:s['stock'][stock_key(r['warehouse'],r['ingredient'])]-=r['quantity']
   b['status']='committed' if kind=='commit' else 'released';b['version']+=1;selected=[b];result=b['status']
  elif kind=='tick':result='ticked'
  else:raise ValueError('unknown kind')
  s['clock']=q['at'];response=dict(operation_id=op,result=result,baskets=copy.deepcopy(sorted(selected,key=lambda b:b['id'])));s['requests'][op]=dict(payload=payload,response=copy.deepcopy(response));s['history'].append(copy.deepcopy(response));save(db,s);return response
