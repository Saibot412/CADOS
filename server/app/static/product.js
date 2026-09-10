"use strict";

let currentPage = 'home', selectedCategory = '', preparedWorkout = null;
const pageDescriptions = {
  home: 'Dein Training. Dein Rhythmus.', workout: 'Finde die Einheit, die heute zu dir passt.',
  calendar: 'Gib deinem Training einen festen Platz.',
  session: 'Jede Einheit zählt. Hier siehst du deinen Fortschritt.',
  settings: 'Deine Trainingswerte und dein Passwort an einem Ort.', users: 'Konten und Zugriffsrechte verwalten.', live: ''
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
  const label=tab.textContent.trim();
  tab.textContent='';tab.append(node('span',label,'nav-label'));
  tab.setAttribute('aria-label',label);tab.title=label;
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('aria-hidden','true');
  const path = document.createElementNS(svg.namespaceURI,'path');
  path.setAttribute('d',navPaths[tab.dataset.tab]); svg.append(path); tab.prepend(svg);
}

const sidebarToggle=node('button',undefined,'sidebar-toggle');
sidebarToggle.type='button';sidebarToggle.id='sidebar-toggle';
document.querySelector('#dashboard>nav').prepend(sidebarToggle);
function setSidebarCollapsed(collapsed) {
  document.body.classList.toggle('sidebar-collapsed',collapsed);
  sidebarToggle.setAttribute('aria-expanded',String(!collapsed));
  sidebarToggle.setAttribute('aria-label',collapsed?'Menü ausklappen':'Menü einklappen');
  sidebarToggle.title=sidebarToggle.getAttribute('aria-label');
  sidebarToggle.replaceChildren(node('span',collapsed?'›':'‹','sidebar-chevron'),node('span','Menü einklappen','nav-label'));
  try{localStorage.setItem('cados.sidebar.collapsed',String(collapsed));}catch{}
}
let sidebarCollapsed=false;
try{sidebarCollapsed=localStorage.getItem('cados.sidebar.collapsed')==='true';}catch{}
setSidebarCollapsed(sidebarCollapsed);
sidebarToggle.onclick=()=>setSidebarCollapsed(!document.body.classList.contains('sidebar-collapsed'));

let previewDialog=null,previewTimer,previewCloseTimer,previewPinned=false;
function closeChartPreview() {
  clearTimeout(previewTimer);clearTimeout(previewCloseTimer);
  if(previewDialog?.open)previewDialog.close();
}
function showChartPreview(workout,ftp,pinned=false) {
  clearTimeout(previewTimer);clearTimeout(previewCloseTimer);
  if(!previewDialog){
    previewDialog=node('dialog');previewDialog.id='chart-preview';
    previewDialog.setAttribute('aria-labelledby','chart-preview-title');document.body.append(previewDialog);
    previewDialog.addEventListener('pointerenter',()=>clearTimeout(previewCloseTimer));
    previewDialog.addEventListener('pointerleave',()=>{if(!previewPinned)previewCloseTimer=setTimeout(closeChartPreview,180);});
  }
  if(previewDialog.open)previewDialog.close();
  previewPinned=pinned;previewDialog.replaceChildren();
  const heading=node('div',undefined,'dialog-head'),title=node('h2',workout.name||'Workout-Verlauf');title.id='chart-preview-title';
  heading.append(title,button('Schließen',closeChartPreview));
  previewDialog.append(heading,powerZonePreview(workout,ftp,true),node('p','Leistung in Watt · Kadenz in rpm · Zeit in Minuten:Sekunden','chart-axis-description'));
  previewDialog.classList.toggle('hover-preview',!pinned);
  if(pinned)previewDialog.showModal();else previewDialog.show();
}
function expandableWorkoutPreview(workout,ftp) {
  const trigger=node('button',undefined,'preview-trigger');trigger.type='button';
  trigger.setAttribute('aria-label','Diagramm vergrößern: '+(workout.name||'Workout'));
  trigger.setAttribute('aria-haspopup','dialog');
  trigger.append(powerZonePreview(workout,ftp),node('span','Vergrößern ↗','preview-hint'));
  trigger.onclick=()=>showChartPreview(workout,ftp,true);
  trigger.addEventListener('pointerenter',()=>{
    if(matchMedia('(hover: hover) and (pointer: fine)').matches&&!trigger.closest('dialog')) {
      clearTimeout(previewCloseTimer);previewTimer=setTimeout(()=>showChartPreview(workout,ftp),500);
    }
  });
  trigger.addEventListener('pointerleave',()=>{
    clearTimeout(previewTimer);if(!previewPinned)previewCloseTimer=setTimeout(closeChartPreview,180);
  });
  return trigger;
}
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&previewDialog?.open){event.preventDefault();closeChartPreview();}});

