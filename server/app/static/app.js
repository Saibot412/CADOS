"use strict";
const $ = s => document.querySelector(s);
let user, records = [], editing, managedUsers = [], calendarMonth = new Date().toISOString().slice(0,7), liveSocket, connectorConnected=false, liveData={}, connectorVersion='', connectorRelease,localSocket=null,localConnected=false;
const titles = {home:'Deine Übersicht',workout:'Workout-Bibliothek',live:'Live-Training',calendar:'Trainingskalender',session:'Trainingshistorie',settings:'Einstellungen',users:'Benutzerverwaltung'};
function notice(message, error=false){$('#notice').textContent=message;$('#notice').className=error?'error':'';$('#notice').hidden=false;}
async function api(path, options={}){
  let response;try{response=await fetch('/api/v1'+path,{...options,headers:{'Content-Type':'application/json','X-Cados-Request':'1',...options.headers}});}catch{throw Error('Der Server ist derzeit nicht erreichbar. Bitte prüfe deine Verbindung und versuche es erneut.');}
  let data;try{data=await response.json();}catch{throw Error('Ungültige Serverantwort');}
  if(!response.ok){if(response.status===401)showLogin();let detail=data.detail;throw Error(typeof detail==='string'?detail:detail?.message||'Bitte Eingaben prüfen und erneut versuchen.');}return data;
}
const post=(path,data)=>api(path,{method:'POST',body:JSON.stringify(data)});
function showLogin(){window.disconnectLocal?.();document.body.classList.remove('signed-in','live-focus-active');user=null;liveSocket?.close();liveSocket=null;connectorConnected=false;$('#login').hidden=false;$('#dashboard').hidden=true;$('#account').hidden=true;}
function showRegister(){ $('#login-form').hidden=true;$('#register-form').hidden=false;}
function showLoginForm(){ $('#register-form').hidden=true;$('#login-form').hidden=false;}
function showDashboard(){ document.body.classList.add('signed-in'); $('#login').hidden=true;$('#dashboard').hidden=false;$('#account').hidden=false;$('#email').textContent=user.email;$('#users-tab').hidden=!user.admin;$('#share-label').hidden=!user.admin;connectLive();loadConnectorRelease();}
function node(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function button(text,callback){const b=node('button',text,'quiet');b.type='button';b.onclick=()=>Promise.resolve().then(callback).catch(e=>notice(e.message,true));return b;}
function active(kind){return records.filter(r=>r.kind===kind&&!r.deleted);}
function compareVersion(first,second){const a=String(first).split('.').map(Number),b=String(second).split('.').map(Number);for(let i=0;i<Math.max(a.length,b.length);i++){const delta=(a[i]||0)-(b[i]||0);if(delta)return delta;}return 0;}
async function loadConnectorRelease(){try{const response=await fetch('/static/connector-release.json',{cache:'no-store'});if(!response.ok)throw Error();connectorRelease=await response.json();renderLive();}catch{connectorRelease=undefined;}}
function formatTime(seconds){seconds=Math.max(0,Number(seconds)||0);return Math.floor(seconds/60)+':'+String(Math.floor(seconds%60)).padStart(2,'0');}
function renderLive(){const d=liveData||{},update=connectorRelease&&connectorVersion&&compareVersion(connectorVersion,connectorRelease.version)<0;$('#connector-status').textContent=connectorConnected?'CADOS Connector verbunden'+(connectorVersion?' · Version '+connectorVersion:''):'CADOS Connector nicht verbunden';$('#connector-detail').textContent=connectorConnected?(d.trainer_connected?'Trainer: '+d.trainer_name:'Trainer noch nicht verbunden. Klicke auf „Trainer verbinden“.'):'Öffne CADOS Connector auf deinem Mac. Das Training läuft dort auch weiter, wenn das Internet kurz ausfällt.';$('#connector-update').hidden=!update;if(update){const updateLink=$('#connector-update-link');updateLink.href=connectorRelease.macos.url;updateLink.target='_blank';updateLink.rel='noopener';updateLink.textContent='Version '+connectorRelease.version+' herunterladen';}$('#connector-connect').disabled=!connectorConnected;$('#live-state').textContent=(d.state||'bereit').toUpperCase();$('#live-workout').textContent=d.workout_name||'Kein Training aktiv';$('#live-block').textContent=d.current_block_name||'Wähle ein Workout und starte es auf deinem Mac.';$('#live-power').textContent=d.current_watts!=null?Math.round(d.current_watts)+' W':'– W';$('#live-target').textContent='Ziel '+(d.target_watts!=null?Math.round(d.target_watts)+' W':'– W')+(d.adaptive_relief_watts?' · −'+d.adaptive_relief_watts+' W':'');$('#live-cadence').textContent=d.current_cadence!=null?Math.round(d.current_cadence)+' rpm':'– rpm';$('#live-target-cadence').textContent='Ziel '+(d.target_cadence!=null?Math.round(d.target_cadence)+' rpm':'– rpm');$('#live-hr').textContent=d.heart_rate?Math.round(d.heart_rate)+' bpm':'– bpm';$('#live-time').textContent=d.elapsed_sec!=null?formatTime(d.elapsed_sec)+' gefahren · '+formatTime(d.remaining_sec)+' offen':'–';$('#live-erg').value=d.adaptive_erg?'adaptive':'normal';}
function handleLiveMessage(message,local=false){
  if(message.local_access&&!local)window.offerLocalAccess?.(message.local_access);
  if(message.type==='devices'){window.receiveDevices?.(message);return;}
  if(message.type==='connector'){
    connectorConnected=!!message.connected||localConnected;
    if(message.connected&&liveSocket?.readyState===1)liveSocket.send(JSON.stringify({type:'command',command:{name:'snapshot'}}));
    if(!connectorConnected)lastTelemetryAt=0;
    renderLive();
  }else if(message.type==='status'){connectorVersion=message.version||connectorVersion;renderLive();}
  else if(message.type==='telemetry'){
    if(local||!localConnected)acceptTelemetry(message.payload||{});
  }else if(message.type==='recovery'){
    if(local||!localConnected){liveWorkout=message.payload.workout;liveHistory=message.payload.history||[];acceptTelemetry(message.payload.telemetry||{},true);}
  }else if(message.type==='error'){pendingStart=false;notice(message.message,true);renderLive();}
}
function connectLive(){
  if(liveSocket||!user)return;
  const socket=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/api/v1/live/browser');
  liveSocket=socket;
  socket.onopen=()=>{if(liveSocket!==socket)return;serverConnected=true;renderLive();};
  socket.onmessage=event=>{if(liveSocket===socket&&user)handleLiveMessage(JSON.parse(event.data));};
  socket.onclose=()=>{if(liveSocket!==socket)return;liveSocket=null;serverConnected=false;connectorConnected=localConnected;renderLive();if(user)setTimeout(connectLive,3000);};
}
function connectorCommand(command){
  // Starting a new workout still requires the server's current account/profile.
  const socket=localConnected&&!['start','update'].includes(command.name)?localSocket:liveSocket;
  if(!connectorConnected||!socket||socket.readyState!==WebSocket.OPEN)throw Error('Verbindung unterbrochen. Nutze die lokale Trainingsansicht oder das Connector-Fenster.');
  socket.send(JSON.stringify({type:'command',command}));
}
function startOnMac(record){
  if(pendingStart||isTrainingActive())return;
  connectorCommand({name:'start',workout:record.payload,plan_id:selectedPlanId,adaptive_erg:$('#live-erg').value==='adaptive'});
  pendingStart=true;setTimeout(()=>{if(pendingStart){pendingStart=false;notice('Start noch nicht bestätigt. Prüfe den Connector, bevor du erneut startest.',true);renderLive();}},10000);
  navigate('live');renderLive();
}

function metric(value,unit){return value==null?'–':Math.round(value)+' '+unit;}
function samplePoints(samples,key){let elapsed=0;return samples.flatMap(sample=>{const duration=Number(sample.duration_sec)||0;elapsed=Number.isFinite(Number(sample.elapsed_sec))?Number(sample.elapsed_sec):elapsed+duration;const value=Number(sample[key]);return Number.isFinite(value)?[[elapsed,value]]:[];});}
function chart(points,label,unit,color){const card=node('section',undefined,'card');card.append(node('h3',label));if(!points.length){card.append(node('p','Für dieses Training wurden keine '+label.toLowerCase()+'-Messwerte gespeichert.','muted'));return card;}const limit=500,step=Math.ceil(points.length/limit),shown=points.filter((_,index)=>index%step===0||index===points.length-1),last=shown.at(-1)[0]||1,max=Math.max(1,...shown.map(point=>point[1])),width=720,height=190,pad=30;const coords=shown.map(([x,y])=>(pad+(x/last)*(width-pad*2)).toFixed(1)+','+(height-pad-(y/max)*(height-pad*2)).toFixed(1)).join(' ');const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 '+width+' '+height);svg.setAttribute('width','100%');svg.setAttribute('role','img');svg.setAttribute('aria-label',label+' über die Trainingsdauer');svg.innerHTML='<line x1="'+pad+'" y1="'+(height-pad)+'" x2="'+(width-pad)+'" y2="'+(height-pad)+'" stroke="#cbd8df"/><line x1="'+pad+'" y1="'+pad+'" x2="'+pad+'" y2="'+(height-pad)+'" stroke="#cbd8df"/><polyline points="'+coords+'" fill="none" stroke="'+color+'" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/><text x="'+pad+'" y="18" fill="#657b8b" font-size="12">'+Math.round(max)+' '+unit+'</text><text x="'+(width-pad)+'" y="'+(height-8)+'" text-anchor="end" fill="#657b8b" font-size="12">'+Math.round(last/60)+' min</text>';svgText(svg,'Zeit (min)',width/2,height-8,{'text-anchor':'middle',fill:'#657b8b','font-size':'12'});svgText(svg,'0',pad,height-8,{fill:'#657b8b','font-size':'12'});card.append(svg);return card;}
function workoutPreview(workout,ftp){return expandableWorkoutPreview(workout,ftp);}

function renderUsers(){const list=$('#users');if(!user?.admin)return;list.replaceChildren();const table=node('table'),head=node('tr');['E-Mail','Rolle','Status','Aktionen'].forEach(label=>head.append(node('th',label)));table.append(head);for(const member of managedUsers){const row=node('tr');[member.email,member.admin?'Administrator':'Benutzer',member.active?'Aktiv':'Deaktiviert'].forEach(value=>row.append(node('td',value)));const actions=node('td');if(member.id===user.id)actions.append(node('span','Eigenes Konto','muted'));else{actions.append(button(member.active?'Deaktivieren':'Aktivieren',()=>setUserStatus(member,!member.active)),button('Löschen',()=>deleteUser(member)));}row.append(actions);table.append(row);}list.append(table);}
function dayKey(value){return localDate(new Date(value));}
function renderCalendar(){const first=new Date(calendarMonth+'-01T12:00:00'),year=first.getFullYear(),month=first.getMonth(),days=new Date(year,month+1,0).getDate(),offset=(first.getDay()+6)%7,grid=$('#calendar');$('#calendar-title').textContent=new Intl.DateTimeFormat('de-AT',{month:'long',year:'numeric'}).format(first);grid.replaceChildren();const calendar=node('div',undefined,'calendar-grid');['Mo','Di','Mi','Do','Fr','Sa','So'].forEach(label=>calendar.append(node('div',label,'calendar-weekday')));for(let index=0;index<offset+days;index++){const cell=node('div',undefined,'calendar-day'+(index<offset?' empty':''));if(index>=offset){const day=index-offset+1,key=calendarMonth+'-'+String(day).padStart(2,'0');cell.append(node('div',String(day),'calendar-date'));if(key===localDate())cell.classList.add('today');for(const plan of active('plan').filter(record=>record.payload.date===key&&!planCompleted(record))){const entry=button('Geplant: '+plan.payload.workout_name,()=>openPlan(plan));entry.classList.add('calendar-entry','planned');cell.append(entry);}for(const session of active('session').filter(record=>dayKey(record.payload.timestamp)===key)){const entry=button('Gefahren: '+session.payload.workout_name,()=>showSession(session));entry.classList.add('calendar-entry','completed');cell.append(entry);}}calendar.append(cell);}grid.append(calendar);const select=$('#plan-workout'),previous=select.value;select.replaceChildren();for(const workout of active('workout').sort((a,b)=>a.payload.name.localeCompare(b.payload.name))){const option=node('option',workout.payload.name);option.value=workout.id;select.append(option);}if([...select.options].some(option=>option.value===previous))select.value=previous;$('#plan-form').elements.date.value ||=new Date().toISOString().slice(0,10);}
async function reloadUsers(){managedUsers=(await api('/users')).users;renderUsers();}
async function setUserStatus(member,active){await api('/users/'+member.id,{method:'PATCH',body:JSON.stringify({active})});await reloadUsers();notice(active?'Benutzer aktiviert.':'Benutzer deaktiviert und abgemeldet.');}
async function deleteUser(member){if(confirm('Benutzer „'+member.email+'“ inklusive aller privaten Trainingsdaten endgültig löschen?')){await api('/users/'+member.id,{method:'DELETE'});await reloadUsers();notice('Benutzer gelöscht.');}}
async function reload(){
 const account=user?.id;setDataLoading(true);
 try{const result=await api('/sync');if(user?.id!==account)return;records=result.records;render();}
 finally{setDataLoading(false);}
}
function render(){
 renderWorkoutLibrary();
 renderOverview();
 renderSettings();
 const sessions=$('#sessions');sessions.replaceChildren();const table=node('table');const head=node('tr');['Datum','Workout','Dauer','Status','Verlauf'].forEach(t=>head.append(node('th',t)));table.append(head);
 for(const r of active('session').sort((a,b)=>b.payload.timestamp.localeCompare(a.payload.timestamp))){const row=node('tr'),p=r.payload;[new Date(p.timestamp).toLocaleDateString('de-AT'),p.workout_name,Math.round(p.duration_sec/60)+' min',sessionStatus(p.status)].forEach(t=>row.append(node('td',t)));const action=node('td');action.append(button('Ansehen',()=>showSession(r)));row.append(action);table.append(row);}sessions.append(active('session').length?table:node('p','Hier erscheinen deine absolvierten Trainings nach der Synchronisation.','empty'));

 renderCalendar();
}
async function save(record){await post('/sync',{changes:[record]});await reload();notice('Gespeichert. Deine Änderungen sind mit deinem Konto synchronisiert.');}
async function remove(r){
 const message=r.shared?'„'+r.payload.name+'“ für alle aus der Workout-Bibliothek entfernen? Bereits gefahrene Trainings bleiben erhalten.':'„'+r.payload.name+'“ löschen? Bereits gefahrene Trainings bleiben erhalten.';
 if(confirm(message)){await save({...r,deleted:true});notice(r.shared?'Veröffentlichung aus der Bibliothek entfernt.':'Workout gelöscht.');}
}
async function copy(r){await save({...r,id:crypto.randomUUID(),revision:0,shared:!!(user.admin&&$('#share').checked),payload:{...r.payload,name:r.payload.name+' (Kopie)',source_name:crypto.randomUUID()+'.json'}});}
function download(r){const blob=new Blob([JSON.stringify(r.payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=r.payload.source_name||'workout.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function field(parent,label,key,value,type='text'){const l=node('label',label),input=node(type==='textarea'?'textarea':'input');if(type!=='textarea')input.type=type;input.name=key;input.value=value??'';l.append(input);parent.append(l);return input;}
function edit(r){if(r.kind==='workout'){openWorkoutBuilder(r);return;}editing=structuredClone(r);const fields=$('#edit-fields');fields.replaceChildren();$('#edit-title').textContent=r.kind==='profile'?'Profil bearbeiten':'Workout ansehen & bearbeiten';
 field(fields,'Name','name',r.payload.name);if(r.kind==='profile'){field(fields,'FTP (W)','ftp',r.payload.ftp,'number');field(fields,'Gewicht (kg)','weight_kg',r.payload.weight_kg,'number').step='0.1';field(fields,'Maximale Herzfrequenz','max_hr',r.payload.max_hr,'number');}
 else{field(fields,'Beschreibung','description',r.payload.description,'textarea');field(fields,'Kategorie','category',r.payload.category);field(fields,'Sortierung','sort_order',r.payload.sort_order||0,'number');const blocks=node('div');r.payload.blocks.forEach((b,i)=>{const box=node('div',undefined,'block');box.append(node('strong',(i+1)+'. '+(b.label||b.type)));field(box,'Sekunden','duration_'+i,b.duration_sec,'number');for(const key of ['target_pct_ftp','target_watts','start_pct_ftp','end_pct_ftp','start_watts','end_watts','target_cadence'])if(b[key]!=null){const input=field(box,({target_pct_ftp:'Ziel-Leistung (FTP-Faktor)',target_watts:'Ziel-Leistung (W)',start_pct_ftp:'Start (FTP-Faktor)',end_pct_ftp:'Ende (FTP-Faktor)',start_watts:'Start-Leistung (W)',end_watts:'End-Leistung (W)',target_cadence:'Ziel-Kadenz (rpm)'})[key],'block_'+i+'_'+key,b[key],'number');input.step='any';}blocks.append(box);});fields.append(blocks);}
 const readonly=r.shared&&!user.admin;fields.querySelectorAll('input,textarea').forEach(e=>e.disabled=readonly);$('#save-edit').hidden=readonly;$('#editor').showModal();}
$('#edit-form').onsubmit=async e=>{e.preventDefault();try{const data=new FormData(e.target),p=editing.payload;p.name=data.get('name');if(editing.kind==='profile'){for(const k of ['ftp','weight_kg','max_hr'])p[k]=data.get(k)===''?null:Number(data.get(k));p.updated_at=new Date().toISOString();}else{p.description=data.get('description');p.category=data.get('category');p.sort_order=Number(data.get('sort_order'));p.blocks.forEach((b,i)=>{b.duration_sec=Number(data.get('duration_'+i));for(const key of Object.keys(b))if(data.has('block_'+i+'_'+key))b[key]=Number(data.get('block_'+i+'_'+key));});}await save(editing);$('#editor').close();}catch(e){notice(e.message,true);}};
$('#close-editor').onclick=()=>$('#editor').close();
$('#close-session').onclick=()=>$('#session-detail').close();
$('#login-form').onsubmit=async e=>{e.preventDefault();const submit=e.target.querySelector('button');submit.disabled=true;try{user=(await post('/auth/login',Object.fromEntries(new FormData(e.target)))).user;e.target.reset();showDashboard();await reload();$('#notice').hidden=true;}catch(e){notice(e.message,true);}finally{submit.disabled=false;}};
$('#show-register').onclick=showRegister;$('#show-login').onclick=showLoginForm;
$('#register-form').onsubmit=async e=>{e.preventDefault();const submit=e.target.querySelector('button');const data=Object.fromEntries(new FormData(e.target));if(data.password!==data.password_confirmation){notice('Die Passwörter stimmen nicht überein.',true);return;}submit.disabled=true;try{await post('/auth/register',data);e.target.reset();showLoginForm();notice('Konto erstellt. Du kannst dich jetzt anmelden.');}catch(e){notice(e.message,true);}finally{submit.disabled=false;}};
$('#logout').onclick=async()=>{try{await post('/auth/logout',{});showLogin();records=[];$('#notice').hidden=true;}catch(e){notice(e.message,true);}};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>navigate(b.dataset.tab));
$('#previous-month').onclick=()=>{const month=new Date(calendarMonth+'-01T12:00:00');month.setMonth(month.getMonth()-1);calendarMonth=month.toISOString().slice(0,7);renderCalendar();};$('#next-month').onclick=()=>{const month=new Date(calendarMonth+'-01T12:00:00');month.setMonth(month.getMonth()+1);calendarMonth=month.toISOString().slice(0,7);renderCalendar();};
$('#connector-connect').onclick=()=>{try{connectorCommand({name:'connect'});notice('Suche nach Trainer und Herzfrequenzsensor gestartet.');}catch(e){notice(e.message,true);}};
$('#live-pause').onclick=()=>{try{connectorCommand({name:'pause'});}catch(e){notice(e.message,true);}};$('#live-resume').onclick=()=>{try{connectorCommand({name:'resume'});}catch(e){notice(e.message,true);}};$('#live-stop').onclick=()=>{try{if(confirm('Training jetzt beenden? Die gefahrene Einheit wird gespeichert.'))connectorCommand({name:'stop'});}catch(e){notice(e.message,true);}};$('#live-erg').onchange=e=>{try{connectorCommand({name:'erg_mode',adaptive_erg:e.target.value==='adaptive'});}catch(error){notice(error.message,true);}};
$('#refresh').onclick=()=>reload().then(()=>notice('Daten aktualisiert.')).catch(e=>notice(e.message,true));$('#search').oninput=render;
$('#import').onclick=()=>$('#file').click();$('#file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>2000000)throw Error('Bitte eine Datei bis 2 MB auswählen.');await api('/import?filename='+encodeURIComponent(file.name)+'&shared='+!!(user.admin&&$('#share').checked),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});await reload();notice('Workout importiert.');}catch(e){notice(e.message,true);}finally{e.target.value='';}};
$('#settings-form').onsubmit=event=>saveTrainingSettings(event);
$('#plan-form').onsubmit=async e=>{e.preventDefault();try{const workout=active('workout').find(record=>record.id===e.target.elements.workout_id.value);if(!workout)throw Error('Bitte ein Workout auswählen.');const plan={id:crypto.randomUUID(),kind:'plan',revision:0,shared:false,deleted:false,payload:{workout_id:workout.id,workout_name:workout.payload.name,date:e.target.elements.date.value}};calendarMonth=plan.payload.date.slice(0,7);await save(plan);notice('Training geplant.');}catch(e){notice(e.message,true);}};
$('#user-form').onsubmit=async e=>{e.preventDefault();try{await post('/users',Object.fromEntries(new FormData(e.target)));e.target.reset();await reloadUsers();notice('Benutzerkonto angelegt.');}catch(e){notice(e.message,true);}};
$('#password-form').onsubmit=async e=>{e.preventDefault();if(e.target.elements.password.value!==e.target.elements.password_confirmation.value){notice('Die Passwörter stimmen nicht überein.',true);return;}try{await post('/auth/password',{email:user.email,password:e.target.elements.password.value});e.target.reset();showLogin();notice('Passwort geändert. Bitte neu anmelden.');}catch(e){notice(e.message,true);}};
