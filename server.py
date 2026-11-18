"""SimuTrade Labs. Python 3.12+, zero third-party runtime dependencies.
SQLite on local disk; Firestore REST using Cloud Run service identity in production.
"""
import os, json, time, math, secrets, hashlib, hmac, sqlite3, threading, mimetypes, re
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse, parse_qs, quote
from http.cookies import SimpleCookie

ROOT=Path(__file__).parent
DB=os.getenv('DB_PATH',str(ROOT/'data'/'simutrade.db'))
PROJECT=os.getenv('GOOGLE_CLOUD_PROJECT','')
CLOUD=bool(os.getenv('K_SERVICE'))
if CLOUD and not PROJECT: raise RuntimeError('Cloud Run requires GOOGLE_CLOUD_PROJECT; local SQLite is not durable there')
LOCK=threading.RLock()
class Conflict(Exception): pass
class Store:
 def __init__(self):
  if not PROJECT:
   Path(DB).parent.mkdir(parents=True,exist_ok=True)
   with sqlite3.connect(DB) as c: c.execute('CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL, version INTEGER NOT NULL)')
 def call(self,path,method='GET',data=None):
  token=json.load(urlopen(Request('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',headers={'Metadata-Flavor':'Google'}),timeout=5))['access_token']
  url=f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/records/{path}'
  req=Request(url,data=None if data is None else json.dumps(data).encode(),method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  try:
   with urlopen(req,timeout=15) as r: return json.load(r)
  except HTTPError as e:
   if e.code==404: return None
   if e.code in (409,412): raise Conflict('Changed in another tab. Refresh and try again.')
   raise
 def get(self,key):
  if PROJECT:
   r=self.call(quote(key,safe=''))
   return (json.loads(r['fields']['payload']['stringValue']),r['updateTime']) if r else (None,None)
  with sqlite3.connect(DB) as c: r=c.execute('SELECT value,version FROM records WHERE key=?',(key,)).fetchone()
  return (json.loads(r[0]),r[1]) if r else (None,None)
 def put(self,key,value,version=None):
  if PROJECT:
   pre='currentDocument.exists=false' if version is None else 'currentDocument.updateTime='+quote(version,safe='')
   return self.call(quote(key,safe='')+'?'+pre,'PATCH',{'fields':{'payload':{'stringValue':json.dumps(value)}}})['updateTime']
  with sqlite3.connect(DB) as c:
   if version is None:
    try: c.execute('INSERT INTO records VALUES (?,?,1)',(key,json.dumps(value)))
    except sqlite3.IntegrityError: raise Conflict('Already exists')
    return 1
   cur=c.execute('UPDATE records SET value=?,version=version+1 WHERE key=? AND version=?',(json.dumps(value),key,version))
   if not cur.rowcount: raise Conflict('Changed in another tab. Refresh and try again.')
   return version+1
STORE=Store()

def fresh():
 return {'balance':100000,'initial':100000,'dayStart':100000,'day':time.strftime('%Y-%m-%d',time.gmtime()),'peak':100000,'positions':[],'trades':[], 'journal':[], 'contacts':[], 'assets':[], 'automations':[], 'alerts':[], 'rules':{'dailyLoss':5,'maxLoss':10,'target':8,'risk':0.5,'minDays':5},'profile':'Custom 100K','completedLessons':[]}

def market(symbol='NQ'):
 if symbol not in ('NQ','ES','PLTR','SPY'): raise ValueError('Unsupported symbol')
 key=os.getenv('TWELVE_DATA_API_KEY')
 if key:
  with urlopen('https://api.twelvedata.com/time_series?symbol='+symbol+'&interval=1min&outputsize=64&apikey='+quote(key),timeout=12) as r: d=json.load(r)
  if not d.get('values'): raise ValueError('Market provider unavailable: '+d.get('message','no data'))
  bars=[{'o':float(x['open']),'h':float(x['high']),'l':float(x['low']),'c':float(x['close']),'t':x['datetime']} for x in reversed(d['values'])]
  return {'symbol':symbol,'price':bars[-1]['c'],'bars':bars,'mode':'provider','source':'Twelve Data · provider timestamp','timestamp':bars[-1]['t'],'fetchedAt':int(time.time()),'pointValue':20 if symbol=='NQ' else 50 if symbol=='ES' else 1}
 base={'NQ':21450,'ES':5890,'PLTR':64,'SPY':590}[symbol]; scale={'NQ':8,'ES':2,'PLTR':0.07,'SPY':0.2}[symbol]
 slot=int(time.time()//10); bars=[]
 def price(n): return base+scale*(math.sin(n*.19)*6+math.sin(n*.071)*10+math.sin(n*.83)*2)
 for n in range(slot-63,slot+1):
  o=price(n-1); c=price(n); bars.append({'o':round(o,2),'c':round(c,2),'h':round(max(o,c)+scale*.9,2),'l':round(min(o,c)-scale*.8,2),'t':n*10})
 return {'symbol':symbol,'price':round(price(slot),2),'bars':bars,'mode':'replay','source':'Synthetic practice feed · 10s bars','timestamp':slot*10,'fetchedAt':int(time.time()),'pointValue':20 if symbol=='NQ' else 50 if symbol=='ES' else 1}

def num(x,lo,hi):
 n=float(x)
 if not math.isfinite(n) or not lo<=n<=hi: raise ValueError('Number outside allowed range')
 return n

def coach(s):
 trades=s['trades']; losses=[t for t in trades[:3] if t['pnl']<0]
 if len(losses)>=2: return {'title':'Protect the next decision.','body':'Two or more of your last three trades closed at a loss. Take a five-minute pause, describe the setup, and reduce the next planned risk. A pause is part of the system.','action':'Pause before your next entry','source':'Rules coach · based on your closed trades'}
 if s['positions']: return {'title':'Manage the plan you already made.','body':'You have an open simulated position. Write down the exit condition before looking for another entry. Do not widen your stop to avoid accepting a loss.','action':'Review your open risk','source':'Rules coach · based on open positions'}
 return {'title':'Your edge starts before entry.','body':'Name the setup. Set the invalidation price. Calculate position size. If you cannot describe all three, observation is today’s trade.','action':'Complete the pre-trade checklist','source':'Rules coach · educational reflection'}

def draft(tool,brief,s):
 key=os.getenv('GEMINI_API_KEY'); model=os.getenv('GEMINI_MODEL','')
 if key and not model: raise ValueError('Set GEMINI_MODEL to a model available in your Google AI project')
 if key:
  prompt='You are SimuTrade Labs educational business assistant. Simulated funds only. No financial recommendations, guaranteed profits, funded account promises, invented statistics or testimonials. Create a useful editable '+tool+' draft from: '+brief+'. Use concrete original language. For trading, emphasize risk process and generic custom rules, never assert current firm rules. Keep under 600 words.'
  req=Request('https://generativelanguage.googleapis.com/v1beta/models/'+quote(model,safe='')+':generateContent',data=json.dumps({'contents':[{'parts':[{'text':prompt}]}]}).encode(),headers={'Content-Type':'application/json','x-goog-api-key':key})
  with urlopen(req,timeout=40) as r: d=json.load(r)
  return {'text':'\n'.join(p.get('text','') for p in d['candidates'][0]['content']['parts']),'mode':'Gemini AI draft','model':model}
 subject=brief.strip()
 templates={
 'Offer Architect':f'OFFER WORKSHEET\n\nAudience & context\n{subject}\n\nPromise\nBuild a repeatable pre-trade routine with measurable rule adherence.\n\nDelivery\n1. Baseline risk and discipline review\n2. Custom simulated challenge profile\n3. Four guided practice sessions\n4. Journal review and next-step plan\n\nPricing decision\nEnter your delivery hours, support cost, and target margin before setting a price. No outcome guarantees.\n\nNext step\nInvite a short fit conversation; qualify goals and available practice time.',
 'Niche Architect':f'NICHE VALIDATION PLAN\n\nHypothesis\n{subject}\n\nInterview five potential users about their last failed practice routine. Ask what rule broke, what they tried, and what they paid for.\n\nCompare\nExisting tools, switching friction, urgency, and weekly practice time.\n\nDecision\nProceed only when repeated needs match a deliverable you can fulfill. Mark all assumptions as unvalidated.',
 'VSL Builder OS':f'VIDEO SCRIPT OUTLINE\n\nContext: {subject}\n\nHook\nA good entry cannot rescue a broken risk routine.\n\nProblem\nDescribe the moment a trader moves a stop, increases size, or abandons the plan.\n\nDemonstration\nShow a simulated setup, the risk calculation, the challenge rule, and the journal reflection.\n\nOffer\nPractice the decision before risking real money.\n\nCTA\nOpen the free lab and complete one planned session.',
 'Ads Architect':f'CAMPAIGN DRAFT\n\nBrief: {subject}\n\nHeadline A: Practice your process. Measure your discipline.\nHeadline B: Every simulated trade needs a plan.\n\nBody: Build your challenge rules, calculate risk, and review the decisions behind each simulated trade. Start with one deliberate session.\n\nCTA: Explore the Lab\n\nTest plan: Compare qualified lab activations, not clicks alone. No profit or challenge-passing guarantees.',
 'Category Architect':f'POSITIONING WORKSHEET\n\nContext: {subject}\n\nCategory: Simulation-led trading education.\nAlternative: Disconnected charts, journals, and rule spreadsheets.\nDistinct mechanism: One loop connecting rules, simulated execution, and reflection.\nProof to gather: Rule adherence across repeated practice sessions.\nClaim boundary: Education with simulated funds; performance does not predict live outcomes.',
 'Sales Asset Architect':f'ASSET EXTRACTION WORKSHEET\n\nSource supplied:\n{subject}\n\n1. Identify the customer’s exact problem in the source.\n2. Pull a short, permission-cleared quote.\n3. Turn the demonstrated process into a three-step explanation.\n4. Draft a CTA tied to that process.\n5. Verify every claim against the original source.\n\nDo not invent results or customer endorsements.',
 'Landing Page Copywriter':f'LANDING COPY DRAFT\n\nBrief: {subject}\n\nHeadline\nBuild discipline before you build exposure.\n\nSubheading\nA simulated practice workspace for risk planning, custom challenge rules, and honest trade review.\n\nHow it works\nSet the rules. Rehearse the decision. Review the result.\n\nCTA\nStart a practice session\n\nTrust note\nSimulated funds only. No promise of profits or funded-account qualification.',
 'Research Agent':f'RESEARCH PLAN · NO WEB RETRIEVAL CONNECTED\n\nQuestion: {subject}\n\nPrimary sources to collect\nProvider’s official rules, instrument specifications, dated fee schedule, and data licensing terms.\n\nEvidence table\nClaim | Official source URL | Effective date | Verified by\n\nComparison\nDrawdown method, daily reset timezone, minimum days, consistency caps, and prohibited strategies.\n\nOpen question\nWhich rule differs most from your current practice assumptions?\n\nThis is a plan, not a sourced research report.',
 'AI Sales Agent':f'QUALIFICATION CONVERSATION DRAFT\n\nContext: {subject}\n\n1. What are you practicing for?\n2. Which rule is hardest to follow?\n3. How often can you practice?\n4. What does a useful review look like to you?\n\nSuggested reply\nLet’s start with a simulated session and review your risk routine. We can discuss fit after you see the workflow.\n\nFollow-up\nOffer a review conversation. No automatic sending or booking is configured.',
 'Nurture Sequence':f'FOLLOW-UP DRAFTS\n\nContext: {subject}\n\nDay 0 — Your first deliberate session\nSet one rule and complete one simulated trade. Reply with the decision you found hardest.\n\nDay 2 — Look behind the result\nWas the trade planned? Review process adherence separately from P&L.\n\nDay 5 — Make the next session smaller\nChoose one repeatable setup and one risk limit. Open the Lab when you are ready.\n\nThese are unsent drafts; secure consent before delivery.'}
 return {'text':templates.get(tool,templates['Research Agent']),'mode':'Structured template · AI not connected'}

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def out(self,status,obj,cookie=None):
  data=json.dumps(obj).encode(); self.send_response(status); self.headers_common();self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(data)
 def headers_common(self):
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('X-Frame-Options','SAMEORIGIN')
  self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'")
 def session(self):
  c=SimpleCookie(); c.load(self.headers.get('Cookie','')); token=c.get('st_session'); token=token.value if token else ''
  row,_=STORE.get('session:'+hashlib.sha256(token.encode()).hexdigest()) if token else (None,None)
  if not row or row['expires']<time.time():return None
  return row
 def body(self):
  size=int(self.headers.get('Content-Length','0'))
  if not 0<size<=100000: raise ValueError('Request size invalid')
  return json.loads(self.rfile.read(size))
 def do_GET(self):
  try:
   path=urlparse(self.path)
   if path.path=='/api/health':return self.out(200,{'ok':True,'storage':'firestore' if PROJECT else 'sqlite','market':'provider configured' if os.getenv('TWELVE_DATA_API_KEY') else 'synthetic replay','ai':bool(os.getenv('GEMINI_API_KEY') and os.getenv('GEMINI_MODEL'))})
   if path.path=='/api/market':return self.out(200,market(parse_qs(path.query).get('symbol',['NQ'])[0]))
   if path.path=='/api/me':
    u=self.session()
    if not u:return self.out(200,{'user':None})
    s,v=STORE.get('state:'+u['uid']);return self.out(200,{'user':{'email':u['email'],'name':u['name']},'state':s,'version':v})
   if path.path=='/api/leads':
    u=self.session()
    owner_token=os.getenv('ADMIN_ACCESS_TOKEN','')
    if not u or u['email']!=os.getenv('ADMIN_EMAIL','').lower() or not owner_token or not hmac.compare_digest(self.headers.get('X-Owner-Token',''),owner_token):return self.out(403,{'error':'Owner email and owner access token required'})
    idx,_=STORE.get('lead-index'); leads=[]
    for k in (idx or []):
     r,_=STORE.get(k)
     if r:leads.append(r)
    return self.out(200,{'leads':leads})
   if path.path.startswith('/api/'):return self.out(404,{'error':'Route not found'})
   target='/index.html' if path.path=='/' else '/app.html' if path.path in ('/app','/app/') else path.path
   p=(ROOT/'public'/target.lstrip('/')).resolve()
   if not p.is_relative_to((ROOT/'public').resolve()) or not p.is_file():return self.out(404,{'error':'Not found'})
   data=p.read_bytes();self.send_response(200);self.headers_common();self.send_header('Content-Type',mimetypes.guess_type(p)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','public,max-age=86400' if '/assets/' in target else 'no-cache');self.end_headers();self.wfile.write(data)
  except ValueError as e:self.out(400,{'error':str(e)})
  except Exception:self.out(503,{'error':'Service temporarily unavailable. Please retry.'})
 def do_POST(self):
  try:
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.out(403,{'error':'Cross-origin request rejected'})
   if self.headers.get('Sec-Fetch-Site')=='cross-site':return self.out(403,{'error':'Cross-site request rejected'})
   if not self.headers.get('Content-Type','').startswith('application/json'):return self.out(415,{'error':'JSON required'})
   path=urlparse(self.path).path;d=self.body()
   if not isinstance(d,dict):raise ValueError('Object required')
   if path=='/api/leads':
    if d.get('website'):return self.out(200,{'ok':True})
    email=str(d.get('email','')).strip().lower();name=str(d.get('name','')).strip()[:100]
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not name or d.get('consent') is not True:raise ValueError('Name, valid email, and consent required')
    key='lead:'+hashlib.sha256(email.encode()).hexdigest()
    with LOCK:
     old,v=STORE.get(key);STORE.put(key,{'id':key,'name':name,'email':email,'goal':str(d.get('goal',''))[:500],'created':old['created'] if old else time.time(),'updated':time.time(),'consent':True,'consentVersion':'waitlist-2026-11-08'},v)
     for attempt in range(4):
      idx,iv=STORE.get('lead-index');idx=idx or []
      if key in idx:break
      try:STORE.put('lead-index',idx+[key],iv);break
      except Conflict:
       if attempt==3:raise
    return self.out(200,{'ok':True,'message':'Your early-access request is saved. No email confirmation has been sent.'})
   if path in ('/api/register','/api/login'):
    email=str(d.get('email','')).strip().lower();pw=str(d.get('password',''));key='user:'+hashlib.sha256(email.encode()).hexdigest()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not 12<=len(pw)<=128:raise ValueError('Use a valid email and a password of 12–128 characters')
    # Durable per-email throttling works across Cloud Run instances.
    ratekey='rate:'+hashlib.sha256((email+str(int(time.time()//600))).encode()).hexdigest()
    with LOCK:
     rate,rv=STORE.get(ratekey);count=(rate or {}).get('count',0)
     if count>=15:return self.out(429,{'error':'Too many attempts. Try again in ten minutes.'})
     STORE.put(ratekey,{'count':count+1,'expires':time.time()+600},rv)
     u,uv=STORE.get(key)
     if path=='/api/register':
      if u:return self.out(409,{'error':'Account already exists. Sign in instead.'})
      salt=secrets.token_hex(16);uid=secrets.token_hex(16);u={'uid':uid,'email':email,'name':str(d.get('name','Trader'))[:80] or 'Trader','salt':salt,'hash':hashlib.scrypt(pw.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()};STORE.put(key,u);STORE.put('state:'+uid,fresh())
     elif not u or not hmac.compare_digest(hashlib.scrypt(pw.encode(),salt=bytes.fromhex(u['salt']),n=16384,r=8,p=1).hex(),u['hash']):return self.out(401,{'error':'Email or password incorrect'})
     token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24);STORE.put('session:'+hashlib.sha256(token.encode()).hexdigest(),{'uid':u['uid'],'email':email,'name':u['name'],'expires':time.time()+604800})
    cookie='st_session='+token+'; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800'+('; Secure' if CLOUD or self.headers.get('X-Forwarded-Proto')=='https' else '')
    return self.out(200,{'ok':True},cookie)
   u=self.session()
   if not u:return self.out(401,{'error':'Sign in to save across devices. Guest practice stays in this browser.'})
   if path=='/api/logout':
    c=SimpleCookie();c.load(self.headers.get('Cookie',''));key='session:'+hashlib.sha256(c['st_session'].value.encode()).hexdigest();old,v=STORE.get(key);old['expires']=0;STORE.put(key,old,v)
    return self.out(200,{'ok':True},'st_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'+('; Secure' if CLOUD else ''))
   with LOCK:
    s,v=STORE.get('state:'+u['uid'])
    if d.get('version')!=v:raise Conflict('Changed in another tab. Refresh and try again.')
    if path=='/api/state':
     incoming=d.get('state',{})
     for k in ('journal','contacts','assets','automations','alerts','completedLessons'):
      if k in incoming:
       if not isinstance(incoming[k],list) or len(incoming[k])>500:raise ValueError('Collection limit exceeded')
       s[k]=incoming[k]
     if 'rules' in incoming:
      r=incoming['rules'];s['rules']={'dailyLoss':num(r['dailyLoss'],0.1,20),'maxLoss':num(r['maxLoss'],0.1,50),'target':num(r['target'],0.1,100),'risk':num(r['risk'],0.01,5),'minDays':int(num(r['minDays'],1,100))}
      s['profile']=str(incoming.get('profile','Custom'))[:80]
    elif path=='/api/reset':s=fresh()
    elif path in ('/api/trade','/api/close'):
     day=time.strftime('%Y-%m-%d',time.gmtime())
     if s['day']!=day:s['dayStart']=s['balance'];s['day']=day
     if path=='/api/trade':
      if len(s['positions'])>=3:raise ValueError('Close an open position before adding more (maximum 3)')
      day=time.strftime('%Y-%m-%d',time.gmtime())
      if s['day']!=day:s['dayStart']=s['balance'];s['day']=day
      r=s['rules'];daily=s['dayStart']-s['balance'];total=s['initial']-s['balance']
      if daily>=s['initial']*r['dailyLoss']/100 or total>=s['initial']*r['maxLoss']/100:raise ValueError('Challenge loss limit reached. Review your journal or reset the practice account.')
      m=market(str(d.get('symbol','NQ')));p=m['price'];qty=int(num(d.get('qty',1),1,100));side=d.get('side');stop=num(d.get('stop'),0.01,1e7);take=num(d.get('take'),0.01,1e7)
      if side not in ('buy','sell') or not (stop<p<take if side=='buy' else take<p<stop):raise ValueError('Stop and target must bracket entry in the trade direction')
      risk=abs(p-stop)*qty*m['pointValue'];openrisk=sum(x['risk'] for x in s['positions'])
      if risk>s['balance']*r['risk']/100+0.01:raise ValueError('Position exceeds your per-trade risk limit. Reduce size or stop distance.')
      if risk+openrisk>min(s['initial']*r['dailyLoss']/100-daily,s['initial']*r['maxLoss']/100-total):raise ValueError('Combined open risk exceeds remaining loss allowance')
      if not d.get('checklist'):raise ValueError('Complete the pre-trade checklist')
      s['positions'].append({'id':secrets.token_hex(8),'symbol':m['symbol'],'entry':p,'qty':qty,'side':side,'stop':stop,'take':take,'risk':round(risk,2),'pointValue':m['pointValue'],'opened':time.time(),'mode':m['mode']})
     else:
      pos=next((x for x in s['positions'] if x['id']==d.get('id')),None)
      if not pos:raise ValueError('Position not found')
      m=market(pos['symbol']);exit=m['price'];pnl=round((exit-pos['entry'])*(1 if pos['side']=='buy' else -1)*pos['qty']*pos['pointValue'],2)
      pos.update({'exit':exit,'pnl':pnl,'closed':time.time()});s['trades'].insert(0,pos);s['positions']=[x for x in s['positions'] if x['id']!=pos['id']];s['balance']=round(s['balance']+pnl,2);s['peak']=max(s['peak'],s['balance'])
    elif path=='/api/draft':return self.out(200,draft(str(d.get('tool','Research Agent'))[:100],str(d.get('brief',''))[:5000],s))
    elif path=='/api/coach':return self.out(200,coach(s))
    else:return self.out(404,{'error':'Route not found'})
    nv=STORE.put('state:'+u['uid'],s,v)
   self.out(200,{'ok':True,'state':s,'version':nv})
  except Conflict as e:self.out(409,{'error':str(e)})
  except (ValueError,TypeError,KeyError) as e:self.out(400,{'error':str(e)})
  except Exception:self.out(503,{'error':'Service temporarily unavailable. No success was confirmed. Please retry.'})

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=int(os.getenv('PORT','3000')));parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--strictPort',action='store_true');args=parser.parse_args()
 port=args.port; print(f'SimuTrade Labs listening on {port}',flush=True);ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