function navigate(page) {
  closeChartPreview();
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
function renderSettings() {
  const profile=active('profile')[0]?.payload, form=$('#settings-form');
  form.elements.name.value=profile?.name||user?.name||'';
  form.elements.weight_kg.value=profile?.weight_kg??'';
  form.elements.ftp.value=profile?.ftp??active('settings')[0]?.payload.default_ftp??250;
  form.elements.max_hr.value=profile?.max_hr??'';
}
async function saveTrainingSettings(event) {
  event.preventDefault();const form=event.target,submit=form.querySelector('button');submit.disabled=true;
  try {
    const previous=active('profile')[0],id=previous?.id||crypto.randomUUID(),now=new Date().toISOString();
    const name=form.elements.name.value.trim();if(!name)throw Error('Bitte einen Benutzernamen eingeben.');
    const record={...(previous||{id,kind:'profile',revision:0,shared:false,deleted:false}),payload:{
      ...previous?.payload,id,name,ftp:Number(form.elements.ftp.value),weight_kg:Number(form.elements.weight_kg.value),
      max_hr:form.elements.max_hr.value===''?null:Number(form.elements.max_hr.value),
      created_at:previous?.payload.created_at||now,updated_at:now
    }};
    await save(record);renderLive();notice('Trainingswerte gespeichert. Vorschau und Leistungszonen sind aktualisiert.');
  } catch(error){notice(error.message,true);} finally{submit.disabled=false;}
}
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
  if(workout){dialog.append(workoutPreview(workout.payload,active('profile')[0]?.payload.ftp||250));actions.append(primaryButton('Training vorbereiten',()=>{dialog.close();openWorkout(workout,plan.id);}));}
  else dialog.append(node('p','Dieses Workout ist nicht mehr in deiner Bibliothek.','muted'));
  actions.append(button('Aus Kalender entfernen',async()=>{
    if(!confirm('Nur diese geplante Einheit aus dem Kalender entfernen? Das Workout bleibt in deiner Bibliothek.'))return;
    await save({...plan,deleted:true});dialog.close();notice('Geplante Einheit entfernt.');
  }));dialog.append(actions);dialog.showModal();
}

function workoutPublisher(record){
  return record.shared ? (record.publisher?.name ? 'Veröffentlicht von '+record.publisher.name : 'Veröffentlicht · Name nicht erfasst') : 'Privates Workout';
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
    card.append(meta,node('h2',p.name),node('p',workoutPublisher(record),'workout-publisher'),duration,node('p',p.description||'Dein strukturiertes Training.','workout-description'),workoutPreview(p,active('profile')[0]?.payload.ftp||250));
    const actions=node('div',undefined,'actions');
    actions.append(primaryButton('Training vorbereiten',()=>openWorkout(record)),button('Planen',()=>planWorkout(record)));
    card.append(actions);
    if(user.admin&&record.shared){
      const removeButton=button('Veröffentlichung löschen',()=>remove(record));
      removeButton.className='workout-delete quiet';removeButton.setAttribute('aria-label','Veröffentlichung löschen: '+p.name);card.append(removeButton);
    }
    list.append(card);
  }
  if(!shown.length){const empty=node('div',undefined,'empty');empty.append(node('h2',all.length?'Kein Treffer. Noch ein Versuch?':'Platz für dein erstes Workout.'),node('p',all.length?'Ändere die Suche oder wähle eine andere Kategorie.':'Importiere eine JSON- oder ZWO-Datei und lege los.'));list.append(empty);}
}


