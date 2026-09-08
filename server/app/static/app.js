"use strict";
const $ = s => document.querySelector(s);
let user, records = [], editing;
const titles = {workout:'Workout-Bibliothek',profile:'Mein Profil',session:'Trainingshistorie',settings:'Einstellungen',users:'Benutzerverwaltung'};
function notice(message, error=false){$('#notice').textContent=message;$('#notice').className=error?'error':'';$('#notice').hidden=false;}
async function api(path, options={}){
  const response=await fetch('/api/v1'+path,{...options,headers:{'Content-Type':'application/json','X-Cados-Request':'1',...options.headers}});
  let data;try{data=await response.json();}catch{throw Error('Ungültige Serverantwort');}
  if(!response.ok){if(response.status===401)showLogin();let detail=data.detail;throw Error(typeof detail==='string'?detail:detail?.message||'Bitte Eingaben prüfen und erneut versuchen.');}return data;
}
const post=(path,data)=>api(path,{method:'POST',body:JSON.stringify(data)});
function showLogin(){user=null;$('#login').hidden=false;$('#dashboard').hidden=true;$('#account').hidden=true;}
function showRegister(){ $('#login-form').hidden=true;$('#register-form').hidden=false;}
function showLoginForm(){ $('#register-form').hidden=true;$('#login-form').hidden=false;}
function showDashboard(){ $('#login').hidden=true;$('#dashboard').hidden=false;$('#account').hidden=false;$('#email').textContent=user.email;$('#users-tab').hidden=!user.admin;$('#share-label').hidden=!user.admin;}
function node(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function button(text,callback){const b=node('button',text,'quiet');b.type='button';b.onclick=()=>Promise.resolve().then(callback).catch(e=>notice(e.message,true));return b;}
function active(kind){return records.filter(r=>r.kind===kind&&!r.deleted);}
async function reload(){records=(await api('/sync')).records;render();}
function render(){
 const list=$('#workouts');list.replaceChildren();const search=$('#search').value.toLocaleLowerCase();
 for(const r of active('workout').filter(r=>(r.payload.name+' '+r.payload.category).toLocaleLowerCase().includes(search)).sort((a,b)=>(a.payload.sort_order||0)-(b.payload.sort_order||0)||a.payload.name.localeCompare(b.payload.name))){
   const p=r.payload,card=node('article',undefined,'card workout-card');card.append(node('span',(p.category||'Workout')+' · '+(r.shared?'Gemeinsam':'Privat'),'tag'),node('h2',p.name),node('div',Math.round(p.blocks.reduce((n,b)=>n+b.duration_sec,0)/60)+' min','duration'),node('p',p.description||'Dein strukturiertes Training.'));
   const actions=node('div',undefined,'actions');actions.append(button(user.admin||!r.shared?'Ansehen & bearbeiten':'Ansehen',()=>edit(r)),button('Kopieren',()=>copy(r)),button('Exportieren',()=>download(r)));
   if(user.admin||!r.shared)actions.append(button('Löschen',()=>remove(r)));card.append(actions);list.append(card);
 }if(!list.children.length)list.append(node('p','Keine passenden Workouts. Importiere dein erstes Training.','empty'));
 const profiles=$('#profiles');profiles.replaceChildren();for(const r of active('profile')){const card=node('article',undefined,'card');card.append(node('h2',r.payload.name),node('div',r.payload.ftp+' W FTP','duration'),button('Bearbeiten',()=>edit(r)));profiles.append(card);}
 const sessions=$('#sessions');sessions.replaceChildren();const table=node('table');const head=node('tr');['Datum','Workout','Dauer','Status'].forEach(t=>head.append(node('th',t)));table.append(head);
 for(const r of active('session').sort((a,b)=>b.payload.timestamp.localeCompare(a.payload.timestamp))){const row=node('tr'),p=r.payload;[new Date(p.timestamp).toLocaleDateString('de-AT'),p.workout_name,Math.round(p.duration_sec/60)+' min',p.status].forEach(t=>row.append(node('td',t)));table.append(row);}sessions.append(active('session').length?table:node('p','Hier erscheinen deine absolvierten Trainings nach der Synchronisation.','empty'));
 $('#settings-form').elements.default_ftp.value=active('settings')[0]?.payload.default_ftp||250;
}
async function save(record){await post('/sync',{changes:[record]});await reload();notice('Gespeichert. Deine Desktop-App übernimmt die Änderung beim Synchronisieren.');}
async function remove(r){if(confirm('„'+r.payload.name+'“ löschen? Bereits gefahrene Trainings bleiben erhalten.'))await save({...r,deleted:true});}
async function copy(r){await save({...r,id:crypto.randomUUID(),revision:0,shared:!!(user.admin&&$('#share').checked),payload:{...r.payload,name:r.payload.name+' (Kopie)',source_name:crypto.randomUUID()+'.json'}});}
function download(r){const blob=new Blob([JSON.stringify(r.payload,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=r.payload.source_name||'workout.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function field(parent,label,key,value,type='text'){const l=node('label',label),input=node(type==='textarea'?'textarea':'input');if(type!=='textarea')input.type=type;input.name=key;input.value=value??'';l.append(input);parent.append(l);return input;}
function edit(r){editing=structuredClone(r);const fields=$('#edit-fields');fields.replaceChildren();$('#edit-title').textContent=r.kind==='profile'?'Profil bearbeiten':'Workout ansehen & bearbeiten';
 field(fields,'Name','name',r.payload.name);if(r.kind==='profile'){field(fields,'FTP (W)','ftp',r.payload.ftp,'number');field(fields,'Gewicht (kg)','weight_kg',r.payload.weight_kg,'number').step='0.1';field(fields,'Maximale Herzfrequenz','max_hr',r.payload.max_hr,'number');}
 else{field(fields,'Beschreibung','description',r.payload.description,'textarea');field(fields,'Kategorie','category',r.payload.category);field(fields,'Sortierung','sort_order',r.payload.sort_order||0,'number');const blocks=node('div');r.payload.blocks.forEach((b,i)=>{const box=node('div',undefined,'block');box.append(node('strong',(i+1)+'. '+(b.label||b.type)));field(box,'Sekunden','duration_'+i,b.duration_sec,'number');for(const key of ['target_pct_ftp','target_watts','start_pct_ftp','end_pct_ftp','start_watts','end_watts','target_cadence'])if(b[key]!=null){const input=field(box,key.replaceAll('_',' '),'block_'+i+'_'+key,b[key],'number');input.step='any';}blocks.append(box);});fields.append(blocks);}
 const readonly=r.shared&&!user.admin;fields.querySelectorAll('input,textarea').forEach(e=>e.disabled=readonly);$('#save-edit').hidden=readonly;$('#editor').showModal();}
$('#edit-form').onsubmit=async e=>{e.preventDefault();try{const data=new FormData(e.target),p=editing.payload;p.name=data.get('name');if(editing.kind==='profile'){for(const k of ['ftp','weight_kg','max_hr'])p[k]=data.get(k)===''?null:Number(data.get(k));p.updated_at=new Date().toISOString();}else{p.description=data.get('description');p.category=data.get('category');p.sort_order=Number(data.get('sort_order'));p.blocks.forEach((b,i)=>{b.duration_sec=Number(data.get('duration_'+i));for(const key of Object.keys(b))if(data.has('block_'+i+'_'+key))b[key]=Number(data.get('block_'+i+'_'+key));});}await save(editing);$('#editor').close();}catch(e){notice(e.message,true);$('#editor').close();}};
$('#close-editor').onclick=()=>$('#editor').close();
$('#login-form').onsubmit=async e=>{e.preventDefault();const submit=e.target.querySelector('button');submit.disabled=true;try{user=(await post('/auth/login',Object.fromEntries(new FormData(e.target)))).user;e.target.reset();showDashboard();await reload();$('#notice').hidden=true;}catch(e){notice(e.message,true);}finally{submit.disabled=false;}};
$('#show-register').onclick=showRegister;$('#show-login').onclick=showLoginForm;
$('#register-form').onsubmit=async e=>{e.preventDefault();const submit=e.target.querySelector('button');const data=Object.fromEntries(new FormData(e.target));if(data.password!==data.password_confirmation){notice('Die Passwörter stimmen nicht überein.',true);return;}submit.disabled=true;try{await post('/auth/register',data);e.target.reset();showLoginForm();notice('Konto erstellt. Du kannst dich jetzt anmelden.');}catch(e){notice(e.message,true);}finally{submit.disabled=false;}};
$('#logout').onclick=async()=>{try{await post('/auth/logout',{});showLogin();records=[];}catch(e){notice(e.message,true);}};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(n=>n.className='quiet');b.className='';for(const key of Object.keys(titles))$('#'+key+'-panel').hidden=key!==b.dataset.tab;$('#page-title').textContent=titles[b.dataset.tab];});
$('#refresh').onclick=()=>reload().then(()=>notice('Daten aktualisiert.')).catch(e=>notice(e.message,true));$('#search').oninput=render;
$('#import').onclick=()=>$('#file').click();$('#file').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>2000000)throw Error('Bitte eine Datei bis 2 MB auswählen.');await api('/import?filename='+encodeURIComponent(file.name)+'&shared='+!!(user.admin&&$('#share').checked),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});await reload();notice('Workout importiert.');}catch(e){notice(e.message,true);}finally{e.target.value='';}};
$('#new-profile').onclick=()=>{const id=crypto.randomUUID();edit({id,kind:'profile',revision:0,shared:false,deleted:false,payload:{id,name:'Mein Profil',ftp:250,created_at:new Date().toISOString()}});};
$('#settings-form').onsubmit=async e=>{e.preventDefault();try{const r=active('settings')[0]||{id:crypto.randomUUID(),kind:'settings',revision:0,shared:false,deleted:false};await save({...r,payload:{default_ftp:Number(e.target.elements.default_ftp.value)}});}catch(e){notice(e.message,true);}};
$('#user-form').onsubmit=async e=>{e.preventDefault();try{await post('/users',Object.fromEntries(new FormData(e.target)));e.target.reset();notice('Benutzerkonto angelegt.');}catch(e){notice(e.message,true);}};
$('#password-form').onsubmit=async e=>{e.preventDefault();try{await post('/auth/password',{email:user.email,password:e.target.elements.password.value});e.target.reset();showLogin();notice('Passwort geändert. Bitte neu anmelden.');}catch(e){notice(e.message,true);}};
api('/auth/me').then(async u=>{user=u;showDashboard();await reload();}).catch(e=>{if(user)notice(e.message,true);});
