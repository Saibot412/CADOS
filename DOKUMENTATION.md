# CADOS – Web-App und Connector

CADOS besteht aus der Web-Oberfläche unter https://cados.saibot.at und dem lokalen
Connector. Der Browser verwaltet Konto, Workouts, Kalender und Trainingsanzeige.
Der Connector übernimmt Bluetooth, ERG-Steuerung und die lokale Aufzeichnung.
Die frühere vollständige Desktop-App wurde entfernt.

## Installation und Anmeldung

Den Connector auf der CADOS-Webseite herunterladen, das DMG öffnen und
**CADOS Connector.app** nach **Programme** ziehen. Die installierbare App enthält
Python und alle Abhängigkeiten. Den Connector starten und Bluetooth erlauben.
Bei der ersten Verwendung **Im Browser anmelden** wählen und die Kopplung auf der
Webseite bestätigen. Es wird kein zweites Passwort im Connector eingegeben.
Bestehende gespeicherte Anmeldungen werden übernommen; Passwörter werden nicht gespeichert.
Über das Connector-Menü in der Menüleiste lässt sich **Anmeldung ändern …** wählen,
sobald kein Training läuft. Neue Konten werden auf der Webseite registriert.

## Updates auf macOS

Der Connector kann außerhalb eines Trainings mit einem Klick nach Updates suchen,
das DMG herunterladen, die SHA-256-Prüfsumme prüfen und die installierte App ersetzen.
Bei fehlenden Schreibrechten wird das DMG zur manuellen Installation geöffnet.
Updates sind während eines Trainings oder einer noch offenen Wiederherstellung gesperrt.

Die App ist ad-hoc signiert, aber ohne Apple-Developer-Konto nicht notarisiert.
Bei einer macOS-Warnung: **Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen**.
Der Installer entfernt keine macOS-Sicherheitskennzeichnungen. Auch bei Updates kann
macOS erneut eine Freigabe verlangen.

## Training und Speicherung

Workouts im Browser auswählen, Trainer verbinden und das Training starten.
Normales und adaptives ERG sind verfügbar; FTP-Rampentests verwenden normales ERG.
Während eines Internetausfalls läuft ein bereits gestartetes Training lokal weiter.
Die geöffnete Webseite verbindet sich zusätzlich direkt mit dem Connector auf
`127.0.0.1:48732`. Erlaube bei Nachfrage den lokalen Netzwerkzugriff im Browser.
Bei einer blockierten Direktverbindung öffnet **Lokale Trainingsansicht öffnen**
im Connector eine vollständig lokale Seite mit Messwerten, Diagramm und Bedienung.
Diese lokale Seite bleibt auch nach einem Neuladen ohne Internet nutzbar.
Pause, Fortsetzen und Beenden bleiben zudem im Connector-Fenster erreichbar.
Für Anmeldung und den Start über die Webseite ist eine Serververbindung erforderlich.

Abgeschlossene Trainings werden lokal in SQLite gespeichert und mit dem Server
synchronisiert. Ohne Verbindung wird der Abgleich später wiederholt.
Unter macOS liegen Daten unter `~/Library/Application Support/Cados`, unter Windows
unter `%LOCALAPPDATA%\Cados`. Bereits vorhandene Kontodaten bleiben erhalten;
weitere Konten verwenden getrennte SQLite-Dateien. Der Server speichert Konten,
Workouts und synchronisierte Trainings in PostgreSQL.

Nach zehn Minuten ohne Webseite schließt sich der Connector automatisch,
außer während eines laufenden Trainings. Das Fenster zeigt den Countdown.
Laufende Einheiten werden alle fünf Sekunden lokal gesichert. Nach einem Absturz
wird Wiederherstellen oder Speichern angeboten. Beim Wiederherstellen bleibt das
Training pausiert, bis du bewusst fortsetzt. Die letzten Sekunden seit der letzten
erfolgreichen Sicherung können fehlen.

## Projektstruktur

- `server/app/static/`: Web-Oberfläche und Trainingsdiagramme.
- `server/app/`: API, Anmeldung, PostgreSQL und Datenbankmigrationen.
- `cados/connector_app.py`: kleines Connector-Fenster und Menüleiste.
- `cados/connector_pairing.py`: Anmeldung durch einmalige Bestätigung im Browser.
- `cados/connector.py`: lokale Trainingssteuerung und Serververbindung.
- `cados/core/`, `cados/models/`, `cados/services/`: gemeinsam verwendete Logik,
  Bluetooth, Messwerte, Speicherung und Synchronisation.