function renderSetupStatus() {
  const host=$('#setup-status');host.replaceChildren();
  for(const [label,ready,text] of [['Connector',connectorConnected,connectorConnected?'Verbunden':'Öffnen oder installieren'],['Trainer',connectorConnected&&liveData.trainer_connected,connectorConnected&&liveData.trainer_connected?(liveData.trainer_name||'Verbunden'):'Noch nicht verbunden']]) {
    const row=node('div',undefined,'setup-row');row.append(node('span',label));const value=node('strong',text,ready?'is-ready':'');row.append(value);host.append(row);
  }
  if(preparedWorkout && $('#workout-detail').open) {
    const ready=connectorConnected&&liveData.trainer_connected, busy=['running','paused','waiting_for_pedal'].includes(liveData.state);
    $('#workout-readiness').textContent=!connectorConnected?'Öffne CADOS Connector auf deinem Computer. Du kannst dieses Workout schon jetzt planen.':!liveData.trainer_connected?'Verbinde deinen eingeschalteten Trainer, um zu starten.':busy?'Ein Training ist bereits aktiv. Du kannst in die Trainingsansicht zurückkehren.':'Alles bereit. Dein Trainer ist verbunden.';
    $('#prepare-start').disabled=!ready||busy||pendingStart;$('#prepare-connect').hidden=!connectorConnected||!!liveData.trainer_connected;
  }
}

function openWorkout(record,planId=null) {
  selectedPlanId=planId;
  preparedWorkout=record;const p=record.payload,content=$('#workout-detail-content');content.replaceChildren();
  $('#workout-detail-title').textContent=p.name;
  content.append(node('p',workoutPublisher(record),'workout-publisher'));
  content.append(node('p',(p.category||'Workout')+' · '+durationOf(p)+' min','detail-meta'),node('p',p.description||'Dein strukturiertes Training.'),workoutPreview(p,active('profile')[0]?.payload.ftp||250));
  const ftpTest=isFTPRamp(p);$('#prepare-erg').disabled=ftpTest;
  $('#prepare-erg').value=ftpTest?'normal':$('#live-erg').value;
  if(ftpTest)content.append(node('p','FTP-Rampentest: normaler ERG ohne adaptive Entlastung. Wenn deine Kadenz im Belastungsteil auf 0 fällt, endet der Test automatisch. Du kannst ihn auch manuell beenden. Die Auswertung erscheint anschließend.','ftp-test-hint'));
  const manage=$('#workout-manage');manage.replaceChildren();
  const closeThen=action=>()=>{$('#workout-detail').close();return action();};
  manage.append(button(user.admin||!record.shared?'Workout bearbeiten':'Workout-Details',closeThen(()=>edit(record))),button('Kopieren',closeThen(()=>copy(record))),button('Exportieren',()=>download(record)));
  if(user.admin||!record.shared){const removeButton=button('Löschen',closeThen(()=>remove(record)));removeButton.classList.add('danger-text');manage.append(removeButton);}
  $('#workout-detail').showModal();renderSetupStatus();window.renderReadinessChecks?.();
}
$('#close-workout-detail').onclick=()=>$('#workout-detail').close();
$('#prepare-plan').onclick=()=>planWorkout(preparedWorkout);
$('#prepare-connect').onclick=()=>$('#connector-connect').click();
$('#prepare-start').onclick=()=>{
  if(!connectorConnected||!liveData.trainer_connected||pendingStart)return;
  try{$('#live-erg').value=$('#prepare-erg').value;startOnMac(preparedWorkout);$('#workout-detail').close();}
  catch(error){notice(error.message,true);}
};
$('#setup-open').onclick=()=>navigate('live');$('#all-sessions').onclick=()=>navigate('session');

const productLiveBase=renderLive;
renderLive=function(){
  productLiveBase();renderSetupStatus();
  const banner=$('#connector-download');if(banner)banner.hidden=connectorConnected||connectorInstalledHere||!['home','workout'].includes(currentPage);
  const running=['running','waiting_for_pedal'].includes(liveData.state), paused=liveData.state==='paused';
  $('#live-pause').disabled=!connectorConnected||!running;
  $('#live-resume').disabled=!connectorConnected||!paused||!liveData.trainer_connected;
  $('#live-stop').disabled=!connectorConnected||!(running||paused);
  $('#live-erg').disabled=!connectorConnected;
  $('#live-state').textContent=({idle:'Bereit',ready:'Bereit',running:'Training läuft',paused:'Pausiert',waiting_for_pedal:'Bereit zum Losfahren',stopped:'Beendet',completed:'Geschafft'})[liveData.state]||'Bereit';
};
const productShowDashboardBase=showDashboard;
showDashboard=function(){productShowDashboardBase();navigate('home');};
const productShowLoginBase=showLogin;
showLogin=function(){productShowLoginBase();liveData={};connectorVersion='';liveWorkout=null;liveHistory=[];preparedWorkout=null;serverConnected=false;lastTelemetryAt=0;selectedPlanId=null;pendingStart=false;pendingReview=null;reviewAttempt=0;document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());};

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
