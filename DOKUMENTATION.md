# Cados - Indoor-Cycling Trainer

## Überblick

Cados ist eine Desktop-Anwendung für strukturiertes Indoor-Cycling mit direkter Trainersteuerung über Bluetooth (FTMS). Die App steuert einen Wahoo KICKR (oder kompatiblen Smart Trainer), zeigt Live-Daten an und führt durch vorgegebene Workout-Pläne.

## Systemvoraussetzungen

- macOS oder Windows 10/11 mit Bluetooth
- Python 3.11+
- Wahoo KICKR oder kompatibler FTMS-Trainer

## Installation

Auf macOS wird Cados per Doppelklick auf `Cados.app` gestartet. Die App richtet
die benötigte Python-Umgebung automatisch unter
`~/Library/Application Support/Cados/.venv` ein, damit der Projektordner klein
bleibt. `Cados.app` ist ein Starter für diesen Projektordner und muss darin
bleiben; es ist kein eigenständiges, verschiebbares App-Paket.

Beim ersten Bluetooth-Scan fragt macOS eventuell nach Bluetooth-Rechten. Erlaube
dann Cados bzw. Python den Zugriff unter Systemeinstellungen > Datenschutz &
Sicherheit > Bluetooth.

Manuell kann Cados weiterhin so gestartet werden:

```bash
python3 -m venv ~/Library/Application\ Support/Cados/.venv
~/Library/Application\ Support/Cados/.venv/bin/python -m pip install -e .
~/Library/Application\ Support/Cados/.venv/bin/python -m cados
```

## Projektstruktur

```
Cados/
├── cados/
│   ├── __main__.py          # Einstiegspunkt für python -m cados
│   ├── config.py            # Konfiguration & Pfade
│   ├── core/
│   │   ├── workout_engine.py  # Training-Logik & Zustandsmaschine
│   │   ├── training_metrics.py # Zeitgewichtete Messwerte & Kennzahlen
│   │   ├── workout_loader.py  # JSON-Workout-Parser
│   │   ├── zwo_importer.py     # Zwift-ZWO-Import
│   │   └── zones.py          # Leistungszonen (Z1-Z7)
│   ├── models/
│   │   ├── profile.py        # Benutzerprofil
│   │   ├── session.py        # Session-Aufzeichnungen
│   │   └── workout.py        # Workout-Datenmodelle
│   ├── services/
│   │   ├── storage.py        # Lokale SQLite-Datenbank
│   │   ├── workout_catalog.py # Mitgelieferte, lokale und Online-Workouts
│   │   ├── workout_library.py # HTTPS-Client der zentralen Bibliothek
│   │   ├── trainer.py        # Bluetooth-Trainersteuerung
│   │   ├── trainer_control.py # Befehls-Worker mit Wiederholungsversuchen
│   │   ├── async_loop.py     # Gemeinsamer Bluetooth-Eventloop
│   │   └── hr_monitor.py     # Herzfrequenzsensor
│   ├── ui/
│   │   ├── main_window.py    # UI-Abläufe & Session-Speicherung
│   │   ├── main_window_view.py # Fensteraufbau & Layout
│   │   ├── library_widgets.py # Workout-Liste & Formatierung
│   │   ├── dialogs.py        # Profil-Dialog
│   │   ├── theme.py          # QSS-Stylesheet (Light-Theme)
│   │   └── widgets.py        # Workout-Timeline-Widget
│   └── assets/               # Icons, Logo & mitgelieferte Workouts
├── server/                    # Optionale zentrale Workout-Bibliothek
└── tests/                     # Automatische Tests
```

## Workout-Dateien

Über **Importieren** können CADOS-JSON-Dateien und übliche Zwift-Workouts (`.zwo`)
direkt ausgewählt werden. Der Import landet in der lokalen SQLite-Datenbank; die
Originaldatei muss anschließend nicht an ihrem bisherigen Ort bleiben. Unterstützt
werden in ZWO die Bausteine `Warmup`, `Cooldown`, `Ramp`, `SteadyState` und
`IntervalsT`. Freies Fahren und feste Watt-ZWO-Dateien werden mit einer verständlichen
Fehlermeldung abgewiesen, weil sie nicht eindeutig in den ERG-Ablauf von CADOS passen.

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

