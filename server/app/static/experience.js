"use strict";

let serverConnected=false,lastTelemetryAt=0,pendingStart=false,selectedPlanId=null;
let pendingReview=null,reviewAttempt=0,reviewBusy=false,hasRecovered=false,homeLiveKey='';
const isTrainingActive=()=>['running','paused','waiting_for_pedal'].includes(liveData.state);
const sessionStatus=status=>({completed:'Abgeschlossen',stopped:'Vorzeitig beendet',interrupted:'Unterbrochen'})[status]||'Gespeichert';
function setDataLoading(loading){$('#refresh').disabled=loading;$('#refresh').textContent=loading?'Lädt …':'Aktualisieren';$('#dashboard').setAttribute('aria-busy',String(loading));}
function planCompleted(plan){return active('session').some(r=>r.payload.status==='completed'&&r.payload.plan_id===plan.id);}
function readableDate(date){return new Date(date+'T12:00:00').toLocaleDateString('de-AT',{weekday:'short',day:'numeric',month:'long'});}
function workoutLoad(workout,ftp){
 const blocks=workout.blocks||[],total=blocks.reduce((n,b)=>n+Number(b.duration_sec),0);
 if(!total)return 'Freies Training';
 const relative=blocks.reduce((n,b)=>n+(liveBlockWatts(b,ftp,'start')+liveBlockWatts(b,ftp,'end'))/2*Number(b.duration_sec),0)/total/ftp;
 return relative<.56?'Locker':relative<.76?'Moderat':relative<.91?'Anspruchsvoll':'Intensiv';
}
function renderOverview(){
 const profile=active('profile')[0]?.payload,ftp=profile?.ftp||250;
 const sessions=active('session').sort((a,b)=>b.payload.timestamp.localeCompare(a.payload.timestamp));
 const plans=active('plan').filter(r=>r.payload.date>=localDate()&&!planCompleted(r)).sort((a,b)=>a.payload.date.localeCompare(b.payload.date));
 const today=plans.find(r=>r.payload.date===localDate());
 const hero=$('#next-workout');hero.replaceChildren();
 if(isTrainingActive()){
  hero.append(node('p','DEIN TRAINING IST AKTIV','eyebrow'),node('h2',liveData.workout_name),node('p','Dein Connector hält den Trainingsstand. Du kannst jederzeit zur Ansicht zurückkehren.'));
  hero.append(primaryButton('Zum laufenden Training',()=>navigate('live')));
 }else if(today){
  const workout=active('workout').find(r=>r.id===today.payload.workout_id);
  hero.append(node('p','HEUTE FÜR DICH GEPLANT','eyebrow'),node('h2',today.payload.workout_name));
  if(workout){
   hero.append(node('p',durationOf(workout.payload)+' min · '+workoutLoad(workout.payload,ftp)+' · '+(workout.payload.category||'Workout'),'hero-date'),workoutPreview(workout.payload,ftp));
   const ready=connectorConnected&&liveData.trainer_connected;
   hero.append(primaryButton(ready?'Training starten':'Training vorbereiten',()=>{
    if(ready){selectedPlanId=today.id;startOnMac(workout);}else openWorkout(workout,today.id);
   }));
  }else hero.append(node('p','Das zugehörige Workout ist nicht mehr verfügbar.'),button('Plan bearbeiten',()=>openPlan(today)));
 }else{
  const completedToday=sessions.some(r=>dayKey(r.payload.timestamp)===localDate()&&r.payload.status==='completed');
  hero.append(node('p',completedToday?'HEUTE SCHON GESCHAFFT':'DEIN TRAINING HEUTE','eyebrow'),node('h2',completedToday?'Gut gefahren. Zeit zum Erholen.':'Heute ist noch alles offen.'),node('p',completedToday?'Deine Einheit ist gespeichert. Schau dir deinen Abschluss an oder plane die nächsten Tage.':'Wähle eine passende Einheit aus deiner Bibliothek. Oder halte dir heute bewusst frei.'));
  hero.append(primaryButton(completedToday?'Abschluss ansehen':'Workout auswählen',()=>completedToday?showSession(sessions.find(r=>dayKey(r.payload.timestamp)===localDate()&&r.payload.status==='completed')):navigate('workout')));
 }
 const start=new Date();start.setHours(0,0,0,0);start.setDate(start.getDate()-((start.getDay()+6)%7));
 const weekly=sessions.filter(r=>new Date(r.payload.timestamp)>=start&&new Date(r.payload.timestamp)<=new Date());
 const summary=$('#home-summary');summary.replaceChildren();
 for(const [label,value,detail] of [['Diese Woche',weekly.length,'gefahrene Einheiten'],['Trainingszeit',Math.round(weekly.reduce((n,r)=>n+r.payload.duration_sec,0)/60)+' min','seit Montag'],['Deine FTP',ftp+' W','Basis deiner Leistungszonen']]){
  const card=node('article',undefined,'summary-card');card.append(node('span',label),node('strong',String(value)),node('small',detail));summary.append(card);
 }
 const upcoming=$('#upcoming-plans');upcoming.replaceChildren();
 for(const plan of plans.filter(p=>p.id!==today?.id).slice(0,3)){
  const row=node('article',undefined,'recent-row'),info=node('div');info.append(node('small',readableDate(plan.payload.date)),node('strong',plan.payload.workout_name));row.append(info,button('Ansehen',()=>openPlan(plan)));upcoming.append(row);
 }
 if(!upcoming.children.length)upcoming.append(node('p','Noch keine weiteren Einheiten geplant. Im Kalender findest du Platz für dein nächstes Ziel.','empty'));
 const recent=$('#recent-sessions');recent.replaceChildren();
 const last=sessions[0];
 if(last){const p=last.payload,card=node('article',undefined,'last-session card');card.append(node('span',sessionStatus(p.status),'tag'),node('h3',p.workout_name),node('p',readableDate(dayKey(p.timestamp))),node('strong',formatTime(p.duration_sec)+' · '+metric(p.metrics?.avg_watts,'W')+' · '+metric(p.metrics?.avg_cadence,'rpm')),button('Auswertung ansehen →',()=>showSession(last)));recent.append(card);}
 else recent.append(node('p','Nach deiner ersten Fahrt findest du hier deinen Abschluss mit Verlauf und Leistungszonen.','empty'));
 if(profile)$('#email').textContent=profile.name||user?.email||'';
 if(currentPage==='home')$('#subtitle').textContent=readableDate(localDate())+' · '+(profile?.name?'Schön, dass du da bist, '+profile.name+'.':'Dein Training. Dein Rhythmus.');
 renderSetupStatus();
 const updateAvailable=connectorRelease&&connectorVersion&&compareVersion(connectorVersion,connectorRelease.version)<0;
 const setup=$('#setup-open');setup.textContent=updateAvailable?'Connector aktualisieren':connectorConnected?(liveData.trainer_connected?'Verbindung ansehen →':'Trainer verbinden'):connectorInstalledHere?'Connector starten':'Connector einrichten';
 setup.onclick=()=>{if(updateAvailable){window.open(connectorRelease.macos.url,'_blank','noopener');return;}if(!connectorConnected){if(connectorInstalledHere)location.href='cados-connector://open';else navigate('workout');}else if(!liveData.trainer_connected)$('#connector-connect').click();else navigate('live');};
}
$('#home-calendar').onclick=()=>navigate('calendar');

