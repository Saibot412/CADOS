"use strict";

// Drafts stay separate from synchronized records until the user saves them.
let workoutBuilder=null;
const builderDialog=node('dialog');builderDialog.id='workout-builder';builderDialog.setAttribute('aria-labelledby','builder-title');
builderDialog.innerHTML=`<form id="builder-form">
  <header class="builder-header"><div><p class="eyebrow">DEIN TRAINING. DEIN AUFBAU.</p><h2 id="builder-title">Workout erstellen</h2></div><button type="button" id="builder-close" class="quiet">Schließen</button></header>
  <div class="builder-layout">
    <fieldset id="builder-fields"><div class="builder-details">
      <label>Workout-Name<input id="builder-name" maxlength="200" required placeholder="z. B. Meine Schwellenintervalle"></label>
      <label>Kategorie<input id="builder-category" maxlength="100" placeholder="z. B. Grundlage"></label>
      <label class="builder-description">Beschreibung<textarea id="builder-description" rows="2" maxlength="5000" placeholder="Was möchtest du mit dieser Einheit trainieren?"></textarea></label>
    </div>
    <div class="builder-block-heading"><h3>Deine Blöcke</h3><span>Von oben nach unten gefahren</span></div>
    <div id="builder-blocks"></div>
    <div class="builder-add"><button type="button" id="builder-add-steady" class="quiet">＋ Konstanter Block</button><button type="button" id="builder-add-ramp" class="quiet">＋ Rampe</button></div>
    </fieldset>
    <aside class="builder-preview"><div class="builder-preview-heading"><div><p class="eyebrow">LIVE-VORSCHAU</p><h3 id="builder-preview-name">Dein Workout</h3></div><strong id="builder-duration"></strong></div>
      <p id="builder-ftp" class="muted"></p><div id="builder-chart"></div>
      <p class="builder-legend"><span>━ Leistung (W)</span><span>┄ Kadenz (rpm)</span></p>
      <p id="builder-selection" class="muted"></p>
      <div class="builder-help"><strong>So baust du deine Einheit</strong><p>Konstante Blöcke halten die Leistung. Rampen verändern sie gleichmäßig vom Start- zum Endwert – nach oben oder nach unten.</p><p>Mit % FTP passt sich das Workout an die persönliche FTP an. Wattwerte bleiben fest. Eine leere Kadenz lässt die Trittfrequenz frei.</p></div>
    </aside>
  </div>
  <footer class="builder-footer"><div><p id="builder-message" role="status"></p><label id="builder-share-label"><input type="checkbox" id="builder-share"> Für alle freigeben</label></div><div class="builder-footer-actions"><button type="button" id="builder-copy" class="quiet" hidden>Als eigenes Workout bearbeiten</button><button type="submit" id="builder-save">Workout speichern</button></div></footer>
</form>`;
document.body.append(builderDialog);