## Leistungszonen

| Zone | Name | FTP-Bereich | Farbe |
|------|------|------------|-------|
| Z1 | Recovery | 0-55% | Grau |
| Z2 | Endurance | 56-75% | Blau |
| Z3 | Tempo | 76-90% | Grün |
| Z4 | Threshold | 91-105% | Gelb |
| Z5 | VO2 Max | 106-120% | Orange |
| Z6 | Anaerobic | 121-150% | Rot |
| Z7 | Neuromuscular | >150% | Lila |

## Training

### Automatisches Verhalten

- **Pedal-to-Start**: Nach Klick auf "Workout starten" wartet Cados bis getreten wird
- **Auto-Pause**: Fällt die Leistung für 2 Sekunden auf 0 W, pausiert das Training automatisch
- **Verbindungsabbruch / Ruhezustand**: Bei fehlender Trainerverbindung oder einer Timerlücke über fünf Sekunden pausiert das Training. Die fehlende Zeit wird nicht als gefahrene Zeit erfasst.
- **Auto-Resume**: Sobald wieder getreten wird, setzt sich das Training fort
- **5-Sekunden-Rampe**: Bei jedem Start/Resume werden die Ziel-Watt über 5 Sekunden von 30 W auf den Sollwert gerampt

### Anzeige im Training

- **Ist-Watt / Soll-Watt**: Eingefärbt nach aktueller Leistungszone
- **Ist-Kadenz**: Grün wenn innerhalb ±5 RPM der Soll-Kadenz, sonst rot
- **±5 W Buttons**: Im Soll-Watt-Feld zum Anpassen der Zielleistung
- **Zeit**: Tatsächlich gefahrene Zeit und verbleibende Workout-Zeit werden getrennt angezeigt. Vor- und Zurückspringen verändert nur die Workout-Position.
- **Timeline**: Grafische Darstellung des Workout-Verlaufs mit aktueller Position
- **Status-Anzeige**: In der Kopfleiste (Warte auf Tritt / Aktiv / Pausiert)

### Steuerung

| Aktion | Beschreibung |
|--------|-------------|
| +5 W / -5 W | Zielleistung anpassen (Bias) |
| Nächster Block | Zum nächsten Workout-Block springen |
| Beenden | Training stoppen und zur Startseite |

## Benutzerprofile

Jeder Benutzer hat einen Namen und einen FTP-Wert. Der FTP-Wert wird zur Berechnung der Zielleistung aus den prozentualen Angaben in den Workouts verwendet.

## Einstellungen

Die Einstellungsdatei im lokalen CADOS-Datenordner enthält:

```json
{
  "tick_interval_ms": 250,
  "trainer_scan_timeout_sec": 5,
  "default_ftp": 250,
  "theme_mode": "light",
  "workout_library_url": "",
  "workout_library_token": ""
}
```

| Einstellung | Beschreibung | Standard |
|-------------|-------------|----------|
| `tick_interval_ms` | UI-Update-Intervall in ms | 250 |
| `trainer_scan_timeout_sec` | Bluetooth-Scan-Timeout | 5 |
| `default_ftp` | Standard-FTP für neue Profile | 250 |
| `theme_mode` | Farbschema (nur "light") | light |
| `workout_library_url` | HTTPS-Adresse der zentralen Bibliothek | leer |
| `workout_library_token` | Gemeinsames Zugriffstoken | leer |

## Trainer-Verbindung

Cados sucht automatisch nach einem Wahoo KICKR über Bluetooth FTMS. Der Verbindungsstatus wird in der Kopfleiste angezeigt. Die Verbindung wird alle 8 Sekunden automatisch versucht.
Ein Trainer gilt erst als bereit, wenn seine FTMS-Steuerfreigabe bestätigt wurde.
Steuerbefehle laufen seriell in einem Hintergrund-Worker. Nur bestätigte Befehle
werden als erfolgreich gespeichert; bei Fehlern erfolgt ein erneuter Versuch.
Pause und Stop haben Vorrang vor noch nicht gesendeten Wattvorgaben. Bereits
laufende Bluetooth-Befehle müssen zunächst beendet werden.

