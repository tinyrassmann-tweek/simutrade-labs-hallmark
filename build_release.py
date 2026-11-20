"""Build self-contained HTML previews and full source archives; standard library only."""
from pathlib import Path
import base64, hashlib, json, re, zipfile
ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/'public'
OUT=ROOT/'dist'
OUT.mkdir(exist_ok=True)

def stylesheet(name):
    text=(PUBLIC/name).read_text(encoding='utf-8')
    return re.sub(r"@import\s+url\(['\"]?\./([^)'\"]+)['\"]?\);",lambda m:stylesheet(m[1]),text)
CSS=stylesheet('style.css')+'\n'+stylesheet('premium.css')

def standalone(name,script=None):
    text=(PUBLIC/name).read_text(encoding='utf-8')
    text=text.replace('<link rel="stylesheet" href="/style.css">','<style>'+CSS+'</style>')
    text=re.sub(r'<link rel="stylesheet" href="/premium\.css(?:\?[^"\n]*)?">','',text)
    text=re.sub(r'<link rel="manifest"[^>]*>','',text)
    for asset in (PUBLIC/'assets').glob('*.webp'):
        text=text.replace('/assets/'+asset.name,'data:image/webp;base64,'+base64.b64encode(asset.read_bytes()).decode())
    if script:
        text=re.sub(r'<script[^>]*src="/'+re.escape(script)+r'"[^>]*>\s*</script>','',text)
        text=text.replace('</body>','<script>window.SIMUTRADE_PREVIEW=true;\n'+(PUBLIC/script).read_text(encoding='utf-8')+'</script></body>')
    return text.replace('href="/app','href="SimuTrade-Labs-App-Preview.html').replace('href="/privacy.html"','href="privacy.html"').replace('href="/terms.html"','href="terms.html"').replace('href="/"','href="SimuTrade-Labs-Landing.html"')

MODAL_CSS='''<style>#portable-preview{margin:0;inset:0;max-width:none;max-height:none;width:100vw;height:100dvh;padding:0;border:0;background:#080e18;color:#d8e9ec;border-radius:0;overflow:hidden}#portable-preview::backdrop{background:#020810e8}#portable-preview header{height:58px;padding:0 20px;display:flex;align-items:center;justify-content:space-between;gap:15px;background:#102230;border-bottom:1px solid #355466;font:12px Arial,sans-serif}#portable-preview header span{color:#92b7c8}#portable-preview button{border:1px solid #426376;border-radius:4px;color:#e2f0f0;background:#142f40;min-height:40px;padding:8px 15px;font:12px Arial,sans-serif}#portable-frame{display:block;width:100%;height:calc(100dvh - 58px);border:0;background:#080e18}</style>'''
BRIDGE='''<script>document.addEventListener('click',function(e){const a=e.target.closest('a');if(a&&a.getAttribute('href')==='SimuTrade-Labs-Landing.html'&&window.parent!==window){e.preventDefault();window.parent.postMessage({type:'simutrade-portable-home'},'*');}});</script>'''

def embed_pages(text,pages):
    payload=json.dumps(pages,ensure_ascii=False).replace('</','<\\/')
    extra=MODAL_CSS+'''<dialog id="portable-preview" aria-label="SimuTrade interactive preview"><header><span id="portable-title">SimuTrade Labs / Practice preview</span><button type="button" id="portable-close">Back to page ×</button></header><iframe id="portable-frame" title="SimuTrade interactive workspace"></iframe></dialog><script type="application/json" id="portable-pages">'''+payload+'''</script><script>
(function(){const pages=JSON.parse(document.getElementById('portable-pages').textContent),dialog=document.getElementById('portable-preview'),frame=document.getElementById('portable-frame');document.getElementById('portable-close').addEventListener('click',()=>dialog.close());function openPage(href){const file=href.split('#')[0];if(!pages[file]||typeof dialog.showModal!=='function')return false;let html=pages[file];if(file==='SimuTrade-Labs-App-Preview.html'){const route=href.split('#')[1]||'overview';html=html.replace('window.SIMUTRADE_PREVIEW=true;','window.SIMUTRADE_PREVIEW=true;window.SIMUTRADE_START_PAGE='+JSON.stringify(route)+';');}document.getElementById('portable-title').textContent=file==='SimuTrade-Labs-App-Preview.html'?'SimuTrade Labs / Guest practice preview':file==='privacy.html'?'SimuTrade Labs / Privacy':'SimuTrade Labs / Simulation limits';frame.srcdoc=html;if(!dialog.open)dialog.showModal();return true;}document.addEventListener('click',function(event){const a=event.target.closest('a');if(a&&openPage(a.getAttribute('href')||''))event.preventDefault();});window.addEventListener('message',function(event){if(event.source!==frame.contentWindow||!event.data)return;if(event.data.type==='simutrade-portable-home')dialog.close();if(event.data.type==='simutrade-portable-open'&&typeof event.data.href==='string'){if(!openPage(event.data.href)&&event.data.href.startsWith('SimuTrade-Labs-App-Preview.html')){dialog.close();location.hash=event.data.href.split('#')[1]||'overview';}}});})();
</script>'''
    return text.replace('</body>',extra+'</body>')

