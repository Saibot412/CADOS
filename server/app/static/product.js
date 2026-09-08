"use strict";

let currentPage = 'home', selectedCategory = '', preparedWorkout = null;
const pageDescriptions = {
  home: 'Dein Training. Dein Rhythmus.', workout: 'Finde die Einheit, die heute zu dir passt.',
  calendar: 'Gib deinem Training einen festen Platz.', profile: 'Die Grundlage für ein Training, das zu dir passt.',
  session: 'Jede Einheit zählt. Hier siehst du deinen Fortschritt.',
  settings: 'Alles so, wie du es brauchst.', users: 'Konten und Zugriffsrechte verwalten.', live: ''
};
const navPaths = {
  home:'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
  workout:'M3 19V9h4v10m2 0V4h5v15m2 0v-7h5v7M2 21h20',
  live:'m13 2-9 12h7l-1 8 10-12h-7Z', calendar:'M4 5h16v16H4ZM8 2v6m8-6v6M4 11h16',
  profile:'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2',
  session:'M3 11a9 9 0 1 1 2 7M3 4v7h7m2-5v6l4 3',
  settings:'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6',
  users:'M14 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M2 21v-2a8 8 0 0 1 16 0v2m-1-17a4 4 0 0 1 0 7m3 4a7 7 0 0 1 2 6'
};
for (const tab of document.querySelectorAll('[data-tab]')) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('aria-hidden','true');
  const path = document.createElementNS(svg.namespaceURI,'path');
  path.setAttribute('d',navPaths[tab.dataset.tab]); svg.append(path); tab.prepend(svg);
}

function navigate(page) {
  currentPage = page;
  for (const tab of document.querySelectorAll('[data-tab]')) {
    tab.className = tab.dataset.tab === page ? '' : 'quiet';
    if (tab.dataset.tab === page) tab.setAttribute('aria-current','page');
    else tab.removeAttribute('aria-current');
  }
  for (const key of Object.keys(titles)) $('#'+key+'-panel').hidden = key !== page;
  $('#page-title').textContent = titles[page]; $('#subtitle').textContent = pageDescriptions[page];
  document.body.classList.toggle('live-focus-active',page === 'live');
  if (page === 'users') reloadUsers().catch(e=>notice(e.message,true));
  renderLive();
  window.scrollTo(0,0);
}

function localDate(date = new Date()) {
  return date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
}
function durationOf(workout) { return Math.round((workout.blocks || []).reduce((n,b)=>n+b.duration_sec,0)/60); }
function primaryButton(label, action) { const result = button(label,action); result.className = 'primary'; return result; }
function planWorkout(record) {
  $('#workout-detail').close(); navigate('calendar');
  $('#plan-workout').value = record.id;
  $('#plan-form').elements.date.value = localDate();
  $('#plan-form').elements.date.focus();
}

function openPlan(plan) {
  let dialog=$('#planned-detail');
  if(!dialog){dialog=node('dialog');dialog.id='planned-detail';dialog.setAttribute('aria-labelledby','planned-title');document.body.append(dialog);}
  dialog.replaceChildren();
  const heading=node('div',undefined,'dialog-head'),title=node('h2',plan.payload.workout_name);title.id='planned-title';
  heading.append(title,button('Schließen',()=>dialog.close()));dialog.append(heading);
  dialog.append(node('p',new Date(plan.payload.date+'T12:00:00').toLocaleDateString('de-AT',{weekday:'long',day:'numeric',month:'long',year:'numeric'})));
  const workout=active('workout').find(r=>r.id===plan.payload.workout_id),actions=node('div',undefined,'detail-actions');
  if(workout){dialog.append(workoutPreview(workout.payload,active('profile')[0]?.payload.ftp||250));actions.append(primaryButton('Training vorbereiten',()=>{dialog.close();openWorkout(workout);}));}
  else dialog.append(node('p','Dieses Workout ist nicht mehr in deiner Bibliothek.','muted'));
  actions.append(button('Aus Kalender entfernen',async()=>{
    if(!confirm('Nur diese geplante Einheit aus dem Kalender entfernen? Das Workout bleibt in deiner Bibliothek.'))return;
    await save({...plan,deleted:true});dialog.close();notice('Geplante Einheit entfernt.');
  }));dialog.append(actions);dialog.showModal();
}

