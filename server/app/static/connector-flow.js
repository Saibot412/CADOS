'use strict';
let localAccess=null,localRetry=null,pairShown=false;
const pairingCode=new URLSearchParams(location.search).get('pair');
window.disconnectLocal=function(){
 clearTimeout(localRetry);localConnected=false;localAccess=null;
 const socket=localSocket;localSocket=null;socket?.close();
};
window.offerLocalAccess=function(access){
 if(!user||access.port!==48732||typeof access.token!=='string')return;
 if(localAccess?.token!==access.token){window.disconnectLocal();localAccess=access;}
 if(!localSocket)connectLocal();
};
function connectLocal(){
 if(!localAccess||!user||localSocket)return;
 let socket;
 try{socket=new WebSocket('ws://127.0.0.1:48732/live');}catch{return;}
 localSocket=socket;
 const timeout=setTimeout(()=>{if(!localConnected)socket.close();},5000);
 socket.onopen=()=>socket.send(JSON.stringify({token:localAccess.token}));
 socket.onmessage=e=>{
  if(socket!==localSocket||!user)return;
  clearTimeout(timeout);localConnected=true;connectorConnected=true;
  handleLiveMessage(JSON.parse(e.data),true);
 };
 socket.onclose=()=>{
  clearTimeout(timeout);if(socket!==localSocket)return;
  localSocket=null;localConnected=false;
  if(!serverConnected)connectorConnected=false;
  renderLive();if(user&&localAccess)localRetry=setTimeout(connectLocal,5000);
 };
}
function showPairing(){
 if(!user||!pairingCode||pairShown)return;
 pairShown=true;
 const dialog=node('dialog'),title=node('h2','Connector mit deinem Konto verbinden?');
 dialog.append(title,node('p','Konto: '+user.email),node('p','Bestätige nur, wenn du die Kopplung gerade im CADOS Connector gestartet hast.'),node('small','Kennung: '+pairingCode));
 dialog.append(button('Connector verbinden',async()=>{
  await post('/connector/pair/approve',{code:pairingCode});
  history.replaceState(null,'',location.pathname);dialog.close();dialog.remove();notice('Bestätigt. Der Connector verbindet sich automatisch.');
 }),button('Abbrechen',()=>{history.replaceState(null,'',location.pathname);dialog.close();dialog.remove();}));
 document.body.append(dialog);dialog.showModal();
}
window.requestConnectorUpdate=function(){
 if(isTrainingActive()||liveData.recovery_available){notice('Bitte das Training vor dem Update beenden oder speichern.',true);return;}
 if(connectorConnected&&compareVersion(connectorVersion||'0.0.0','0.4.0')>=0){
  if(confirm('Connector aktualisieren? Er wird nach dem Download beendet und neu geöffnet.')){
   try{connectorCommand({name:'update'});notice('Update wird im Connector heruntergeladen und geprüft.');}catch(e){notice(e.message,true);}
  }
 }else window.open(connectorRelease?.macos?.url,'_blank','noopener');
};
const flowRenderLive=renderLive;
renderLive=function(){
 flowRenderLive();showPairing();
 let panel=$('#connector-help');
 if(!panel){
  panel=node('section',undefined,'card connector-help');panel.id='connector-help';
  const heading=node('h3','Dein Connector'),actions=node('div',undefined,'connector-actions');
  const pairing=button('Mit diesem Konto koppeln',()=>{location.href='cados-connector://pair';});
  const local=button('Lokale Trainingsansicht',()=>{
   if(localAccess)window.open('http://127.0.0.1:48732/#'+encodeURIComponent(localAccess.token),'_blank','noopener');
   else notice('Öffne die lokale Trainingsansicht im Connector-Fenster.');
  });local.id='open-local-training';
  const update=button('Connector aktualisieren',window.requestConnectorUpdate);update.id='update-connector-action';
  actions.append(pairing,local,update);
  const status=node('p');status.id='local-link-status';
  const instructions=node('details'),summary=node('summary','Installation auf dem Mac');
  instructions.append(summary,node('p','1. DMG herunterladen und öffnen. 2. CADOS Connector auf Programme ziehen. 3. App öffnen und im Browser koppeln.'),node('p','Falls macOS das Öffnen blockiert: Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen. CADOS ist ohne Apple-Developer-Konto nicht notarisiert.'),node('p','Erlaube CADOS bei Nachfrage Bluetooth und dem Browser die lokale Verbindung. Falls die direkte Verbindung blockiert wird, öffne „Lokale Trainingsansicht“ im Connector.'));
  panel.append(heading,status,actions,instructions);$('#home-panel').append(panel);
 }
 $('#local-link-status').textContent=localConnected?'Direkt mit diesem Computer verbunden · Training bleibt ohne Internet bedienbar.':localAccess?'Lokale Verbindung wird geprüft. Erlaube deinem Browser den Zugriff auf den lokalen Computer.':'Der Connector verbindet deinen Trainer mit CADOS.';
 if(localConnected&&isTrainingActive()&&!serverConnected)$('#connector-detail').textContent='Ohne Serververbindung · Live-Daten und Bedienung laufen direkt über deinen Computer.';
 const updateAvailable=connectorRelease&&connectorVersion&&compareVersion(connectorVersion,connectorRelease.version)<0;
 $('#update-connector-action').hidden=!updateAvailable;$('#update-connector-action').disabled=isTrainingActive()||!!liveData.updating;
 $('#connector-update-link').onclick=e=>{e.preventDefault();window.requestConnectorUpdate();};
 let recovery=$('#recover-training');
 if(!recovery){recovery=node('section',undefined,'card');recovery.id='recover-training';recovery.append(node('h3','Unterbrochenes Training gefunden'),node('p'));recovery.append(button('Wiederherstellen',()=>connectorCommand({name:'restore'})),button('Als beendete Einheit speichern',()=>connectorCommand({name:'save_recovered'})));$('#home-panel').prepend(recovery);}
 recovery.hidden=!liveData.recovery_available;
 if(liveData.recovery_available)recovery.querySelector('p').textContent=liveData.recovery_available.name+' · '+formatTime(liveData.recovery_available.elapsed_sec)+' gespeichert. Beim Wiederherstellen bleibt der Trainer zunächst pausiert.';
 renderReadinessChecks();
};
function renderReadinessChecks(){
 const checks=[
  ['Konto',connectorConnected?(liveData.account_email||user?.email||'Verbunden'):'Connector noch nicht gekoppelt'],
  ['Trainer',liveData.trainer_connected?(liveData.trainer_name||'Bereit'):'Nicht bereit · einschalten und „Trainer verbinden“ wählen'],
  ['Kadenz',liveData.measured_cadence>0?Math.round(liveData.measured_cadence)+' rpm erkannt':'Zum Prüfen kurz treten'],
  ['Herzfrequenz',liveData.hr_connected?(liveData.hr_name||'Verbunden'):'Optional · kein Sensor verbunden'],
  ['Offline-Bedienung',localConnected?'Direkte Verbindung bereit':'Lokale Ansicht im Connector verfügbar'],
 ];
 let list=$('#readiness-checks');if(!list){list=node('dl');list.id='readiness-checks';$('.start-setup').append(list);}
 list.replaceChildren();for(const [name,value] of checks)list.append(node('dt',name),node('dd',value));
 if(!liveData.trainer_connected)list.append(node('dd','Falls die Verbindung fehlschlägt: Prüfe Bluetooth-Rechte und schließe andere Trainings-Apps, die den Trainer verwenden.'));
 $('#prepare-start').disabled=$('#prepare-start').disabled||!!liveData.recovery_available||!!liveData.updating||!serverConnected;
}
