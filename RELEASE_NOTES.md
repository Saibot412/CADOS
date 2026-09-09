# CADOS 0.3.0

## Training im Mittelpunkt

- Die Übersicht zeigt das heutige geplante oder laufende Training, Wochenwerte, kommende Einheiten und den letzten Abschluss.
- Einheitliche Karten, Abstände, Tastaturfokus und verständliche Verbindungszustände.
- Automatische Abschlussansicht mit Soll-/Ist-Leistung und Kadenz, Zonenzeiten und persönlicher Belastungsbewertung (1–10).
- Über einen Kalendereintrag gestartete, abgeschlossene Trainings erledigen genau diesen Eintrag. Vorzeitig beendete Einheiten bleiben in der Historie; der Plan bleibt offen.

## Verlässliche lokale Steuerung

- Die Trainingssteuerung läuft unabhängig von Serververbindung, Synchronisierung und Gerätesuche.
- Der Connector bietet Pause, Fortsetzen und Training beenden auch ohne Internet.
- Nach Browser-Neuladen werden Workout, Trainingsstand und bisheriger Messverlauf vom laufenden Connector wiederhergestellt.
- Bei Bluetooth-Verlust pausiert die Einheit. Nach Wiederverbinden und erneutem Treten fährt der Widerstand sanft hoch.
- Nach Rechner-Ruhezustand bleibt das Training pausiert, bis es ausdrücklich fortgesetzt wird; die Schlafzeit zählt nicht als Trainingszeit.
- Abschlüsse werden zuerst lokal gespeichert und später synchronisiert, auch nach einem Connector-Neustart.

## Veröffentlichung

1. GitHub-Release mit Tag `v0.3.0` erstellen und `release/CADOS-Connector-macOS.dmg` als Asset hochladen.
2. Anschließend den Webserver aus dem aktualisierten Git-Stand neu bauen.
3. Auf dem Mac den bisherigen Connector beenden und durch die neue App ersetzen.

Web und Connector gemeinsam aktualisieren. Der Download verweist auf das Release `v0.3.0`; vor dessen Veröffentlichung ist dieser Link noch nicht verfügbar. Die neuen Session-Felder werden im vorhandenen JSON-Payload gespeichert; eine zusätzliche Datenbankschemaänderung ist nicht erforderlich.

Ein laufender Connector ist für Training ohne Internet erforderlich. Ein offline neu geladener Browser kann die Server-Webseite nicht laden; die lokalen Tasten bleiben im Connector erreichbar. Ausschalten oder ein Absturz des Connector-Prozesses ist keine unterstützte Wiederaufnahme einer laufenden Einheit. Die Änderungen wurden mit simuliertem Trainer geprüft; ein Praxistest mit dem echten Trainer bleibt nötig.
