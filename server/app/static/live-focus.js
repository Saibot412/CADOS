"use strict";

let liveWorkout, liveHistory = [];
const renderLiveFocusBase = renderLive;
const startOnMacFocusBase = startOnMac;

function liveNumber(value, unit) {
  return value == null ? "– " + unit : Math.round(value) + " " + unit;
}

function liveWorkoutForChart() {
  if (liveWorkout) return liveWorkout;
  const match = active("workout").find(record => record.payload.name === liveData.workout_name);
  return match?.payload;
}

function liveBlockWatts(block, ftp, edge) {
  const watts = edge === "start" ? block.start_watts : block.end_watts;
  const percent = edge === "start" ? block.start_pct_ftp : block.end_pct_ftp;
  return Number(watts ?? (percent != null ? percent * ftp : block.target_watts ?? (block.target_pct_ftp ?? 0) * ftp));
}

function svgElement(tag, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function svgText(svg, text, x, y, attributes = {}) {
  const element = svgElement("text", {x, y, fill: "#738792", "font-size": 11, ...attributes});
  element.textContent = text;
  svg.append(element);
}

function renderLiveChart() {
  const svg = document.querySelector("#live-chart");
  if (!svg) return;
  svg.replaceChildren();
  const workout = liveWorkoutForChart();
  const ftp = active("profile")[0]?.payload.ftp || 250;
  const blocks = workout?.blocks || [];
  let cursor = 0;
  const power = [], cadence = [];
  for (const block of blocks) {
    const duration = Math.max(0, Number(block.duration_sec) || 0);
    power.push([cursor, liveBlockWatts(block, ftp, "start")], [cursor + duration, liveBlockWatts(block, ftp, "end")]);
    if (block.target_cadence != null) cadence.push([cursor, Number(block.target_cadence)], [cursor + duration, Number(block.target_cadence)]);
    cursor += duration;
  }
  const total = Math.max(cursor, Number(liveData.elapsed_sec) || 0, 1);
  const actual = liveHistory.filter(point => point.elapsed <= total + 1);
  const powerValues = [...power.map(point => point[1]), ...actual.map(point => point.watts), Number(liveData.target_watts) || 0].filter(Number.isFinite);
  const lowPower = Math.max(0, Math.floor((Math.min(...powerValues, 0) - 20) / 25) * 25);
  const highPower = Math.max(ftp * 1.7, Math.ceil((Math.max(...powerValues, 100) + 20) / 25) * 25);
  const cadenceValues = [...cadence.map(point => point[1]), ...actual.map(point => point.cadence)].filter(Number.isFinite);
  const lowCadence = cadenceValues.length ? Math.max(0, Math.floor((Math.min(...cadenceValues) - 5) / 5) * 5) : 60;
  const highCadence = cadenceValues.length ? Math.ceil((Math.max(...cadenceValues) + 5) / 5) * 5 : 110;
  const width = 1000, height = 300, left = 115, right = 58, top = 32, bottom = 31;
  const chartWidth = width - left - right, chartHeight = height - top - bottom;
  const x = seconds => left + Math.min(Math.max(seconds / total, 0), 1) * chartWidth;
  const wattsY = watts => top + (1 - (watts - lowPower) / (highPower - lowPower)) * chartHeight;
  const cadenceY = value => top + (1 - (value - lowCadence) / Math.max(1, highCadence - lowCadence)) * chartHeight;
  drawPowerZones(svg,{ftp,maximum:highPower,left,right,top,bottom,width,height});
  for (let row = 0; row < 4; row++) {
    const ratio = row / 3, y = top + ratio * chartHeight, watts = Math.round(highPower - ratio * (highPower - lowPower));
    if (cadenceValues.length) svgText(svg, Math.round(highCadence - ratio * (highCadence - lowCadence)) + " rpm", width - right + 9, y + 4, {fill: "#3b79b8"});
  }
  const points = list => list.map(point => x(point[0]).toFixed(1) + "," + wattsY(point[1]).toFixed(1)).join(" ");
  if (power.length) svg.append(svgElement("polyline", {points: points(power), fill: "none", stroke: "#137c73", "stroke-width": 3.5, "stroke-linejoin": "round", "stroke-linecap": "round"}));
  if (cadence.length) svg.append(svgElement("polyline", {points: cadence.map(point => x(point[0]).toFixed(1) + "," + cadenceY(point[1]).toFixed(1)).join(" "), fill: "none", stroke: "#3b79b8", "stroke-width": 2.5, "stroke-dasharray": "7 5", "stroke-linejoin": "round"}));
  if (actual.length > 1) svg.append(svgElement("polyline", {points: actual.map(point => x(point.elapsed).toFixed(1) + "," + wattsY(point.watts).toFixed(1)).join(" "), fill: "none", stroke: "#193d55", "stroke-width": 3, "stroke-linejoin": "round", "stroke-linecap": "round"}));
  const actualCadence = actual.filter(point => Number.isFinite(point.cadence));
  if (actualCadence.length > 1) svg.append(svgElement("polyline", {points: actualCadence.map(point => x(point.elapsed).toFixed(1) + "," + cadenceY(point.cadence).toFixed(1)).join(" "), fill: "none", stroke: "#7654a8", "stroke-width": 2.6, "stroke-linejoin": "round", "stroke-linecap": "round"}));
  const elapsed = Math.min(Number(liveData.elapsed_sec) || 0, total), progressX = x(elapsed);
  svg.append(svgElement("line", {x1: progressX, y1: top - 5, x2: progressX, y2: height - bottom + 4, stroke: "#db7659", "stroke-width": 2}));
  if (liveData.current_watts != null) svg.append(svgElement("circle", {cx: progressX, cy: wattsY(Number(liveData.current_watts)), r: 4.5, fill: "#193d55", stroke: "#fff", "stroke-width": 2}));
  svgText(svg, "0:00", left, height - 8);
  svgText(svg, formatTime(total), width - right, height - 8, {"text-anchor": "end"});
  svgText(svg, 'Zeit (min:sek)', (left + width - right)/2, height - 8, {'text-anchor':'middle'});
  svgText(svg, 'rpm', width-right+9, top-12, {fill:'#3b79b8'});
  if (!power.length) svgText(svg, "Starte ein Workout, um den geplanten Verlauf zu sehen.", width / 2, height / 2, {"text-anchor": "middle", "font-size": 14});
}

function renderLiveFocus() {
  renderLiveFocusBase();
  const data = liveData || {};
  const elapsed = Number(data.elapsed_sec);
  if (Number.isFinite(elapsed) && data.current_watts != null) {
    if (liveHistory.length && elapsed < liveHistory.at(-1).elapsed) liveHistory = [];
    if (!liveHistory.length || elapsed > liveHistory.at(-1).elapsed) liveHistory.push({elapsed, watts: Number(data.current_watts), cadence: Number(data.current_cadence)});
    if (liveHistory.length > 1800) liveHistory.shift();
  }
  document.querySelector("#live-power").textContent = liveNumber(data.current_watts, "W");
  document.querySelector("#live-target").textContent = liveNumber(data.target_watts, "W");
  document.querySelector("#live-cadence").textContent = liveNumber(data.current_cadence, "rpm");
  document.querySelector("#live-hr").textContent = liveNumber(data.heart_rate, "bpm");
  document.querySelector("#live-target-note").textContent = data.adaptive_relief_watts ? "Adaptiv −" + Math.round(data.adaptive_relief_watts) + " W" : "ERG-Vorgabe";
  document.querySelector("#live-elapsed").textContent = Number.isFinite(elapsed) ? formatTime(elapsed) : "0:00";
  document.querySelector("#live-remaining").textContent = data.remaining_sec != null ? formatTime(data.remaining_sec) + " verbleibend" : "verbleibend –";
  renderLiveChart();
}

renderLive = renderLiveFocus;
startOnMac = function (record) {
  liveWorkout = record.payload;
  liveHistory = [];
  return startOnMacFocusBase(record);
};

document.querySelectorAll("[data-tab]").forEach(tab => tab.addEventListener("click", () => {
  document.body.classList.toggle("live-focus-active", tab.dataset.tab === "live");
}));
document.querySelector("#live-back").onclick = () => {
  document.body.classList.remove("live-focus-active");
  document.querySelector('[data-tab="workout"]').click();
};