function renderWorkoutLibrary() {
  const all = active('workout'), categories = [...new Set(all.map(r=>r.payload.category||'Workout'))].sort();
  if (!categories.includes(selectedCategory)) selectedCategory = '';
  const filters = $('#workout-filters'); filters.replaceChildren();
  for (const category of ['',...categories]) {
    const chip = button(category || 'Alle Workouts',()=>{selectedCategory=category;renderWorkoutLibrary();});
    chip.className='filter-chip'; chip.setAttribute('aria-pressed',String(category===selectedCategory)); filters.append(chip);
  }
  const search = $('#search').value.toLocaleLowerCase(), list = $('#workouts'); list.replaceChildren();
  const shown = all.filter(r=>(!selectedCategory || (r.payload.category||'Workout')===selectedCategory) &&
    (r.payload.name+' '+(r.payload.category||'')).toLocaleLowerCase().includes(search))
    .sort((a,b)=>(a.payload.sort_order||0)-(b.payload.sort_order||0)||a.payload.name.localeCompare(b.payload.name));
  $('#workout-count').textContent=shown.length+' '+(shown.length===1?'Workout':'Workouts');
  for (const record of shown) {
    const p=record.payload, card=node('article',undefined,'card workout-card'), meta=node('div',undefined,'workout-meta');
    meta.append(node('span',p.category||'Workout','tag'),node('span',record.shared?'Bibliothek':'Privat','ownership'));
    const duration=node('div',undefined,'workout-duration'); duration.append(node('strong',String(durationOf(p))),node('span',' min'));
    card.append(meta,node('h2',p.name),duration,node('p',p.description||'Dein strukturiertes Training.','workout-description'),workoutPreview(p,active('profile')[0]?.payload.ftp||250));
    const actions=node('div',undefined,'actions');
    actions.append(primaryButton('Training vorbereiten',()=>openWorkout(record)),button('Planen',()=>planWorkout(record)));
    card.append(actions); list.append(card);
  }
  if(!shown.length){const empty=node('div',undefined,'empty');empty.append(node('h2',all.length?'Kein Treffer. Noch ein Versuch?':'Platz für dein erstes Workout.'),node('p',all.length?'Ändere die Suche oder wähle eine andere Kategorie.':'Importiere eine JSON- oder ZWO-Datei und lege los.'));list.append(empty);}
}

