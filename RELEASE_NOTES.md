# CADOS 0.3.1

- FTP-Rampentest bis 200 % der bisherigen FTP: bei 300 W FTP sind bis zu 600 W Sollleistung vorgesehen.
- Normaler ERG im FTP-Rampentest; adaptive Entlastung bleibt ausgeschaltet.
- Auswertung nach Testende: bisherige FTP, Schätzung, Veränderung in Watt und Prozent. Die neue FTP wird nur auf ausdrücklichen Klick übernommen.
- Grundlage: 75 % der besten vollständigen, zusammenhängenden Messminute im Stufenteil. Warmup, Pausen und zu kurze Messabschnitte ergeben keinen verwertbaren Testwert.
- Höhere gemessene Herzfrequenzwerte (50–250 bpm) erhöhen beim Synchronisieren einer Einheit automatisch den Profilwert. Niedrigere Werte senken ihn nicht.
- Unveränderte mitgelieferte FTP-Testblöcke werden beim Serverstart aktualisiert. Eigene Blockänderungen und Löschungen bleiben erhalten.

Veröffentlichung: Release `v0.3.1` auf GitHub erstellen, die neue `release/CADOS-Connector-macOS.dmg` anhängen, danach Server und Mac-Connector aktualisieren. Die Felder liegen in vorhandenen JSON-Daten; keine weitere Schemaänderung erforderlich.

Die FTP bleibt eine Rampentest-Schätzung. Den Vorschlag nur nach einem bis zur persönlichen Belastungsgrenze gefahrenen Test übernehmen. Die Tests nutzen simulierte Trainerdaten; die reale Belastungsregelung hängt vom angeschlossenen Trainer ab.

---

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

## Workout-Builder im Web

- Neue Workouts direkt in der Bibliothek erstellen oder bestehende bearbeiten.
- Konstante Blöcke und Rampen mit Minuten/Sekunden, Watt oder % FTP sowie optionaler Kadenz.
- Sofortige Diagrammvorschau mit Markierung des bearbeiteten Blocks; Blöcke kopieren, verschieben oder entfernen.
- Gemeinsame Workouts bleiben für normale Nutzer schreibgeschützt und können als private Kopie bearbeitet werden.
- Diese Ergänzung benötigt nur ein Update des Webservers; Connector 0.3.0 bleibt kompatibel.

## Veröffentlichte Workouts

- Neue Veröffentlichungen zeigen den Benutzernamen des veröffentlichenden Kontos. Die Zuordnung wird vom Server gesetzt und bleibt bei Bearbeitungen erhalten.
- Administratoren können Veröffentlichungen direkt in der Workout-Übersicht löschen. Gespeicherte Trainingseinheiten bleiben erhalten.
- Schema-Version 3 ergänzt beim Serverstart automatisch die Publisher-Spalte. Alte, nicht zuordenbare Veröffentlichungen zeigen „Name nicht erfasst“; mitgelieferte Workouts zeigen „CADOS“.

## Veröffentlichung

1. GitHub-Release mit Tag `v0.3.0` erstellen und `release/CADOS-Connector-macOS.dmg` als Asset hochladen.
2. Anschließend den Webserver aus dem aktualisierten Git-Stand neu bauen.
3. Auf dem Mac den bisherigen Connector beenden und durch die neue App ersetzen.

Web und Connector gemeinsam aktualisieren. Der Download verweist auf das Release `v0.3.0`; vor dessen Veröffentlichung ist dieser Link noch nicht verfügbar. Die neuen Session-Felder werden im vorhandenen JSON-Payload gespeichert; für diese Session-Felder ist keine zusätzliche Datenbankschemaänderung erforderlich. Die Zuordnung veröffentlichter Workouts ergänzt Schema-Version 3 automatisch.

Ein laufender Connector ist für Training ohne Internet erforderlich. Ein offline neu geladener Browser kann die Server-Webseite nicht laden; die lokalen Tasten bleiben im Connector erreichbar. Ausschalten oder ein Absturz des Connector-Prozesses ist keine unterstützte Wiederaufnahme einer laufenden Einheit. Die Änderungen wurden mit simuliertem Trainer geprüft; ein Praxistest mit dem echten Trainer bleibt nötig.
