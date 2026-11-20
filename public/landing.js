'use strict';
(() => {
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const cash = n => '$' + Number(n).toLocaleString('en-US', {maximumFractionDigits:2});
const menu=$('.menu-toggle'), nav=$('.nav-links');
menu.addEventListener('click',()=>{const open=nav.classList.toggle('open');menu.setAttribute('aria-expanded',String(open));menu.setAttribute('aria-label',open?'Close navigation':'Open navigation');});
nav.addEventListener('click',e=>{if(e.target.closest('a')){nav.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){nav.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');}});
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
if(!reduced.matches && 'IntersectionObserver' in window){
 document.documentElement.classList.add('js-motion');
 const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('is-visible');observer.unobserve(entry.target);}}),{threshold:.07,rootMargin:'0px 0px 30px 0px'});
 $$('.m-reveal').forEach(el=>observer.observe(el));
}
$('#motion-toggle').addEventListener('click',()=>{const paused=document.body.classList.toggle('motion-paused');$('#motion-toggle').setAttribute('aria-pressed',String(paused));$('#motion-toggle').setAttribute('aria-label',paused?'Resume ambient animations':'Pause ambient animations');$('#motion-toggle').innerHTML=paused?'<span aria-hidden="true">▷</span> <span>Resume motion</span>':'<span aria-hidden="true">||</span> <span>Pause motion</span>';});
if(reduced.matches){$('#motion-toggle').hidden=true;document.body.classList.add('motion-paused');}
function heroChart(){
 const svg=$('#hero-chart'), y=v=>215-(v-19990)*6;
 const values=Array.from({length:36},(_,i)=>19996+i*.46+Math.sin(i*.78)*3.3+Math.sin(i*1.9));
 const grid=[19990,20000,20010,20020].map(v=>`<line class="m-chart-grid" x1="18" x2="630" y1="${y(v)}" y2="${y(v)}"/>`).join('');
 const n=values.length,mean=values.reduce((a,b)=>a+b)/n,mx=(n-1)/2,slope=values.reduce((a,v,i)=>a+(i-mx)*(v-mean),0)/values.reduce((a,_,i)=>a+(i-mx)**2,0),intercept=mean-slope*mx;
 const candles=values.map((v,i)=>{const o=i?values[i-1]:v-1,x=23+i*13.4,bull=v>=o;return `<g class="m-candle" style="--delay:${i*.009}s"><line x1="${x}" x2="${x}" y1="${y(Math.max(o,v)+1.3)}" y2="${y(Math.min(o,v)-1.2)}" stroke="${bull?'#54dce8':'#68878f'}"/><rect x="${x-3.1}" y="${Math.min(y(o),y(v))}" width="6.2" height="${Math.max(2,Math.abs(y(o)-y(v)))}" rx=".7" fill="${bull?'#62d7df':'#637f89'}"/></g>`;}).join('');
 svg.innerHTML=`<defs><linearGradient id="heroWash" x2="0" y2="1"><stop stop-color="#54dce8" stop-opacity=".10"/><stop offset="1" stop-color="#54dce8" stop-opacity=".01"/></linearGradient><clipPath id="heroClip"><rect x="18" y="16" width="489" height="215"/></clipPath></defs><rect x="18" y="${y(20020)}" width="489" height="${y(20000)-y(20020)}" fill="url(#heroWash)"/><rect x="18" y="${y(20000)}" width="489" height="${y(19990)-y(20000)}" fill="#f88e91" opacity=".035"/>${grid}<g clip-path="url(#heroClip)">${candles}<path d="M23,${y(intercept)}L492,${y(intercept+slope*35)}" stroke="#d7b773" stroke-width="1" stroke-dasharray="4 5" fill="none" opacity=".7"/><line class="m-scan" x1="20" x2="20" y1="18" y2="228" stroke="#b6f4f5" stroke-width=".6"/></g><line class="m-reference" x1="18" x2="505" y1="${y(20020)}" y2="${y(20020)}" stroke="#54dce8" opacity=".5"/><line class="m-reference" x1="18" x2="505" y1="${y(20000)}" y2="${y(20000)}" stroke="#a4bdc8"/><line class="m-reference" x1="18" x2="505" y1="${y(19990)}" y2="${y(19990)}" stroke="#c9958d" opacity=".6"/><text x="523" y="${y(20020)-7}" style="fill:#75c9ce;font-size:8px">TARGET REF.</text><text x="523" y="${y(20020)+9}">20,020</text><text x="523" y="${y(20000)-7}" style="fill:#bdcdd4;font-size:8px">ENTRY EXAMPLE</text><text x="523" y="${y(20000)+9}">20,000</text><text x="523" y="${y(19990)-7}" style="fill:#bf9691;font-size:8px">STOP REF.</text><text x="523" y="${y(19990)+9}">19,990</text>`;
}
heroChart();
$$('[data-hero-size]').forEach(button=>button.addEventListener('click',()=>{
 const risk=Number(button.dataset.heroSize)*200,over=risk>500;
 $$('[data-hero-size]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 $('#hero-risk-title').textContent=cash(risk)+(over?' exceeds your limit':' planned risk');
 $('#hero-risk-sub').textContent=over?'Above your $500 cap. Reduce size before entry.':'Inside your $500 limit. '+cash(500-risk)+' remains unused.';
 $('#hero-risk-pct').textContent=(risk/1000).toFixed(2)+'%';
 $('#hero-risk-result').classList.toggle('over',over);$('#hero-risk-result .m-check-icon').innerHTML=over?'!':'<svg viewBox="0 0 16 16" class="m-inline-icon" aria-hidden="true"><path d="M3 8l3 3 7-7" fill="none"/></svg>';
}));
const tabs=$$('[role=tab]');
function showTab(tab){tabs.forEach(t=>{const active=t===tab;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;document.getElementById(t.getAttribute('aria-controls')).hidden=!active;});}
tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>showTab(tab));tab.addEventListener('keydown',e=>{let target;if(e.key==='ArrowRight')target=(index+1)%tabs.length;if(e.key==='ArrowLeft')target=(index+tabs.length-1)%tabs.length;if(e.key==='Home')target=0;if(e.key==='End')target=tabs.length-1;if(target!==undefined){e.preventDefault();tabs[target].focus();showTab(tabs[target]);}});});
function planUpdate(checked=false){const size=Number($('#plan-size').value),risk=size*200,over=risk>500;$('#plan-risk').textContent=cash(risk);$('#plan-risk').style.color=over?'var(--red)':'var(--cyan)';$('#plan-size-label').textContent=size+(size===1?' contract':' contracts');$('#plan-fill').style.width=Math.min(100,risk/500*100)+'%';$('#plan-fill').style.background=over?'linear-gradient(90deg,#f88e9160,#f88e91aa)':'';$('#plan-feedback').textContent=checked?(over?'Over the limit by '+cash(risk-500)+'. This planned risk would be rejected by the Lab. Reduce the size to 2 contracts or fewer.':'Inside the $500 cap. '+cash(risk)+' planned risk leaves '+cash(500-risk)+' unused. This checks the per-trade cap only.'):(over?'This size exceeds your per-trade limit. Check the plan to see the adjustment.':'The risk changes with size. Check this plan before a simulated entry.');$('#plan-feedback').style.color=over?'#efa3a5':'#a7c0cb';}
$('#plan-size').addEventListener('input',()=>planUpdate());$('#plan-check').addEventListener('click',()=>planUpdate(true));
let replayIndex=0,replaySide='long';const replayValues=[20002,19996,20008,20001];
function replayDraw(){const value=replayValues[replayIndex],pnl=(value-20000)*40*(replaySide==='long'?1:-1);$('#replay-price').textContent=value.toLocaleString('en-US',{minimumFractionDigits:2});$('#replay-pnl').textContent=(pnl>=0?'+':'−')+cash(Math.abs(pnl));$('#replay-pnl').style.color=pnl>=0?'var(--cyan)':'var(--red)';$('#replay-step').textContent=(replayIndex+1)+' / 4';const y=v=>145-(v-19990)*6;const vals=Array.from({length:25},(_,i)=>19996+Math.sin(i*.57)*3+i*.1).concat(replayValues.slice(0,replayIndex+1)),pts=vals.map((v,i)=>[18+i*(430/(vals.length-1)),y(v)]),d=pts.map((p,i)=>(i?'L':'M')+p.join(',')).join(' '),last=pts[pts.length-1];$('#replay-chart').innerHTML=[35,85,135].map(v=>`<line class="m-chart-grid" x1="0" x2="600" y1="${v}" y2="${v}"/>`).join('')+`<path d="${d} L448,160 L18,160 Z" fill="#54dce809"/><path d="${d}" stroke="#54dce8" stroke-width="2" fill="none"/><line x1="0" x2="600" y1="${y(20000)}" y2="${y(20000)}" stroke="#879fa8" stroke-dasharray="4 5"/><circle cx="${last[0]}" cy="${last[1]}" r="4" fill="#a6eff1"/><text x="470" y="${y(20000)-8}" style="font-size:9px">ENTRY 20,000</text><text x="18" y="183" style="font-size:9px">CONTROLLED SYNTHETIC EXAMPLE</text>`;}
replayDraw();$('#replay-next').addEventListener('click',()=>{replayIndex=(replayIndex+1)%4;replayDraw();});$$('[data-replay-side]').forEach(b=>b.addEventListener('click',()=>{replaySide=b.dataset.replaySide;$$('[data-replay-side]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));replayDraw();}));
$('#review-example').addEventListener('submit',e=>{e.preventDefault();const f=e.target,followed=f.elements.followed.checked,emotion=f.elements.emotion.value,note=f.elements.note.value.trim();$('#review-feedback').textContent=(followed?'Plan followed. Keep the specific behavior you want to repeat.':'Plan needs review. Name one boundary you will keep on your next repetition.')+' Feeling recorded: '+emotion+'.'+(note?' Your note is ready for review.':' Add one concrete observation to make the lesson useful.')+' This example is not saved to your journal.';});
function riskUpdate(){const balance=Number($('#risk-balance').value),percent=Number($('#risk-slider').value),distance=Number($('#risk-distance').value),budget=balance*percent/100,per=distance*20,units=Math.floor((budget+.000001)/per),used=units*per,unused=budget-used,ratio=used/budget;$('#risk-pct').textContent=percent.toFixed(2)+'%';$('#risk-amount').textContent=cash(budget);$('#risk-equation').textContent=cash(balance)+' × '+percent.toFixed(2)+'%';$('#risk-contracts').textContent=units;$('#risk-used').textContent=cash(used);$('#risk-unused').textContent=cash(unused);const w=470,fill=w*ratio;$('#risk-diagram').innerHTML=`<defs><linearGradient id="budgetFill"><stop stop-color="#2b6d7c"/><stop offset="1" stop-color="#62dce4" stop-opacity=".8"/></linearGradient><pattern id="budgetHatch" width="7" height="7" patternUnits="userSpaceOnUse"><path d="M-1,1l2,-2M0,7l7,-7M6,8l2,-2" stroke="#d7b773" stroke-opacity=".25" stroke-width="1"/></pattern></defs><line x1="32" x2="502" y1="26" y2="26" stroke="#335160"/><text x="32" y="18">Your planned risk</text><text x="502" y="18" text-anchor="end">${cash(budget)} budget</text><path d="M32,65L47,54H517L502,65Z" fill="#2a4b5b"/><path d="M502,65L517,54V116L502,127Z" fill="#223e4e"/><rect x="32" y="65" width="470" height="62" fill="url(#budgetHatch)" stroke="#526c72"/><rect x="32" y="65" width="${fill}" height="62" fill="url(#budgetFill)"/><line x1="${32+fill}" x2="${32+fill}" y1="57" y2="135" stroke="#e6c682" stroke-width="1.4"/><text x="32" y="154" style="fill:#8ed8de">${cash(used)} planned loss</text><text x="502" y="154" text-anchor="end" style="fill:#c7b383">${cash(unused)} unused</text><text x="32" y="180" style="font-size:9px">${units} × ${distance} points × $20/point = ${cash(used)}</text>`;$('#risk-diagram').setAttribute('aria-label',cash(budget)+' budget, '+cash(used)+' planned loss, '+cash(unused)+' unused. '+units+' whole contracts.');}
['risk-balance','risk-distance','risk-slider'].forEach(id=>document.getElementById(id).addEventListener('input',riskUpdate));riskUpdate();
let pauseEnd=0,pauseInterval;
function pauseTick(){const seconds=pauseEnd?Math.max(0,Math.ceil((pauseEnd-Date.now())/1000)):300;$('#landing-pause-time').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');if(pauseEnd&&seconds===0){pauseEnd=0;clearInterval(pauseInterval);$('#landing-pause').textContent='Try the five-minute pause';$('#landing-pause-status').textContent='Pause complete. Review your setup and risk before returning.';}}
$('#landing-pause').addEventListener('click',()=>{if(pauseEnd){pauseEnd=0;clearInterval(pauseInterval);$('#landing-pause').textContent='Try the five-minute pause';$('#landing-pause-status').textContent='Pause ended. Return to your plan when you are ready.';}else{pauseEnd=Date.now()+300000;pauseInterval=setInterval(pauseTick,1000);$('#landing-pause').textContent='End this pause';$('#landing-pause-status').textContent='Pause started. Name the setup, the risk, and one deliberate next step.';}pauseTick();});
$('#lead-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.target,b=f.querySelector('button[type=submit]'),status=$('#lead-status');b.disabled=true;b.setAttribute('aria-busy','true');status.textContent='Saving your request…';try{if(location.protocol==='file:'||window.SIMUTRADE_PREVIEW)throw new Error('This downloaded page is an interactive preview. Run the included server to send your request.');const data=Object.fromEntries(new FormData(f));data.consent=f.elements.consent.checked;const payload = {
  submissionId: crypto.randomUUID(),
  name: data.name,
  email: data.email,
  company: "",
  venture: "SimuTrade Labs",
  message: "Early access interest: " + data.goal,
  goal: data.goal,
  website: data.website,
  consent: data.consent
};
const r = await fetch('/api/leads', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(payload)
});const d=await r.json();if(!r.ok)throw new Error(d.error||'Unable to save. Please retry.');if (typeof d.reference !== 'string' || !d.reference) {
  throw new Error('The request was not confirmed. Please retry.');
}
status.textContent = 'Your early-access request is saved. Reference: ' +
  d.reference + '. No email confirmation has been sent.';status.className='m-fine positive';status.style.setProperty('color','var(--green)','important');f.reset();}catch(error){status.className='m-fine negative';status.style.setProperty('color','var(--red)','important');status.textContent=error.message;}finally{b.disabled=false;b.removeAttribute('aria-busy');}});
})();