function renderOverview() {
  const sessions=active('session').sort((a,b)=>b.payload.timestamp.localeCompare(a.payload.timestamp));
  const weekStart=new Date(); weekStart.setHours(0,0,0,0);weekStart.setDate(weekStart.getDate()-((weekStart.getDay()+6)%7));
  const weekly=sessions.filter(r=>new Date(r.payload.timestamp)>=weekStart);
  const minutes=Math.round(weekly.reduce((n,r)=>n+(r.payload.duration_sec||0),0)/60);
  const summary=$('#home-summary'); summary.replaceChildren();
  for(const [label,value,detail] of [['Diese Woche',weekly.length,'gefahrene Einheiten'],['Trainingszeit',minutes+' min','seit Montag'],['Deine FTP',(active('profile')[0]?.payload.ftp??'–')+' W','persönliche Leistungsschwelle']]) {
    const item=node('article',undefined,'summary-card');item.append(node('span',label),node('strong',String(value)),node('small',detail));summary.append(item);
  }
  const next=active('plan').filter(r=>r.payload.date>=localDate()).sort((a,b)=>a.payload.date.localeCompare(b.payload.date))[0];
  const hero=$('#next-workout'); hero.replaceChildren();
  hero.append(node('p',next?'ALS NÄCHSTES':'DEIN NÄCHSTER SCHRITT','eyebrow'));
  if(next) {
    const workout=active('workout').find(r=>r.id===next.payload.workout_id);
    hero.append(node('h2',next.payload.workout_name),node('p',new Date(next.payload.date+'T12:00:00').toLocaleDateString('de-AT',{weekday:'long',day:'numeric',month:'long'}),'hero-date'));
    if(workout){hero.append(workoutPreview(workout.payload,active('profile')[0]?.payload.ftp||250),primaryButton('Training vorbereiten',()=>openWorkout(workout)));}
    else hero.append(button('Plan im Kalender ansehen',()=>navigate('calendar')));
  } else {
    hero.append(node('h2','Zeit für deine nächste Einheit.'),node('p','Entdecke deine Workouts oder plane schon jetzt dein nächstes Training.'));
    const art=workoutPreview({blocks:[{duration_sec:100,target_watts:65},{duration_sec:60,target_watts:125},{duration_sec:40,target_watts:65},{duration_sec:60,target_watts:165},{duration_sec:40,target_watts:65},{duration_sec:60,target_watts:125},{duration_sec:100,target_watts:65}]},250);
    art.setAttribute('aria-hidden','true');art.querySelectorAll('text').forEach(label=>label.remove());hero.append(art,primaryButton('Workouts entdecken',()=>navigate('workout')));
  }
  const recent=$('#recent-sessions');recent.replaceChildren();
  if(!sessions.length)recent.append(node('p','Deine erste Einheit wartet auf dich. Nach dem Training findest du hier deinen Verlauf.','empty'));
  for(const record of sessions.slice(0,3)) {
    const row=node('article',undefined,'recent-row'), info=node('div'); info.append(node('strong',record.payload.workout_name),node('small',new Date(record.payload.timestamp).toLocaleDateString('de-AT',{day:'numeric',month:'long'})+' · '+Math.round(record.payload.duration_sec/60)+' min'));
    row.append(info,button('Verlauf ansehen →',()=>showSession(record)));recent.append(row);
  }
  const profile=active('profile')[0]?.payload;
  if(profile)$('#email').textContent=profile.name||user?.email||'';
  renderSetupStatus();
}

function renderSetupStatus() {
  const host=$('#setup-status');host.replaceChildren();
  for(const [label,ready,text] of [['Connector',connectorConnected,connectorConnected?'Verbunden':'Öffnen oder installieren'],['Trainer',connectorConnected&&liveData.trainer_connected,connectorConnected&&liveData.trainer_connected?(liveData.trainer_name||'Verbunden'):'Noch nicht verbunden']]) {
    const row=node('div',undefined,'setup-row');row.append(node('span',label));const value=node('strong',text,ready?'is-ready':'');row.append(value);host.append(row);
  }
  if(preparedWorkout && $('#workout-detail').open) {
    const ready=connectorConnected&&liveData.trainer_connected, busy=['running','paused','waiting_for_pedal'].includes(liveData.state);
    $('#workout-readiness').textContent=!connectorConnected?'Öffne CADOS Connector auf deinem Computer. Du kannst dieses Workout schon jetzt planen.':!liveData.trainer_connected?'Verbinde deinen eingeschalteten Trainer, um zu starten.':busy?'Ein Training ist bereits aktiv. Du kannst in die Trainingsansicht zurückkehren.':'Alles bereit. Dein Trainer ist verbunden.';
    $('#prepare-start').disabled=!ready||busy;$('#prepare-connect').hidden=!connectorConnected||!!liveData.trainer_connected;
  }
}