LEGAL_BRIDGE="""<script>document.addEventListener('click',function(event){const a=event.target.closest('a');if(!a||window.parent===window)return;const href=a.getAttribute('href')||'';if(href==='SimuTrade-Labs-Landing.html'){event.preventDefault();window.parent.postMessage({type:'simutrade-portable-home'},'*');}else if(href.startsWith('SimuTrade-Labs-App-Preview.html')){event.preventDefault();window.parent.postMessage({type:'simutrade-portable-open',href:href},'*');}});</script>"""
privacy=standalone('privacy.html').replace('</body>',LEGAL_BRIDGE+'</body>')
terms=standalone('terms.html').replace('</body>',LEGAL_BRIDGE+'</body>')
app=standalone('app.html','app.js').replace('</body>',BRIDGE+'</body>')
app=embed_pages(app,{'privacy.html':privacy,'terms.html':terms})
landing=embed_pages(standalone('index.html','landing.js'),{'SimuTrade-Labs-App-Preview.html':app,'privacy.html':privacy,'terms.html':terms})
outputs={'SimuTrade-Labs-Landing.html':landing,'SimuTrade-Labs-App-Preview.html':app,'privacy.html':privacy,'terms.html':terms}
for name,text in outputs.items():(OUT/name).write_text(text,encoding='utf-8')
(OUT/'SimuTrade-Labs-Launch-Guide.html').write_text((ROOT/'START-HERE.html').read_text(encoding='utf-8').replace('dist/SimuTrade-','SimuTrade-').replace('../SimuTrade-','SimuTrade-'),encoding='utf-8')

EXCLUDED={'.git','dist','deliverables','data','__pycache__','.venv','node_modules'}
def source_files():
    for path in sorted(ROOT.rglob('*')):
        rel=path.relative_to(ROOT)
        if not path.is_file() or any(p in EXCLUDED for p in rel.parts):continue
        if path.name.startswith('.env') and path.name!='.env.example':continue
        if path.name.startswith('_visual-qa') or path.name.startswith('_portable-qa'):continue
        if path.suffix in {'.pyc','.log'}:continue
        yield path,rel

archive=OUT/'SimuTrade-Labs-Complete-Build.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for path,rel in source_files():z.write(path,Path('simutrade-labs')/rel)
    for name in [*outputs,'SimuTrade-Labs-Launch-Guide.html']:z.write(OUT/name,name)
with zipfile.ZipFile(OUT/'SimuTrade-Labs-GitHub-Ready.zip','w',zipfile.ZIP_DEFLATED) as z:
    files={}
    for path,rel in source_files():
        if str(rel)=='.hallmark/compare.html':continue
        z.write(path,Path('simutrade-labs')/rel);files[str(rel)]=hashlib.sha256(path.read_bytes()).hexdigest()
    z.writestr('SHA256SUMS.json',json.dumps(files,indent=2)+'\n')
for name in ['SimuTrade-Labs-Landing.html','SimuTrade-Labs-App-Preview.html','SimuTrade-Labs-Complete-Build.zip','SimuTrade-Labs-GitHub-Ready.zip']:
    print(name, (OUT/name).stat().st_size, 'bytes')