- `cados/assets/`: App-Icon und mitgelieferte Workouts.
- `scripts/build_macos_connector.py`: eigenständige macOS-App und DMG erstellen.
- `tests/`: lokale automatisierte Tests.

PySide6 wird weiterhin für das kleine Connector-Fenster benötigt.
Serverinstallation und Betrieb: [server/README.md](server/README.md).

## Entwicklung

Die CADOS-Flutter-Anwendung liegt unter [`flutter_app`](flutter_app/README.md)
(Paket `cados_app`). Heute, Workouts, Training und Einstellungen verwenden responsive
Material-3-Navigation. Anmeldung, sichere Tokenablage und Sitzungswiederherstellung
nutzen die vorhandenen `/api/v1/auth`-Endpunkte. Die Serveradresse ist in Einstellungen
konfigurierbar; Standard ist `https://cados.saibot.at`.

Reale Sync-Snapshots liefern Profil/FTP, Workoutbibliothek, geplante Einheiten und
Trainingshistorie. Revisionen, Löschmarkierungen, Freigaben und unbekannte Felder
bleiben erhalten. Es gibt keine Demo-Daten. Ohne Daten, Netzwerk oder Geräte zeigt
die App ehrliche Leer-/Fehler-/Verbindungszustände. Kalender-/Workoutbearbeitung bleibt offen. Reale Bibliotheksworkouts und geplante
Einheiten lassen sich mit ihrem Profil-FTP lokal ausführen. Start wartet auf neue
positive Leistung; Zielwatt werden begrenzt und höchstens einmal pro Sekunde gesendet.
Die echte Plan-ID und der ursprüngliche Workoutpayload bleiben an der Einheit.

Trainer- und HR-Controller mit universal_ble, Backoff 1/2/4/8/16 Sekunden,
Gerätepräferenzen und dauerhaftem rotiertem Log bleiben erhalten. Diagnostik und
Dateiexport befinden sich sekundär unter Einstellungen → Diagnostik & Support.
Nach Trainer-Reconnect werden Abonnements und Steuerfreigabe erneuert; Start und
Zielleistung werden nicht automatisch gesendet. Der reine Dart-Workoutkern mit
bestehenden Paritätstests ist über einen gesonderten Sessioncontroller mit der
Trainersteuerung verbunden. Geräteausfall, veraltete Leistung und App-Hintergrund
pausieren mit ausdrücklicher Fortsetzung; HR-Ausfall stoppt die Einheit nicht.
Befehlsfehler werden sichtbar. Wiederherstellung startet niemals automatisch.

Ein atomarer lokaler Journalspeicher sichert etwa alle fünf Sekunden und bei
Zustandswechseln. Beim Beenden wird dieselbe stabile Session-UUID in die dauerhafte
Outbox übernommen. Der bestehende POST-Sync-Pfad überträgt die echten Samples;
fehlende Sensorwerte bleiben leer. Fehlgeschlagene Uploads bleiben über Neustarts
erhalten und werden nach Anmeldung/Refresh oder manuell wiederholt. Erst passende
autoritative Bestätigung entfernt die Einheit. Anschließend wird der Katalog samt
serverseitig aktualisiertem Profilpuls geladen. Speichergrenzen, Wiederherstellung
und weitere Details stehen im Flutter-README. Adaptive ERG, lokale vollständige
Metrik-/FTP-Test-Parität sowie Editorfunktionen sind weiterhin offen.

Real beobachtet wurden KICKR CORE FTMS-Befehlsannahme (Steuerfreigabe, Zielwatt,
Start und Stop), gleichzeitiger Garmin-Fenix-HR-Empfang und HR-Reconnect.
HR-Werte werden beim ersten Empfang und danach bei jedem 25. Wert protokolliert.
Physische Widerstandsänderung beim Treten bleibt aufgeschoben. Weitere Geräte,
native Exportdialoge und Plattform-Lebenszyklen benötigen zusätzliche Validierung.
Python-Connector und FastAPI/PostgreSQL bleiben unverändert. Die CI führt nur
Formatierung, Analyse und Tests aus; Builds sind bis zum Abschluss der Migration
gesperrt und später ausschließlich für Windows vorgesehen.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m cados
```

`python -m cados` und `cados-connector` öffnen ausschließlich den Connector.
`cados-connector-cli` startet ihn ohne Fenster mit bereits eingerichteter Anmeldung.
Mit `python -m cados --login` kann die Anmeldung erneut geöffnet werden.
Die alten Projektstarter und die vollständige Desktop-Oberfläche gibt es nicht mehr.

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/build_macos_connector.py
```

