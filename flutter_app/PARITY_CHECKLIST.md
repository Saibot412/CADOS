# CADOS Flutter – Gleichwertigkeits- und Release-Checkliste

Stand: Flutter 1.0.0, Migration Punkte 1–5 softwareseitig abgeschlossen.

Legende: **erfüllt** = im Flutter-Produkt implementiert und automatisiert geprüft;
**extern** = absichtlich weiter im FastAPI-Web-/Adminprodukt; **offen** = benötigt
noch echten Produktions-, Windows- oder Hardware-Nachweis.

| Bereich | Python/Web-Referenz | Flutter-Stand | Nachweis / Grenze |
|---|---|---|---|
| Konto | Login, Logout, Kontoauswahl | **erfüllt** für einen aktiven Server/Account | HTTPS-Origin, `/auth/login`, `/auth/me`, `/auth/logout`, sicherer Token; Kontowechsel über Ab-/Anmeldung statt Python-Mehrkontenliste |
| Registrierung/Passwort/Admin | Web-Registrierung, Passwort- und Benutzerverwaltung | **extern** | Bleibt serverseitige Web-/Adminfunktion; keine Adminrechte im Trainingsclient |
| Connector-Pairing/-Update | Browser koppelt Python-Connector; DMG-Selbstupdate | **nicht zutreffend** | Flutter steuert BLE selbst; Windows-Paket wird als vollständiges GitHub-Release aktualisiert |
| Profil und Zonen | Profil, FTP, Gewicht, Max-HR, Leistungs-/HF-Zonen | **erfüllt** | Revisionsgebundene Mutation, autoritativer Refresh, explizite FTP-Übernahme |
| Workoutbibliothek | Anzeigen, Erstellen, Kopieren, Bearbeiten, Import, Löschen | **erfüllt** | Geteilte Records geschützt; JSON/ZWO bytegenau; unbekannte Felder erhalten |
| Kalender/Planung | Monat/Tag, Start, Abschlusszuordnung | **erfüllt** | Lokale Kalendertage, Tombstones, fehlende/vergangene Pläne nicht startbar |
| Geräteauswahl | FTMS-Trainer und Bluetooth-HR getrennt | **erfüllt**, Hardwarebreite **offen** | universal_ble, explizite Auswahl, gespeicherte Geräte, gemeinsamer Scanbesitz |
| FTMS-Steuerung | Request Control, Ziel, Start/Pause/Resume/Stop | **erfüllt**, native Releaseprüfung **offen** | Bestätigung per Control-Point-Indication; keine automatische Last nach Reconnect |
| Adaptive ERG | Python-Regelung | **erfüllt**, physische Wirkung **offen** | Opt-in standardmäßig aus; Python-paritätische Mathematik; nur bestätigte Ziele sichtbar |
| Training | Block-/Rampenausführung, Pausen, Zielbegrenzung | **erfüllt** | Reiner Dart-Kern und Sessioncontroller automatisiert geprüft |
| Journal/Recovery | Lokale Sicherung und Wiederaufnahme | **erfüllt** | Atomarer Checkpoint, stabile UUID, bewusste Wiederherstellung, Größenlimits |
| Outbox/Sync | Offline speichern, später synchronisieren | **erfüllt** | Konto-/Serverbindung, idempotente Bestätigung, 401/409/Offline erhalten Daten |
| Historie/Ergebnis | Sessions, Metriken, FTP-Test | **erfüllt** | Echte Samples, zeitgewichtete Metriken, NP/IF/TSS, autoritativer Serverrefresh |
| Diagnostik/Export | Rotierendes Log, Datei speichern | **erfüllt**, Windows-Dialog **offen** | Keine Tokens/Passwörter/HTTP-Bodies; nativer Dateidialog am Release prüfen |
| Lokale Browseransicht | Python-Connector auf `127.0.0.1` | **nicht zutreffend** | Flutter ist selbst die lokale Trainingsoberfläche und braucht keinen Browser |
| Server/PostgreSQL | FastAPI, Sync, Import, Admin, Datenbank | **extern und weiterverwendet** | Flutter spricht ausschließlich authentifiziert mit FastAPI, nie direkt mit PostgreSQL |
| Mobile Sharing/Web | Connector-/Web-Sonderpfade | **außerhalb Windows 1.0.0** | Flutter-Web wird wegen `dart:io` nicht unterstützt; mobile Share-Aktion bleibt zurückgestellt |

## Release-Gates

- [x] Punkte 1–5 vollständig implementiert und jeweils durch Flutter-/Python-Tests und CI bestätigt.
- [x] Python-Connector bleibt als Rückfalloption im Repository und wird nicht entfernt.
- [x] Produktions-E2E-Harness liegt außerhalb der normalen Suite und liest Credentials nur aus der Umgebung.
- [ ] Echten E2E-Lauf gegen `https://cados.saibot.at` erfolgreich ausführen: Login, `/auth/me`, Restore, `/sync`, temporäres Workout, absichtlicher 409, temporäre Session, 401/Offline-Probe und Tombstone-Bereinigung.
- [ ] Windows-Workflow auf nativem Runner erfolgreich: Format, Analyze, Tests und Release-Build.
- [ ] Vollständiges Runner-Verzeichnis als ZIP und SHA-256 veröffentlichen; nicht nur die EXE.
- [ ] Frisch entpacktes Paket auf Windows starten und Secure Storage, Dateidialog sowie BLE-Verbindungen ohne Pedalbelastung prüfen.
- [ ] Später, erst bei gesundheitlicher Freigabe: tatsächliche ERG-Widerstandsänderung unter Last validieren.

## Produktions-E2E sicher ausführen

Credentials werden weder committed noch geloggt. Das Skript erzeugt kryptografische
UUID-v4-Werte, verwendet ausschließlich FastAPI und tombstoned temporäres Workout und
temporäre Session in einem `finally`-Block.

```bash
cd flutter_app
CADOS_E2E_EMAIL='…' CADOS_E2E_PASSWORD='…' \
  flutter test tool/production_e2e_test.dart
```

Optional kann `CADOS_E2E_SERVER` gesetzt werden; Standard ist
`https://cados.saibot.at`. Der normale Befehl `flutter test` führt diesen expliziten
Produktionslauf nicht mit aus.

## Windows-Release

`.github/workflows/flutter-windows-release.yml` kann manuell einen 30 Tage verfügbaren
CI-Artefaktbuild erzeugen. Ein Tag `flutter-v*` erzeugt zusätzlich ein GitHub-Release
mit vollständigem portablem ZIP und `.sha256`. Das Paket ist kein Installer und nicht
codesigniert; `cados_app.exe`, DLLs und `data/` müssen zusammenbleiben.