function acceptTelemetry(data,recovery=false){
 lastTelemetryAt=Date.now();connectorConnected=true;liveData=data;
 if(isTrainingActive())pendingStart=false;
 if(recovery&&!hasRecovered){hasRecovered=true;if(isTrainingActive())navigate('live');}
 if(data.session_id&&!isTrainingActive()){
  let reviewed=false;try{reviewed=sessionStorage.getItem('cados.review.'+user.id)===data.session_id;}catch{}
  if(!reviewed)pendingReview=data.session_id;
 }
 renderLive();
}
const experienceRenderLive=renderLive;
renderLive=function(){
 experienceRenderLive();
 const stale=isTrainingActive()&&(!serverConnected||!connectorConnected||Date.now()-lastTelemetryAt>8000);
 document.body.classList.toggle('telemetry-stale',stale);
 const detail=$('#connector-detail');
 if(stale){
  $('#connector-status').textContent='Live-Verbindung unterbrochen';
  detail.textContent='Werte sind eingefroren. Der Connector steuert lokal weiter. Pause und Beenden findest du in seinem Fenster.';
  for(const id of ['live-pause','live-resume','live-stop','live-erg'])$('#'+id).disabled=true;
 }else if(isTrainingActive()&&!liveData.trainer_connected){
  detail.textContent='Trainerverbindung verloren. Das Training pausiert. Schalte den Trainer ein und klicke auf „Trainer verbinden“.';
 }else if(liveData.state==='paused'){
  detail.textContent=liveData.auto_paused?'Automatisch pausiert. Sobald du wieder trittst, geht es sanft weiter.':'Training pausiert. Klicke auf „Fortsetzen“, wenn du bereit bist.';
 }else if(liveData.session_id){detail.textContent=liveData.sync_pending?'Training lokal gespeichert. Die Synchronisierung wird automatisch nachgeholt.':'Training gespeichert und synchronisiert.';}
 if(pendingStart){$('#live-state').textContent='Start wird bestätigt …';$('#live-stop').disabled=true;}
 const key=[liveData.state,connectorConnected,liveData.trainer_connected,connectorInstalledHere,connectorVersion,connectorRelease?.version].join('|');
 if(key!==homeLiveKey){homeLiveKey=key;renderOverview();}
};
setInterval(()=>{
 if(user){renderLive();if(pendingReview&&!reviewBusy&&serverConnected&&Date.now()>reviewAttempt)loadCompletedSession();}
},2000);
async function loadCompletedSession(){
 reviewBusy=true;reviewAttempt=Date.now()+5000;const id=pendingReview,account=user?.id;
 try{
  const result=await api('/sync');if(account!==user?.id)return;
  records=result.records;const record=active('session').find(r=>r.id===id);
  if(record){pendingReview=null;try{sessionStorage.setItem('cados.review.'+account,id);}catch{}render();document.querySelectorAll('dialog[open]').forEach(d=>d.close());showSession(record);}
 }catch{ /* Local saving is independent; retry the account snapshot after reconnect. */ }
 finally{reviewBusy=false;}
}
window.addEventListener('online',()=>{if(user){connectLive();reload().catch(()=>{});}});
window.addEventListener('offline',()=>{serverConnected=false;renderLive();});
const experienceLogin=showLogin;
showLogin=function(){experienceLogin();hasRecovered=false;homeLiveKey='';document.body.classList.remove('telemetry-stale');};

