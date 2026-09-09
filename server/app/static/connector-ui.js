"use strict";

let connectorInstalledHere = false;
try { connectorInstalledHere = localStorage.getItem('cados.connector.installed') === 'yes'; } catch {}
function rememberConnectorLaunch() {
  if (location.hash !== '#connector-ready') return false;
  connectorInstalledHere = true;
  try { localStorage.setItem('cados.connector.installed', 'yes'); } catch {}
  history.replaceState(null, '', location.pathname + location.search);
  return true;
}
rememberConnectorLaunch();
window.addEventListener('hashchange', () => { if (rememberConnectorLaunch()) renderLive(); });
window.addEventListener('storage', event => {
  if (event.key === 'cados.connector.installed') {
    connectorInstalledHere = event.newValue === 'yes';
    renderLive();
  }
});

const renderLiveBase = renderLive;
renderLive = function () {
  renderLiveBase();
  let download = document.querySelector("#connector-download");
  if (!download) {
    download = document.createElement("aside");
    download.id = "connector-download";
    download.className = "connector-download";
    const title = document.createElement("strong");
    title.textContent = "Trainer direkt im Browser fahren";
    const detail = document.createElement("span");
    detail.textContent = "Installiere einmal den CADOS Connector für Bluetooth und ERG-Steuerung auf deinem Mac.";
    const link = document.createElement("a");
    link.id = "connector-download-link";
    link.target = "_blank";
    link.rel = "noopener";
    const fallback = document.createElement('a');
    fallback.id = 'connector-alternative';
    download.append(title, detail, link, fallback);
    document.querySelector(".heading").after(download);
  }
  const link = document.querySelector("#connector-download-link");
  const downloadUrl = connectorRelease?.macos?.url || "https://github.com/Saibot412/CADOS/releases/download/v0.2.0/CADOS-Connector-macOS.dmg";
  link.href = connectorInstalledHere ? 'cados-connector://open' : downloadUrl;
  link.textContent = connectorInstalledHere ? 'Connector starten' : 'Connector für macOS laden';
  link.target = connectorInstalledHere ? '_self' : '_blank';
  const fallback = document.querySelector('#connector-alternative');
  fallback.href = connectorInstalledHere ? downloadUrl : 'cados-connector://open';
  fallback.target = connectorInstalledHere ? '_blank' : '_self';
  fallback.rel = 'noopener';
  fallback.textContent = connectorInstalledHere ? 'Erneut herunterladen' : 'Bereits installiert? Starten';
  download.querySelector('span').textContent = connectorInstalledHere
    ? 'Starte den Connector auf diesem Mac, um deinen Trainer zu verbinden.'
    : 'Installiere den Connector einmal auf deinem Mac und öffne ihn. Er verbindet deinen Trainer mit CADOS.';
  download.hidden = connectorConnected;
};