Der macOS-Build erzeugt `release/CADOS-Connector-macOS.dmg`.
Release-Veröffentlichung und Versionshinweise sind in `server/README.md` beschrieben.
Windows bleibt im gemeinsamen Connector-Code berücksichtigt; dieses Build-Skript
liefert ausschließlich das macOS-Paket.
Persönliche Daten, virtuelle Umgebungen und Build-Ausgaben gehören nicht ins Git-Repository.

## Workout-Dateien

JSON und Zwift-ZWO werden im Browser importiert. Der Workout-Builder unterstützt
konstante Blöcke und Rampen mit sofortiger Diagrammvorschau.

### JSON-Schema

```json
{
  "name": "Workout-Name",
  "description": "Optionale Beschreibung",
  "author": "Autor (optional, Standard: Unbekannt)",
  "ftp_reference": 250,
  "blocks": [ ... ]
}
```

| Feld | Pflicht | Beschreibung |
|------|---------|--------------|
| `name` | Ja | Name des Workouts |
| `description` | Nein | Beschreibung |
| `author` | Nein | Autor (Standard: "Unbekannt") |
| `ftp_reference` | Nein | Referenz-FTP in Watt |
| `blocks` | Ja | Liste der Blöcke (mind. 1) |

### Block-Typen

#### Steady (Konstante Leistung)

```json
{
  "type": "steady",
  "label": "Sweet Spot",
  "duration_sec": 480,
  "target_pct_ftp": 0.88,
  "target_cadence": 92
}
```

| Feld | Pflicht | Beschreibung |
|------|---------|--------------|
| `type` | Ja | `"steady"` |
| `label` | Nein | Block-Bezeichnung |
| `duration_sec` | Ja | Dauer in Sekunden (> 0) |
| `target_pct_ftp` | * | Zielleistung als FTP-Anteil (z.B. 0.88 = 88%) |
| `target_watts` | * | Zielleistung in Watt (alternativ zu pct_ftp) |
| `target_cadence` | Nein | Zielkadenz in RPM |

*Mindestens `target_pct_ftp` oder `target_watts` erforderlich.

#### Ramp (Rampe)

```json
{
  "type": "ramp",
  "label": "Warmup",
  "duration_sec": 600,
  "start_pct_ftp": 0.50,
  "end_pct_ftp": 0.75,
  "target_cadence": 90
}
```

| Feld | Pflicht | Beschreibung |
|------|---------|--------------|
| `type` | Ja | `"ramp"` |
| `label` | Nein | Block-Bezeichnung |
| `duration_sec` | Ja | Dauer in Sekunden (> 0) |
| `start_pct_ftp` | * | Startleistung als FTP-Anteil |
| `start_watts` | * | Startleistung in Watt |
| `end_pct_ftp` | * | Endleistung als FTP-Anteil |
| `end_watts` | * | Endleistung in Watt |
| `target_cadence` | Nein | Zielkadenz in RPM |

*Start: mindestens `start_pct_ftp` oder `start_watts`. Ende: mindestens `end_pct_ftp` oder `end_watts`.

### Beispiel-Workouts

- `Endurance 60.json` – Grundlagen-Ausdauer
- `Sweet Spot 3x10.json` – Sweet Spot
- `VO2max 4x4.json` – VO2max-Intervalle
- `FTP Ramp Test (ERG).json` – FTP-Rampentest
- `Over Unders 3x12.json` – Over/Under-Intervalle

Ungültige Dateien werden protokolliert und übersprungen. Zahlen müssen zum
jeweiligen Feld passen; nicht endliche Werte, negative Ziele und nicht ganzzahlige
Dauern werden abgewiesen.

## Trainer, Gurte und Uhren auswählen

In der Web-Übersicht **Trainer & Pulssensor auswählen** öffnen, Geräte suchen und
Trainer sowie optionalen Pulssensor getrennt verbinden. CADOS merkt sich die Auswahl
auf diesem Computer und versucht die Wiederverbindung. Ein Trainerwechsel während
einer laufenden oder pausierten Einheit ist gesperrt. Ohne Internet gibt es dieselbe
Auswahl in der lokalen Trainingsansicht des Connectors.

Die unterstützten Protokolle, Hersteller-Einordnung und Grenzen stehen in
[GERAETE_KOMPATIBILITAET.md](GERAETE_KOMPATIBILITAET.md).
