"use strict";

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
    download.append(title, detail, link);
    document.querySelector(".heading").after(download);
  }
  const link = document.querySelector("#connector-download-link");
  link.href = connectorRelease?.macos?.url || "https://github.com/Saibot412/CADOS/releases/download/v0.2.0/CADOS-Connector-macOS.dmg";
  link.textContent = "Connector für macOS laden";
  download.hidden = connectorConnected;
};
