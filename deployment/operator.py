"""Owner-authenticated operator. Tokens never appear in output or command arguments."""
import sys,json,subprocess,urllib.request,base64
action=sys.argv[1]
if action not in ('activate','suspend','team'):raise SystemExit('Choose activate, suspend or team')
token=subprocess.check_output(['gcloud','auth','print-identity-token'],text=True,stderr=subprocess.DEVNULL).strip()
info=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'=='))
if info.get('email','').lower()!='tiny.rassmann@gmail.com':raise SystemExit('Use the existing owner gcloud sign-in.')
url='https://simutradelabs.thinktanksolutionsai.online/api/simutrade/operator/'+action
body=None
if action=='team':url+='?id='+sys.argv[2]
else:body=json.dumps(json.load(open(sys.argv[2]))).encode()
req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
with urllib.request.urlopen(req,timeout=45) as r:print(json.dumps(json.load(r),indent=2))