function sessionComparison(p){
 const section=node('section',undefined,'result-chart');section.append(node('h3','Dein Soll-/Ist-Verlauf'));
 const samples=p.samples||[];
 if(!samples.length){section.append(node('p','Für diese Einheit sind keine Messwerte vorhanden.','empty'));return section;}
 const svg=svgElement('svg',{viewBox:'0 0 1000 340',role:'img','aria-label':'Soll und Ist: Leistung in Watt, Kadenz in rpm, Zeit in Minuten und Sekunden'});
 const ftp=p.ftp_watts||250,width=1000,height=340,left=125,right=60,top=28,bottom=35;
 const step=Math.max(1,Math.ceil(samples.length/1800)),shown=samples.filter((_,i)=>i%step===0||i===samples.length-1);
 const total=samples.reduce((n,s)=>Math.max(n,s.elapsed_sec||0),1),maximum=samples.reduce((n,s)=>Math.max(n,(s.watts||0)*1.1,(s.target_watts||0)*1.1),ftp*1.7);
 drawPowerZones(svg,{ftp,maximum,left,right,top,bottom,width,height});
 const x=t=>left+t/total*(width-left-right),wy=v=>top+(1-v/maximum)*(height-top-bottom);
 const cadenceTarget=s=>{let cursor=0;for(const block of p.workout_payload?.blocks||[]){cursor+=block.duration_sec;if((s.workout_elapsed_sec??s.elapsed_sec)<cursor)return block.target_cadence??null;}return null;};
 const cadenceMax=Math.max(110,...shown.map(s=>Math.max(s.cadence||0,cadenceTarget(s)||0)+10)),cy=v=>top+(1-v/cadenceMax)*(height-top-bottom);
 for(const [key,color,dash,y,value] of [['target_watts','#137c73','7 5',wy,s=>s.target_watts],['watts','#193d55','',wy,s=>s.watts],['target_cadence','#3b79b8','7 5',cy,cadenceTarget],['cadence','#7654a8','',cy,s=>s.cadence]]){
  const valid=shown.filter(s=>value(s)!=null&&Number.isFinite(Number(value(s))));
  if(valid.length)svg.append(svgElement('polyline',{points:valid.map(s=>x(s.elapsed_sec)+','+y(value(s))).join(' '),fill:'none',stroke:color,'stroke-width':2.5,'stroke-dasharray':dash,'data-series':key}));
 }
 for(let i=0;i<=2;i++)svgText(svg,String(Math.round(cadenceMax*(1-i/2))),width-right+9,top+i/2*(height-top-bottom)+4,{fill:'#3b79b8'});
 svgText(svg,'rpm',width-right+9,14);svgText(svg,'0:00',left,height-8);svgText(svg,'Zeit (min:sek)',width/2,height-8,{'text-anchor':'middle'});svgText(svg,formatTime(total),width-right,height-8,{'text-anchor':'end'});
 const legend=node('p','Grün gestrichelt: Soll-Watt · Dunkelblau: Ist-Watt · Blau gestrichelt: Soll-Kadenz · Violett: Ist-Kadenz','chart-axis-description');
 section.append(svg,legend);return section;
}
function sessionZones(p){
 const section=node('section',undefined,'result-zones');section.append(node('h3','Zeit in deinen Leistungszonen'));
 const ftp=p.ftp_watts,seconds=powerZones.map(()=>0);
 if(!ftp||!(p.samples||[]).length){section.append(node('p','Für diese Einheit fehlen FTP oder Messwerte.','muted'));return section;}
 for(const sample of p.samples){if(sample.watts==null)continue;const index=powerZones.findIndex(z=>sample.watts<=z.upper*ftp);if(index>=0)seconds[index]+=Math.max(0,Number(sample.duration_sec)||0);}
 const total=seconds.reduce((a,b)=>a+b,0);
 powerZones.forEach((zone,i)=>{
  const row=node('div',undefined,'zone-row'),label=node('span',zone.code+' · '+zone.name),track=node('div',undefined,'zone-track'),bar=node('div');
  bar.style.width=(total?seconds[i]/total*100:0)+'%';bar.style.background=zone.color;track.append(bar);
  row.append(label,track,node('strong',formatTime(seconds[i])));section.append(row);
 });section.append(node('p','Berechnet aus deinen gemessenen Wattwerten und der FTP dieser Einheit ('+ftp+' W).','chart-axis-description'));return section;
}
function showSession(record){
 const p=record.payload,content=$('#session-content');content.replaceChildren();
 $('#session-title').textContent=p.status==='completed'?'Training geschafft.':sessionStatus(p.status);
 content.append(node('p',p.workout_name,'result-workout'),node('p',readableDate(dayKey(p.timestamp))+' · '+sessionStatus(p.status),'muted'));
 const summary=node('div',undefined,'result-metrics');
 for(const [label,value] of [['Trainingszeit',formatTime(p.duration_sec)],['Ø Leistung',metric(p.metrics?.avg_watts,'W')],['Ø Kadenz',metric(p.metrics?.avg_cadence,'rpm')],['Belastung',metric(p.metrics?.tss,'TSS')]]){const card=node('article');card.append(node('span',label),node('strong',value));summary.append(card);}
 content.append(summary,sessionComparison(p),sessionZones(p));
 const form=node('form',undefined,'effort-form');form.append(node('h3','Wie anstrengend war es?'),node('p','Dein persönliches Gefühl, von 1 (sehr leicht) bis 10 (maximal).'));
 const label=node('label','Belastung bewerten'),select=node('select');select.name='perceived_exertion';select.required=true;const empty=node('option','Bewertung auswählen');empty.value='';select.append(empty);
 for(let value=1;value<=10;value++){const option=node('option',String(value)+' · '+(value<=2?'Sehr leicht':value<=4?'Leicht':value<=6?'Anstrengend':value<=8?'Sehr anstrengend':'Maximal'));option.value=value;select.append(option);}select.value=p.perceived_exertion??'';label.append(select);
 const submit=node('button',p.perceived_exertion?'Bewertung aktualisieren':'Bewertung speichern'),status=node('p',undefined,'muted');status.setAttribute('role','status');
 form.append(label,submit,status);form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{await save({...record,payload:{...record.payload,perceived_exertion:Number(select.value)}});record=active('session').find(r=>r.id===record.id)||record;status.textContent='Deine Bewertung ist gespeichert.';}catch(error){status.textContent=error.message;}finally{submit.disabled=false;}};
 content.append(form);const actions=node('div',undefined,'detail-actions');actions.append(primaryButton('Zur Übersicht',()=>{$('#session-detail').close();navigate('home');}),button('Im Kalender ansehen',()=>{$('#session-detail').close();calendarMonth=dayKey(p.timestamp).slice(0,7);renderCalendar();navigate('calendar');}));content.append(actions);
 if(!$('#session-detail').open)$('#session-detail').showModal();
}
api('/auth/me').then(async account=>{user=account;showDashboard();await reload();}).catch(error=>{if(user)notice(error.message,true);});
