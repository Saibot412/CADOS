'use strict';
let deviceChoices={trainer:[],hr:[]},devicePreferences={},lastDeviceBusy=null;
const deviceDialog=node('dialog');deviceDialog.id='device-picker';deviceDialog.setAttribute('aria-labelledby','device-picker-title');
const deviceTitle=node('h2','Deine Trainingsgeräte');deviceTitle.id='device-picker-title';
const deviceHint=node('p','Trainer einschalten, Gurt anlegen oder bei der Uhr „Herzfrequenz senden“ aktivieren. Danach suchen und dein Gerät auswählen.');
const deviceMessage=node('p');deviceMessage.id='device-message';deviceMessage.setAttribute('role','status');
const deviceList=node('div');deviceList.id='device-list';
const scanButton=button('Geräte suchen',()=>{deviceMessage.textContent='Suche nach Geräten in deiner Nähe …';connectorCommand({name:'scan_devices'});});
const deviceHeader=node('div',undefined,'dialog-head');deviceHeader.append(deviceTitle,button('Schließen',()=>deviceDialog.close()));
deviceDialog.append(deviceHeader,deviceHint,scanButton,deviceMessage,deviceList);
const compatibility=node('details');compatibility.append(node('summary','Was funktioniert mit CADOS?'),node('p','Trainer mit Bluetooth-FTMS und ERG-Steuerung sowie Gurte und Uhren mit standardisiertem Bluetooth-Pulssignal. Die Unterstützung wird beim Verbinden geprüft; ein Markenname allein reicht nicht aus.'),node('p','Uhren: Bluetooth-Herzfrequenzübertragung / Broadcast HR einschalten. Bei belegter Verbindung andere Trainings-Apps schließen. ANT+-only-Geräte und Apple Watch werden hier nicht direkt unterstützt.'));
deviceDialog.append(compatibility);document.body.append(deviceDialog);
window.receiveDevices=function(message){deviceChoices=message.payload;devicePreferences=message.preferences||{};deviceMessage.textContent='Suche abgeschlossen. Wähle deine Geräte aus.';renderDeviceChoices();};
function renderDeviceChoices(){
 deviceList.replaceChildren();
 for(const [kind,label] of [['trainer','Trainer · ERG'],['hr','Herzfrequenz · optional']]){
  const section=node('section'),heading=node('h3',label);section.append(heading);
  const choices=deviceChoices[kind]||[];
  for(const item of choices){
   const row=node('article',undefined,'device-row'),description=node('div');
   description.append(node('strong',item.name),node('small',item.protocol+(item.rssi!=null?' · Signal '+item.rssi+' dBm':'')),node('small',item.identifier.slice(-12)+(devicePreferences[kind]===item.identifier?' · Gemerkt':'')));
   const select=button('Verbinden',()=>{deviceMessage.textContent=item.name+' wird verbunden …';connectorCommand({name:'select_device',kind,identifier:item.identifier});});
   select.disabled=!!liveData.devices_busy||(kind==='trainer'&&isTrainingActive());row.append(description,select);section.append(row);
  }
  if(!choices.length)section.append(node('p','Noch keine Geräte gefunden. Gerät einschalten und erneut suchen.','muted'));
  if(devicePreferences[kind])section.append(button(kind==='hr'?'Ohne Pulssensor fahren':'Trainer trennen und vergessen',()=>{connectorCommand({name:'disconnect_device',kind});}));
  deviceList.append(section);
 }
}
function openDevicePicker(){
 if(compareVersion(connectorVersion||'0.0.0','0.4.1')<0){notice('Die Geräteauswahl benötigt Connector 0.4.1 oder neuer. Bitte den Connector aktualisieren.',true);return;}
 if(!connectorConnected){notice('Bitte zuerst den Connector starten und mit deinem Konto koppeln.',true);return;}
 renderDeviceChoices();if(!deviceDialog.open)deviceDialog.showModal();
}
$('#connector-connect').textContent='Geräte auswählen';$('#connector-connect').onclick=openDevicePicker;
$('#prepare-connect').textContent='Geräte auswählen';
const deviceRenderLive=renderLive;
renderLive=function(){
 deviceRenderLive();scanButton.disabled=!connectorConnected||!!liveData.devices_busy;
 if(deviceDialog.open){if(lastDeviceBusy!==liveData.devices_busy){lastDeviceBusy=liveData.devices_busy;renderDeviceChoices();}if(liveData.device_status)deviceMessage.textContent=liveData.device_status;}
 let buttonOnHome=$('#device-picker-home');
 if(!buttonOnHome){buttonOnHome=button('Trainer & Pulssensor auswählen',openDevicePicker);buttonOnHome.id='device-picker-home';$('.connector-actions')?.append(buttonOnHome);}
 if(liveData.trainer_max_power&&Number(liveData.trainer_target_watts)>liveData.trainer_max_power)$('#connector-detail').textContent='Der Trainer begrenzt die Leistung auf '+liveData.trainer_max_power+' W. Die Testauswertung verwendet deine gemessene Leistung.';
 if(liveData.cadence_available===false){$('#live-cadence').textContent='– rpm';}
};