function openWorkout(record) {
  preparedWorkout=record;const p=record.payload,content=$('#workout-detail-content');content.replaceChildren();
  $('#workout-detail-title').textContent=p.name;
  content.append(node('p',(p.category||'Workout')+' · '+durationOf(p)+' min','detail-meta'),node('p',p.description||'Dein strukturiertes Training.'),workoutPreview(p,active('profile')[0]?.payload.ftp||250));
  $('#prepare-erg').value=$('#live-erg').value;
  const manage=$('#workout-manage');manage.replaceChildren();
  const closeThen=action=>()=>{$('#workout-detail').close();return action();};
  manage.append(button(user.admin||!record.shared?'Workout bearbeiten':'Workout-Details',closeThen(()=>edit(record))),button('Kopieren',closeThen(()=>copy(record))),button('Exportieren',()=>download(record)));
  if(user.admin||!record.shared){const removeButton=button('Löschen',closeThen(()=>remove(record)));removeButton.classList.add('danger-text');manage.append(removeButton);}
  $('#workout-detail').showModal();renderSetupStatus();
}
$('#close-workout-detail').onclick=()=>$('#workout-detail').close();
$('#prepare-plan').onclick=()=>planWorkout(preparedWorkout);
$('#prepare-connect').onclick=()=>$('#connector-connect').click();
$('#prepare-start').onclick=()=>{
  if(!connectorConnected||!liveData.trainer_connected)return;
  try{$('#live-erg').value=$('#prepare-erg').value;startOnMac(preparedWorkout);$('#workout-detail').close();}
  catch(error){notice(error.message,true);}
};
$('#setup-open').onclick=()=>navigate('live');$('#all-sessions').onclick=()=>navigate('session');

const productLiveBase=renderLive;
renderLive=function(){
  productLiveBase();renderSetupStatus();
  const banner=$('#connector-download');if(banner)banner.hidden=connectorConnected||!['home','workout'].includes(currentPage);
  const running=['running','waiting_for_pedal'].includes(liveData.state), paused=liveData.state==='paused';
  $('#live-pause').disabled=!connectorConnected||!running;
  $('#live-resume').disabled=!connectorConnected||!paused;
  $('#live-stop').disabled=!connectorConnected||!(running||paused);
  $('#live-erg').disabled=!connectorConnected;
  $('#live-state').textContent=({idle:'Bereit',ready:'Bereit',running:'Training läuft',paused:'Pausiert',waiting_for_pedal:'Bereit zum Losfahren',stopped:'Beendet',completed:'Geschafft'})[liveData.state]||'Bereit';
};
const productShowDashboardBase=showDashboard;
showDashboard=function(){productShowDashboardBase();navigate('home');};
const productShowLoginBase=showLogin;
showLogin=function(){productShowLoginBase();liveData={};connectorVersion='';liveWorkout=null;liveHistory=[];preparedWorkout=null;document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());};

const productNoticeBase=notice;let noticeTimer;
notice=function(message,error=false){
  clearTimeout(noticeTimer);document.querySelectorAll('.dialog-notice').forEach(item=>item.remove());
  const dialog=document.querySelector('dialog[open]');
  if(dialog){const inline=node('p',message,'dialog-notice'+(error?' error':''));inline.setAttribute('role','status');dialog.prepend(inline);inline.scrollIntoView({block:'nearest'});return;}
  productNoticeBase(message,error);const close=node('button','×','notice-close');close.setAttribute('aria-label','Meldung schließen');close.onclick=()=>$('#notice').hidden=true;$('#notice').append(close);if(!error)noticeTimer=setTimeout(()=>$('#notice').hidden=true,5000);
};
// Keyboard-friendly native dialogs: Escape closes them and focus returns to the trigger.
for(const dialog of document.querySelectorAll('dialog'))dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
$('#plan-form').elements.date.value=localDate();
$('#plan-form').elements.date.min=localDate();
$('#previous-month').setAttribute('aria-label','Vorheriger Monat');$('#next-month').setAttribute('aria-label','Nächster Monat');
// Initialize only after the full interface (including live-view hooks) is ready.
api('/auth/me').then(async account=>{user=account;showDashboard();await reload();}).catch(error=>{if(user)notice(error.message,true);});
