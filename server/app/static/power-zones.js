"use strict";

// Same FTP boundaries and palette as cados/core/zones.py (desktop training view).
const powerZones = [
  {code:'Z1',name:'Erholung',upper:.55,color:'#8B98A7'},
  {code:'Z2',name:'Grundlage',upper:.75,color:'#2E86FF'},
  {code:'Z3',name:'Tempo',upper:.90,color:'#2FBF71'},
  {code:'Z4',name:'Schwelle',upper:1.05,color:'#F2C94C'},
  {code:'Z5',name:'VO₂max',upper:1.20,color:'#FF9F43'},
  {code:'Z6',name:'Anaerob',upper:1.50,color:'#EB5757'},
  {code:'Z7',name:'Sprint',upper:Infinity,color:'#9B51E0'}
];

function drawPowerZones(svg,{ftp,maximum,left,right,top,bottom,width,height,compact=false}) {
  const y=watts=>top+(1-watts/maximum)*(height-top-bottom);
  let lower=0;
  for(const zone of powerZones) {
    const upper=zone.upper*ftp,visibleUpper=Math.min(upper,maximum);
    if(lower>=maximum)break;
    const bandTop=y(visibleUpper),bandBottom=y(lower),bandHeight=bandBottom-bandTop;
    const group=svgElement('g',{'data-zone':zone.code});
    const minimumLabel=lower===0?0:Math.floor(lower+.5)+1;
    const range=Number.isFinite(upper)?minimumLabel+'–'+Math.floor(upper+.5)+' W':minimumLabel+'+ W';
    const title=svgElement('title');title.textContent=zone.code+' · '+zone.name+' · '+range;group.append(title);
    group.append(svgElement('rect',{x:left,y:bandTop,width:width-left-right,height:bandHeight,fill:zone.color,'fill-opacity':.075}));
    group.append(svgElement('line',{x1:left,y1:bandTop,x2:width-right,y2:bandTop,stroke:zone.color,'stroke-opacity':.3}));
    group.append(svgElement('rect',{x:left-5,y:bandTop,width:3,height:bandHeight,fill:zone.color}));
    // Separate labels only if the visible band has room. Full names/ranges stay in the tooltip.
    if(bandHeight>=(compact?12:16)) {
      const wattLabel=Number.isFinite(upper)?'≤ '+Math.floor(upper+.5)+' W':'> '+Math.floor(lower+.5)+' W';
      svgText(group,zone.code+' · '+wattLabel,left-12,(bandTop+bandBottom)/2+(compact?3:4),{
        'text-anchor':'end',fill:zone.color,'font-size':compact?11:10,'font-weight':600,
        stroke:'#25352c','stroke-width':.2,'paint-order':'stroke'
      });
    }
    svg.append(group);lower=upper;
  }
  svgText(svg,'W · FTP '+Math.round(ftp),left-10,top-9,{'text-anchor':'end','font-size':compact?9:10});
  svgText(svg,'0 W',left-12,height-bottom+4,{'text-anchor':'end','font-size':compact?8:9,fill:powerZones[0].color});
}

function powerZonePreview(workout,ftp,large=false,selectedBlock=null) {
  ftp=Math.max(1,Number(ftp)||250);
  const width=large?1000:520,height=large?400:240,left=large?135:110,right=large?65:44,top=23,bottom=32;
  const power=[],cadence=[],cadenceRuns=[];let elapsed=0,cadenceRun=null;
  for(const block of workout.blocks||[]) {
    const duration=Number(block.duration_sec)||0;
    power.push([elapsed,liveBlockWatts(block,ftp,'start')],[elapsed+duration,liveBlockWatts(block,ftp,'end')]);
    if(block.target_cadence!=null){
      if(!cadenceRun){cadenceRun=[];cadenceRuns.push(cadenceRun);}
      const segment=[[elapsed,block.target_cadence],[elapsed+duration,block.target_cadence]];
      cadence.push(...segment);cadenceRun.push(...segment);
    }else cadenceRun=null;
    elapsed+=duration;
  }
  const maximum=Math.max(ftp*1.7,...power.map(p=>p[1]*1.08));
  const maxCadence=Math.max(110,...cadence.map(p=>p[1]+5));
  const x=time=>left+time/(elapsed||1)*(width-left-right);
  const y=value=>height-bottom-value/maximum*(height-top-bottom);
  const cy=value=>height-bottom-value/maxCadence*(height-top-bottom);
  const svg=svgElement('svg',{viewBox:'0 0 '+width+' '+height,width:'100%',role:'img','aria-label':'Workout-Vorschau mit FTP-Leistungszonen, Soll-Watt und Soll-Kadenz'});
  drawPowerZones(svg,{ftp,maximum,left,right,top,bottom,width,height,compact:true});
  if(Number.isInteger(selectedBlock)&&workout.blocks?.[selectedBlock]) {
    const start=workout.blocks.slice(0,selectedBlock).reduce((sum,block)=>sum+(Number(block.duration_sec)||0),0);
    const end=start+(Number(workout.blocks[selectedBlock].duration_sec)||0);
    svg.append(svgElement('rect',{x:x(start),y:top,width:Math.max(0,x(end)-x(start)),height:height-top-bottom,
      fill:'#137c73','fill-opacity':.10,stroke:'#137c73','stroke-width':1.5,'data-selected-block':selectedBlock}));
  }
  svg.append(svgElement('polyline',{points:power.map(p=>x(p[0])+','+y(p[1])).join(' '),fill:'none',stroke:'#137c73','stroke-width':2.5,'stroke-linejoin':'round'}));
  if(cadence.length){
    for(const run of cadenceRuns)svg.append(svgElement('polyline',{points:run.map(p=>x(p[0])+','+cy(p[1])).join(' '),fill:'none',stroke:'#275d9b','stroke-width':2,'stroke-dasharray':'5 4'}));
    for(const value of [0,Math.round(maxCadence/2),maxCadence])svgText(svg,String(value),width-right+8,cy(value)+3,{fill:'#275d9b','font-size':9});
  }
  svgText(svg,'rpm',width-right+8,top-9,{fill:'#275d9b','font-size':large?12:9});
  if(!cadence.length)svgText(svg,'Keine Kadenzvorgabe',width-right,top-9,{'text-anchor':'end','font-size':large?12:9});
  svgText(svg,'Zeit (min:sek)',left+(width-left-right)/2,height-5,{'text-anchor':'middle','font-size':large?12:9});
  svgText(svg,'0:00',left,height-5,{'font-size':9});svgText(svg,formatTime(elapsed),width-right,height-5,{'text-anchor':'end','font-size':9});
  return svg;
}
