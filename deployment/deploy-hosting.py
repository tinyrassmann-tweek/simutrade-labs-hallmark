"""Publish immutable public files while preserving the existing Hosting file map and routes."""
import concurrent.futures,copy,gzip,hashlib,json,pathlib,subprocess,urllib.parse,urllib.request
SITE='simutrade-labs-tts'
EXPECTED='sites/simutrade-labs-tts/versions/a4bb174c4cbed45f'
ROOT=pathlib.Path(__file__).resolve().parents[1]
TOKEN=subprocess.check_output(['gcloud','auth','print-access-token'],text=True).strip()
def api(path,method='GET',body=None):
 req=urllib.request.Request('https://firebasehosting.googleapis.com/v1beta1/'+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
previous=api('sites/'+SITE+'/releases?pageSize=1')['releases'][0]['version']['name']
assert previous==EXPECTED,'Concurrent Hosting release. Inspect before retrying.'
old=api(previous);listing=api(previous+'/files?pageSize=1000');assert not listing.get('nextPageToken')
files={f['path']:f['hash'] for f in listing['files']};packed={};hashes={}
for p in sorted((ROOT/'public').rglob('*')):
 if not p.is_file():continue
 path='/'+str(p.relative_to(ROOT/'public'));data=p.read_bytes();blob=gzip.compress(data,mtime=0);digest=hashlib.sha256(blob).hexdigest()
 files[path]=digest;packed[digest]=blob;hashes[path]=hashlib.sha256(data).hexdigest()
config=copy.deepcopy(old.get('config',{}));rewrites=config.setdefault('rewrites',[])
assert not any(r.get('glob')=='/api/simutrade/**' for r in rewrites)
rewrites.insert(0,{'glob':'/api/simutrade/**','run':{'serviceId':'think-tank-hub','region':'us-east1'}})
rules=config.setdefault('headers',[])
rule=next((x for x in rules if x.get('glob')=='**'),None)
if rule is None:rule={'glob':'**','headers':{}};rules.append(rule)
rule['headers'].update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'strict-origin-when-cross-origin','X-Frame-Options':'DENY','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"})
created=api('sites/'+SITE+'/versions','POST',{'config':config});version=created['name']
populated=api(version+':populateFiles','POST',{'files':files})
def upload(digest):
 req=urllib.request.Request(populated['uploadUrl']+'/'+digest,data=packed[digest],method='POST',headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/octet-stream'})
 with urllib.request.urlopen(req,timeout=45) as r:r.read()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(upload,populated.get('uploadRequiredHashes',[])))
api(version+'?updateMask=status','PATCH',{'status':'FINALIZED'})
assert api('sites/'+SITE+'/releases?pageSize=1')['releases'][0]['version']['name']==previous,'Concurrent release; stop'
released=api('sites/'+SITE+'/releases?versionName='+urllib.parse.quote(version,safe=''),'POST',{})
receipt={'previous':previous,'version':version,'release':released['name'],'public_files':hashes,'preserved_previous_files':len(listing['files']),'total_files':len(files),'api_route':'/api/simutrade/**','service':'think-tank-hub','region':'us-east1'}
pathlib.Path('/tmp/simutrade-hosting-receipt.json').write_text(json.dumps(receipt,indent=2))
print('ST_HOSTING_RELEASE '+json.dumps({k:v for k,v in receipt.items() if k!='public_files'}))
