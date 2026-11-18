import unittest,tempfile,subprocess,os,time,json,urllib.request,urllib.error,http.cookiejar,socket,pathlib,sqlite3,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
class AppTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();cls.base=f'http://127.0.0.1:{port}'
  env={**os.environ,'PORT':str(port),'DB_PATH':cls.tmp.name+'/test.db','ADMIN_EMAIL':'owner@example.test','ADMIN_ACCESS_TOKEN':'owner-test-token'}
  for k in ('GOOGLE_CLOUD_PROJECT','K_SERVICE','TWELVE_DATA_API_KEY','GEMINI_API_KEY'):env.pop(k,None)
  cls.proc=subprocess.Popen(['python3','server.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL)
  for _ in range(50):
   try:urllib.request.urlopen(cls.base+'/api/health',timeout=1);break
   except Exception:time.sleep(.1)
 @classmethod
 def tearDownClass(cls):cls.proc.terminate();cls.proc.wait();cls.tmp.cleanup()
 def request(self,path,data=None,client=None,headers=None):
  req=urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json',**(headers or {})})
  try:
   opener=client.open if client else urllib.request.urlopen
   with opener(req,timeout=10) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def account(self,email=None):
  c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));email=email or f'{time.time_ns()}@example.test'
  status,r=self.request('/api/register',{'email':email,'name':'QA Trader','password':'temporary-test-password-123'},c);self.assertEqual(status,200,r)
  return c,self.request('/api/me',client=c)[1]
 def trade(self,c,r,qty=1,wrong=False):
  p=self.request('/api/market')[1]['price'];return self.request('/api/trade',{'version':r['version'],'symbol':'NQ','side':'buy','qty':qty,'stop':p+(5 if wrong else -5),'take':p+20,'checklist':True},c)
 def test_lead_consent_dedup_and_durable_storage(self):
  self.assertEqual(self.request('/api/leads',{'name':'QA','email':'qa@example.test'})[0],400)
  for _ in range(2):self.assertEqual(self.request('/api/leads',{'name':'QA','email':'qa@example.test','consent':True})[0],200)
  with sqlite3.connect(self.tmp.name+'/test.db') as c:self.assertEqual(len(json.loads(c.execute("SELECT value FROM records WHERE key='lead-index'").fetchone()[0])),1)
 def test_account_isolation(self):
  a,ar=self.account();b,br=self.account();s=ar['state'];s['journal']=[{'title':'Private'}];self.assertEqual(self.request('/api/state',{'state':s,'version':ar['version']},a)[0],200);self.assertEqual(self.request('/api/me',client=b)[1]['state']['journal'],[])
 def test_password_login_and_hash(self):
  email=f'login{time.time_ns()}@example.test';c,r=self.account(email);self.assertEqual(self.request('/api/login',{'email':email,'password':'incorrect-test-password'})[0],401)
  self.assertEqual(self.request('/api/login',{'email':email,'password':'temporary-test-password-123'})[0],200)
  with sqlite3.connect(self.tmp.name+'/test.db') as db:
   v=json.loads(db.execute('SELECT value FROM records WHERE key=?',('user:'+hashlib.sha256(email.encode()).hexdigest(),)).fetchone()[0]);self.assertNotIn('password',v);self.assertEqual(len(v['hash']),128)
 def test_trade_close_pnl_and_persistence(self):
  c,r=self.account();status,t=self.trade(c,r);self.assertEqual(status,200,t);pos=t['state']['positions'][0];status,z=self.request('/api/close',{'version':t['version'],'id':pos['id']},c);self.assertEqual(status,200,z);self.assertEqual(z['state']['positions'],[]);self.assertEqual(len(z['state']['trades']),1);self.assertAlmostEqual(z['state']['balance'],100000+z['state']['trades'][0]['pnl']);self.assertEqual(self.request('/api/me',client=c)[1]['state'],z['state'])
 def test_risk_and_bracket_enforced(self):
  c,r=self.account();status,d=self.trade(c,r,100);self.assertEqual(status,400);self.assertIn('risk limit',d['error']);self.assertEqual(self.trade(c,r,wrong=True)[0],400)
 def test_stale_version_rejected(self):
  c,r=self.account();d={'state':r['state'],'version':r['version']};self.assertEqual(self.request('/api/state',d,c)[0],200);self.assertEqual(self.request('/api/state',d,c)[0],409)
 def test_client_cannot_forge_balance(self):
  c,r=self.account();status,d=self.request('/api/state',{'state':{'balance':9999999,'trades':[{'pnl':999}]},'version':r['version']},c);self.assertEqual(status,200);self.assertEqual(d['state']['balance'],100000);self.assertEqual(d['state']['trades'],[])
 def test_cross_origin_and_unauth_denied(self):
  self.assertEqual(self.request('/api/leads',{'name':'x'},headers={'Origin':'https://evil.example'})[0],403);self.assertEqual(self.request('/api/state',{'state':{}})[0],401);self.assertEqual(self.request('/api/leads')[0],403)
 def test_logout_revokes_session(self):
  c,r=self.account();self.assertEqual(self.request('/api/logout',{},c)[0],200);self.assertIsNone(self.request('/api/me',client=c)[1]['user'])
 def test_owner_inbox_requires_both_credentials(self):
  c,r=self.account('owner@example.test');self.assertEqual(self.request('/api/leads',client=c)[0],403);self.assertEqual(self.request('/api/leads',client=c,headers={'X-Owner-Token':'owner-test-token'})[0],200)
 def test_honest_templates_and_feed(self):
  c,r=self.account();status,d=self.request('/api/draft',{'tool':'Research Agent','brief':'Compare rules','version':r['version']},c);self.assertEqual(status,200);self.assertIn('AI not connected',d['mode']);self.assertIn('NO WEB RETRIEVAL',d['text']);m=self.request('/api/market')[1];self.assertEqual(m['mode'],'replay');self.assertEqual(len(m['bars']),64);self.assertEqual(self.request('/api/market?symbol=INVALID')[0],400)
 def test_invalid_rule_values(self):
  c,r=self.account();rules={**r['state']['rules'],'risk':float('nan')};self.assertEqual(self.request('/api/state',{'state':{'rules':rules},'version':r['version']},c)[0],400)
 def test_static_assets_and_security_headers(self):
  for p in ('/','/app','/privacy.html','/terms.html','/style.css','/app.js','/assets/hero.webp','/assets/review.webp'):
   with urllib.request.urlopen(self.base+p) as r:self.assertEqual(r.status,200);self.assertEqual(r.headers.get('X-Content-Type-Options'),'nosniff')
if __name__=='__main__':unittest.main()