function builderBlock(block){
 const ftp=workoutBuilder.ftp;
 const percent=block.type==='steady'?block.target_pct_ftp!=null:(block.start_pct_ftp!=null||block.end_pct_ftp!=null);
 const value=(pct,watts,fallback)=>percent?(pct!=null?pct*100:(watts!=null?watts/ftp*100:fallback)):(watts??fallback);
 return {type:block.type,label:block.label||'',duration_sec:block.duration_sec,unit:percent?'percent':'watts',
   start:block.type==='steady'?value(block.target_pct_ftp,block.target_watts,75):value(block.start_pct_ftp,block.start_watts,50),
   end:value(block.end_pct_ftp,block.end_watts,75),cadence:block.target_cadence??'',extra:structuredClone(block)};
}
function builderPayload(){
 return {...workoutBuilder.source.payload,name:$('#builder-name').value.trim(),category:$('#builder-category').value.trim()||'Eigenes Workout',description:$('#builder-description').value,
  blocks:workoutBuilder.blocks.map(block=>{
   const result={...block.extra,type:block.type,label:block.label.trim()||(block.type==='ramp'?'Rampe':'Konstant'),duration_sec:block.duration_sec};
   for(const key of ['target_pct_ftp','target_watts','start_pct_ftp','end_pct_ftp','start_watts','end_watts','target_cadence'])delete result[key];
   const suffix=block.unit==='percent'?'pct_ftp':'watts',convert=value=>block.unit==='percent'?Number((Number(value)/100).toFixed(6)):Number(value);
   if(block.type==='steady')result['target_'+suffix]=convert(block.start);
   else{result['start_'+suffix]=convert(block.start);result['end_'+suffix]=convert(block.end);}
   if(block.cadence!=='')result.target_cadence=Number(block.cadence);
   return result;
  })};
}
function openWorkoutBuilder(record=null){
 const id=crypto.randomUUID();
 const source=record?structuredClone(record):{id,kind:'workout',revision:0,shared:false,deleted:false,payload:{name:'',category:'Eigenes Workout',description:'',source_name:id+'.json',blocks:[]}};
 workoutBuilder={source,ftp:active('profile')[0]?.payload.ftp||250,blocks:[],selected:0,dirty:false,busy:false,readonly:!!(record?.shared&&!user.admin)};
 const defaults=[{type:'ramp',label:'Aufwärmen',duration_sec:300,start_pct_ftp:.4,end_pct_ftp:.7,target_cadence:85},{type:'steady',label:'Hauptteil',duration_sec:600,target_pct_ftp:.75,target_cadence:90},{type:'ramp',label:'Abwärmen',duration_sec:300,start_pct_ftp:.7,end_pct_ftp:.4,target_cadence:85}];
 workoutBuilder.blocks=(record?source.payload.blocks:defaults).map(builderBlock);
 $('#builder-title').textContent=workoutBuilder.readonly?'Workout ansehen':record?'Workout bearbeiten':'Workout erstellen';
 $('#builder-name').value=source.payload.name;$('#builder-category').value=source.payload.category||'';$('#builder-description').value=source.payload.description||'';
 $('#builder-share').checked=source.shared;$('#builder-share-label').hidden=!user.admin||!!record;
 $('#builder-share').disabled=!!record;$('#builder-fields').disabled=workoutBuilder.readonly;
 $('#builder-save').hidden=workoutBuilder.readonly;$('#builder-copy').hidden=!workoutBuilder.readonly;
 $('#builder-message').textContent=workoutBuilder.readonly?'Dieses Bibliotheks-Workout kannst du als eigene Kopie anpassen.':'Noch nicht gespeichert. Änderungen bleiben bis zum Speichern in diesem Entwurf.';
 $('#builder-ftp').textContent='Vorschau mit deiner FTP: '+workoutBuilder.ftp+' W · Änderungen sind sofort sichtbar.';
 renderBuilderBlocks();if(!builderDialog.open)builderDialog.showModal();
 $('#builder-fields').scrollTop=0;
}
function updateBuilderPreview(){
 if(!workoutBuilder)return;
 const payload=builderPayload();
 const valid=block=>Number.isInteger(block.duration_sec)&&block.duration_sec>0&&['target_pct_ftp','target_watts','start_pct_ftp','start_watts','end_pct_ftp','end_watts'].every(key=>block[key]==null||(Number.isFinite(block[key])&&block[key]>0&&(key.endsWith('watts')?block[key]<=32767:block[key]*workoutBuilder.ftp<=32767)))&&(block.target_cadence==null||(Number.isInteger(block.target_cadence)&&block.target_cadence>0));
 const usable=payload.blocks.filter(valid),duration=usable.reduce((sum,b)=>sum+b.duration_sec,0);
 $('#builder-preview-name').textContent=payload.name||'Dein Workout';$('#builder-duration').textContent=formatTime(duration)+' min';
 const index=valid(payload.blocks[workoutBuilder.selected]||{})?payload.blocks.slice(0,workoutBuilder.selected).filter(valid).length:null;
 $('#builder-chart').replaceChildren(powerZonePreview({...payload,blocks:usable},workoutBuilder.ftp,false,index));
 $('#builder-selection').textContent=usable.length!==payload.blocks.length?'Unvollständige Blöcke erscheinen, sobald Dauer und Leistung gültig sind.':payload.blocks.length?'Markiert: Block '+(workoutBuilder.selected+1)+' · '+payload.blocks[workoutBuilder.selected]?.label:'Füge deinen ersten Block hinzu.';
 const invalid=duration>86400||!payload.blocks.length||payload.blocks.length>2000;
 $('#builder-save').disabled=workoutBuilder.busy||invalid||usable.length!==payload.blocks.length;
 if(duration>86400)$('#builder-selection').textContent='Das Workout darf höchstens 24 Stunden dauern.';
 $('#builder-add-steady').disabled=$('#builder-add-ramp').disabled=workoutBuilder.blocks.length>=2000;
}
function builderInput(parent,label,name,value,options={},oninput){
 const wrapper=node('label',label),input=node('input');input.name=name;input.value=value;
 for(const [key,val] of Object.entries(options))input.setAttribute(key,val);
 input.addEventListener('input',()=>{oninput(input.value);workoutBuilder.dirty=true;updateBuilderPreview();});
 wrapper.append(input);parent.append(wrapper);return input;
}
function selectBuilderBlock(index){
 workoutBuilder.selected=index;$('#builder-blocks').querySelectorAll('.builder-block').forEach((card,i)=>card.classList.toggle('selected',i===index));updateBuilderPreview();
}
function mutateBuilder(action,focus=true){
 if(workoutBuilder.readonly||workoutBuilder.busy)return;
 action();workoutBuilder.dirty=true;workoutBuilder.selected=Math.max(0,Math.min(workoutBuilder.selected,workoutBuilder.blocks.length-1));
 renderBuilderBlocks();if(focus){const card=$('#builder-blocks').children[workoutBuilder.selected];card?.querySelector('input')?.focus({preventScroll:true});card?.scrollIntoView({block:'nearest'});}
}
function renderBuilderBlocks(){
 const list=$('#builder-blocks');list.replaceChildren();
 workoutBuilder.blocks.forEach((block,index)=>{
  const card=node('article',undefined,'builder-block'+(index===workoutBuilder.selected?' selected':''));
  card.addEventListener('focusin',()=>{if(workoutBuilder.selected!==index)selectBuilderBlock(index);});
  const heading=node('div',undefined,'builder-row-head');heading.append(node('strong',String(index+1).padStart(2,'0'),'block-number'));
  const name=node('input');name.value=block.label;name.placeholder=block.type==='ramp'?'Rampe':'Konstant';name.maxLength=200;name.setAttribute('aria-label','Block '+(index+1)+' benennen');name.oninput=()=>{block.label=name.value;workoutBuilder.dirty=true;updateBuilderPreview();};heading.append(name);
  const actions=node('div',undefined,'builder-row-actions');
  for(const [label,text,action,disabled] of [
   ['Nach oben','↑',()=>{[workoutBuilder.blocks[index-1],workoutBuilder.blocks[index]]=[block,workoutBuilder.blocks[index-1]];workoutBuilder.selected=index-1;},index===0],
   ['Nach unten','↓',()=>{[workoutBuilder.blocks[index+1],workoutBuilder.blocks[index]]=[block,workoutBuilder.blocks[index+1]];workoutBuilder.selected=index+1;},index===workoutBuilder.blocks.length-1],
   ['Block duplizieren','Kopie',()=>{workoutBuilder.blocks.splice(index+1,0,structuredClone(block));workoutBuilder.selected=index+1;},workoutBuilder.blocks.length>=2000],
   ['Block entfernen','×',()=>{workoutBuilder.blocks.splice(index,1);workoutBuilder.selected=index;},false]]){
   const control=button(text,()=>mutateBuilder(action));control.setAttribute('aria-label',label+' · Block '+(index+1));control.title=label;control.disabled=disabled;actions.append(control);
  }
  heading.append(actions);card.append(heading);
  const fields=node('div',undefined,'builder-row-fields');
  const typeLabel=node('label','Typ'),type=node('select');type.name='type';for(const [value,label]of [['steady','Konstant'],['ramp','Rampe']]){const option=node('option',label);option.value=value;type.append(option);}type.value=block.type;
  type.onchange=()=>mutateBuilder(()=>{block.type=type.value;if(block.type==='ramp')block.end=block.start;workoutBuilder.selected=index;},false);typeLabel.append(type);fields.append(typeLabel);
  const duration=node('div',undefined,'builder-duration-inputs');
  let minutes,seconds;
  const durationChanged=()=>{block.duration_sec=Number(minutes.value)*60+Number(seconds.value);seconds.setCustomValidity(block.duration_sec>0?'':'Der Block braucht eine Dauer größer als 0.');};
  minutes=builderInput(duration,'Minuten','minutes',Math.floor(block.duration_sec/60),{type:'number',min:0,max:1440,step:1,required:''},durationChanged);
  seconds=builderInput(duration,'Sekunden','seconds',block.duration_sec%60,{type:'number',min:0,max:59,step:1,required:''},durationChanged);fields.append(duration);
  const unitLabel=node('label','Leistung in'),unit=node('select');unit.name='unit';for(const [value,label]of [['percent','% FTP'],['watts','Watt']]){const option=node('option',label);option.value=value;unit.append(option);}unit.value=block.unit;
  unit.onchange=()=>mutateBuilder(()=>{const factor=unit.value==='watts'?workoutBuilder.ftp/100:100/workoutBuilder.ftp;block.start=unit.value==='watts'?Math.max(1,Math.round(block.start*factor)):Number((block.start*factor).toFixed(4));block.end=unit.value==='watts'?Math.max(1,Math.round(block.end*factor)):Number((block.end*factor).toFixed(4));block.unit=unit.value;workoutBuilder.selected=index;},false);unitLabel.append(unit);fields.append(unitLabel);
  const unitText=block.unit==='percent'?'% FTP':'W',powerOptions={type:'number',min:block.unit==='watts'?1:.01,step:block.unit==='watts'?1:'any',required:''};powerOptions.max=block.unit==='watts'?32767:32767/workoutBuilder.ftp*100;
  builderInput(fields,(block.type==='ramp'?'Start':'Ziel')+' ('+unitText+')','start',Number(block.start.toFixed(4)),powerOptions,value=>block.start=Number(value));
  if(block.type==='ramp')builderInput(fields,'Ende ('+unitText+')','end',Number(block.end.toFixed(4)),powerOptions,value=>block.end=Number(value));
  builderInput(fields,'Kadenz (rpm)','cadence',block.cadence,{type:'number',min:1,step:1,placeholder:'Frei'},value=>block.cadence=value===''?'':Number(value));
  card.append(fields);list.append(card);
 });
 if(!workoutBuilder.blocks.length)list.append(node('p','Dein Workout beginnt mit einem Block. Füge einen konstanten Abschnitt oder eine Rampe hinzu.','empty'));
 updateBuilderPreview();
}
function addBuilderBlock(type){mutateBuilder(()=>{workoutBuilder.blocks.push({type,label:type==='ramp'?'Rampe':'Konstant',duration_sec:300,unit:'percent',start:type==='ramp'?50:75,end:90,cadence:90,extra:{}});workoutBuilder.selected=workoutBuilder.blocks.length-1;});}
$('#builder-add-steady').onclick=()=>addBuilderBlock('steady');$('#builder-add-ramp').onclick=()=>addBuilderBlock('ramp');
for(const id of ['builder-name','builder-category','builder-description','builder-share'])$('#'+id).addEventListener('input',()=>{workoutBuilder.dirty=true;updateBuilderPreview();});
function closeWorkoutBuilder(){if(workoutBuilder?.busy)return;if(workoutBuilder?.dirty&&!confirm('Ungespeicherte Änderungen verwerfen?'))return;builderDialog.close();workoutBuilder=null;}
$('#builder-close').onclick=closeWorkoutBuilder;builderDialog.addEventListener('cancel',event=>{event.preventDefault();closeWorkoutBuilder();});
window.addEventListener('beforeunload',event=>{if(builderDialog.open&&workoutBuilder?.dirty){event.preventDefault();event.returnValue='';}});
$('#builder-copy').onclick=()=>{const source=structuredClone(workoutBuilder.source),id=crypto.randomUUID();source.id=id;source.revision=0;source.shared=false;source.payload.source_name=id+'.json';source.payload.name+=' (Kopie)';openWorkoutBuilder(source);workoutBuilder.dirty=true;};
$('#builder-form').onsubmit=async event=>{
 event.preventDefault();if(workoutBuilder.readonly||workoutBuilder.busy)return;
 const payload=builderPayload();if(!payload.name){$('#builder-message').textContent='Bitte gib deinem Workout einen Namen.';$('#builder-name').focus();return;}
 const record={...workoutBuilder.source,payload,shared:workoutBuilder.source.revision?workoutBuilder.source.shared:$('#builder-share').checked};
 workoutBuilder.busy=true;$('#builder-save').disabled=true;$('#builder-fields').disabled=true;$('#builder-close').disabled=true;$('#builder-message').textContent='Workout wird gespeichert …';
 try{
  await post('/sync',{changes:[record]});workoutBuilder.dirty=false;builderDialog.close();workoutBuilder=null;
  try{await reload();notice('Workout gespeichert. Du findest es in deiner Bibliothek.');}catch{notice('Workout gespeichert. Bitte die Bibliothek aktualisieren, sobald die Verbindung wieder verfügbar ist.',true);}
 }catch(error){$('#builder-message').textContent=error.message;}
 finally{if(workoutBuilder){workoutBuilder.busy=false;$('#builder-fields').disabled=workoutBuilder.readonly;updateBuilderPreview();}$('#builder-close').disabled=false;}
};
$('#create-workout').onclick=()=>openWorkoutBuilder();