Die Gerätesuche liest Service-UUIDs aus den Advertising-Daten gemäß der
[Bleak-Scanner-API](https://bleak.readthedocs.io/en/latest/api/scanner.html).

## Datenspeicherung

Profile, Sessions, Messwerte und importierte Workouts liegen in einer lokalen
SQLite-Datei. Unter macOS ist das standardmäßig
`~/Library/Application Support/Cados/cados.sqlite3`, unter Windows
`%LOCALAPPDATA%\Cados\cados.sqlite3`. SQLite benötigt keinen Server und überträgt
keine Daten. Beim ersten Start werden vorhandene `data/profiles.json` und
`data/sessions.json` einmalig und atomar übernommen. Die JSON-Dateien bleiben als
Rückfallkopie erhalten.


Sessions enthalten zusätzlich den Trainingsstart, den verwendeten FTP-Wert,
die tatsächlich gefahrene Dauer, die Workout-Position, Durchschnittswerte, NP,
IF, TSS, Kalorien und Messdaten für Leistung, Kadenz, Herzfrequenz und Sollleistung.
NP und die beste vollständige Minute basieren auf zeitgewichteten Ein-Sekunden-Werten.
Fehlende Herzfrequenzmessungen gehen nicht als 0 bpm in den Durchschnitt ein.

Beim normalen Fensterschließen wird ein laufendes Training gestoppt und gespeichert.
Schlägt die lokale Speicherung fehl, bleibt das Fenster offen und die Session bleibt
für einen erneuten Versuch erhalten. Beim normalen App-Quit wird die Speicherung
ebenfalls versucht. Ein erzwungenes Prozessende oder Stromausfall kann eine noch
laufende, nicht gespeicherte Session weiterhin verlieren.

Alte Sessions bleiben lesbar; damals nicht gespeicherte Messdaten können nicht
nachträglich rekonstruiert werden. Beschädigte Altdaten werden nicht überschrieben
und die Migration wird in diesem Fall nicht als abgeschlossen markiert.

## Zentrale Workout-Bibliothek

Die Schaltfläche **Server** speichert URL und Zugriffstoken. **Online laden** holt
den Katalog; bei konfiguriertem Server geschieht dies zusätzlich beim App-Start.
Ein über **Importieren** hinzugefügtes Workout wird lokal gespeichert und danach im
Hintergrund auf dem Server veröffentlicht. Scheitert der Upload, bleibt die lokale
Kopie erhalten. Profile und gefahrene Trainings werden dabei nicht hochgeladen.

Der Server in `server/` verwendet die bereits vorhandene PostgreSQL-Datenbank und
stellt eine kleine, token-geschützte API bereit. Hinweise zu Docker, HTTPS und den
Umgebungsvariablen stehen in `server/README.md`. Ohne eingerichteten Server bleibt
die App vollständig offline benutzbar.

## Entwicklung und Tests

Aus dem Projektordner mit installierten Abhängigkeiten:

```bash
python -m pip install -e .
python -B -m unittest discover -s tests -v
```

Mit der bestehenden macOS-Umgebung:

```bash
"$HOME/Library/Application Support/Cados/.venv/bin/python" -B -m unittest discover -s tests -v
```

Die Tests verwenden simulierte Trainer und temporäre Datenordner. Qt-Tests laufen
mit `QT_QPA_PLATFORM=offscreen`; ohne installiertes PySide6 werden nur diese Tests
übersprungen. Die Tests prüfen unter anderem Bluetooth-Bestätigungen,
Wiederholungsversuche, Verbindungswechsel, Auto-Pause, Session-Speicherung beim
Schließen und Abwärtskompatibilität der Aufzeichnungen.

Ein Test mit einem echten Trainer und einer echten Server-PostgreSQL-Instanz ist davon
getrennt erforderlich, um das Verhalten dieser Geräte bzw. Dienste zu bestätigen.

## Versionsverwaltung

Quellcode, Tests, Workout-Vorlagen und die Starter gehören ins Repository.
`data/`, `logs/`, SQLite-Dateien, virtuelle Umgebungen, Build-Ausgaben und Zugangsdaten
werden durch `.gitignore` ausgeschlossen. Persönliche Trainingsdaten müssen
separat gesichert werden.
