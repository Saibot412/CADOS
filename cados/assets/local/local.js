'use strict';
const $=s=>document.querySelector(s);
let token=location.hash.slice(1);
try{if(token)sessionStorage.setItem('cados.local.token',token);else token=sessionStorage.getItem('cados.local.token')||'';}catch{}
history.replaceState(null,'','/');
let socket,workout,historyPoints=[],data={},last=0;
const duration=v=>Math.floor(v/60)+':'+String(Math.floor(v%60)).padStart(2,'0');
function command(name,extra={}){if(socket?.readyState===1)socket.send(JSON.stringify({command:{name,...extra}}));}
function connect(){
 socket=new WebSocket('ws://127.0.0.1:48732/live');
 socket.onopen=()=>socket.send(JSON.stringify({token}));
 socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='recovery'){workout=m.payload.workout;historyPoints=m.payload.history||[];render(m.payload.telemetry);}else if(m.type==='telemetry')render(m.payload);else if(m.type==='devices')renderDevices(m);else if(m.type==='error')$('#notice').textContent=m.message;};
 socket.onclose=()=>{$('#connection').textContent='Connector getrennt – Werte eingefroren';document.querySelectorAll('button,select').forEach(b=>b.disabled=true);if(token)setTimeout(connect,3000);};
}
function render(d){
 data=d;last=Date.now();$('#connection').textContent=d.server_connected?'Lokal verbunden · Server erreichbar':'Lokal verbunden · ohne Internet';
 $('#name').textContent=d.workout_name||'Bereit';$('#state').textContent=({running:'Training läuft',paused:'Pausiert',waiting_for_pedal:'Warte auf Treten',completed:'Abgeschlossen',stopped:'Beendet'})[d.state]||'Bereit';
 $('#power').textContent=(d.current_watts??'–')+' W';$('#target').textContent='Ziel '+(d.target_watts??'–')+' W';$('#cadence').textContent=(d.current_cadence??'–')+' rpm';$('#target-cadence').textContent='Ziel '+(d.target_cadence??'–')+' rpm';$('#hr').textContent=d.heart_rate?d.heart_rate+' bpm':'–';$('#time').textContent=duration(d.elapsed_sec||0);
 const active=['running','paused','waiting_for_pedal'].includes(d.state);
 document.querySelectorAll('[data-command]').forEach(b=>{const n=b.dataset.command;b.hidden=['restore','save_recovered'].includes(n)&&!d.recovery_available;b.disabled=n==='pause'?d.state!=='running':n==='resume'?d.state!=='paused'||!d.trainer_connected:n==='stop'?!active:false;});
 $('#erg').disabled=!active||d.ftp_test;$('#erg').value=String(!!d.adaptive_erg);
 if(d.recovery_available)$('#notice').textContent='Unterbrochene Einheit: '+d.recovery_available.name;
 else if(d.session_id)$('#notice').textContent=d.sync_pending?'Einheit lokal gespeichert. Synchronisierung folgt.':'Einheit gespeichert und synchronisiert.';
 if(d.state==='running'&&historyPoints.at(-1)?.elapsed!==d.elapsed_sec)historyPoints.push({elapsed:d.elapsed_sec,watts:d.current_watts,cadence:d.current_cadence});
 draw();
}
function draw(){
 const blocks=workout?.blocks||[],ftp=data.ftp_watts||250,targets=[],cadences=[];let total=0;
 const watts=(b,end)=>b.type==='ramp'?(b[(end?'end':'start')+'_pct_ftp']!=null?b[(end?'end':'start')+'_pct_ftp']*ftp:b[(end?'end':'start')+'_watts']||0):(b.target_pct_ftp!=null?b.target_pct_ftp*ftp:b.target_watts||0);
 for(const b of blocks){targets.push([total,watts(b,false)],[total+Number(b.duration_sec),watts(b,true)]);if(b.target_cadence)cadences.push([[total,b.target_cadence],[total+Number(b.duration_sec),b.target_cadence]]);total+=Number(b.duration_sec);}
 total=Math.max(total,data.elapsed_sec||0,1);const max=Math.max(100,...targets.map(p=>p[1]),...historyPoints.map(p=>p.watts||0))*1.1;
 const svg=$('#chart');svg.replaceChildren();const elem=(tag,attrs,text)=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text)e.textContent=text;svg.append(e);};
 for(let i=0;i<=4;i++){const y=265-i*58;elem('line',{x1:55,x2:945,y1:y,y2:y,stroke:'#e2e9e4'});elem('text',{x:2,y},Math.round(max*i/4)+' W');elem('text',{x:950,y},Math.round(160*i/4)+' rpm');elem('text',{x:55+i*220,y:290},duration(total*i/4));}
 const line=(points,scale,color,dash)=>elem('polyline',{points:points.map(([x,y])=>(55+x/total*890)+','+(265-y/scale*232)).join(' '),fill:'none',stroke:color,'stroke-width':2,'stroke-dasharray':dash||''});
 line(targets,max,'#84978e');cadences.forEach(p=>line(p,160,'#a184c4','5 4'));
 const step=Math.max(1,Math.ceil(historyPoints.length/1800)),shown=historyPoints.filter((_,i)=>i%step===0||i===historyPoints.length-1);line(shown.map(p=>[p.elapsed,p.watts]),max,'#087961');line(shown.map(p=>[p.elapsed,p.cadence]),160,'#8050b0');
}
for(const b of document.querySelectorAll('[data-command]'))b.onclick=()=>{if(b.dataset.command==='stop'&&!confirm('Training beenden und speichern?'))return;command(b.dataset.command);};
$('#erg').onchange=()=>command('erg_mode',{adaptive_erg:$('#erg').value==='true'});
setInterval(()=>{if(last&&Date.now()-last>5000){$('#connection').textContent='Keine aktuellen Messwerte';document.querySelectorAll('button,select').forEach(b=>b.disabled=true);}},1000);
if(token)connect();else $('#notice').textContent='Bitte diese Ansicht über den Connector öffnen.';

function renderDevices(message){
 const host=$('#devices');host.replaceChildren();
 for(const [kind,label] of [['trainer','Trainer'],['hr','Herzfrequenz']]){
  const title=document.createElement('h3');title.textContent=label;host.append(title);
  for(const device of message.payload[kind]||[]){const b=document.createElement('button');b.textContent=device.name+' · '+device.protocol;b.disabled=kind==='trainer'&&['running','paused','waiting_for_pedal'].includes(data.state);b.onclick=()=>command('select_device',{kind,identifier:device.identifier});host.append(b);}
  if(message.preferences?.[kind]){const b=document.createElement('button');b.textContent=label+' trennen und vergessen';b.onclick=()=>command('disconnect_device',{kind});host.append(b);}
 }
}
$('#scan-devices').onclick=()=>command('scan_devices');
