# CADOS Flutter application

The production client lives in `flutter_app/` (package `cados_app`). Material 3
navigation provides Heute, Workouts, Training and Einstellungen on desktop and mobile.
Runtime uses real HTTP, secure token storage, universal_ble, file device preferences
and durable diagnostics. There are no bundled demo accounts, workouts or telemetry.
The Python connector and FastAPI/PostgreSQL server remain unchanged.

Einstellungen accepts an HTTPS server origin (default `https://cados.saibot.at`). Login
posts email/password to `/api/v1/auth/login`, stores the returned bearer token in
platform secure storage, and restores sessions with `/api/v1/auth/me`. Logout calls
`/api/v1/auth/logout` and clears local credentials; offline revocation failures are
reported. Tokens are scoped to their issuing origin and redirects are disabled.
Passwords, tokens and HTTP response bodies never enter diagnostics. Android backup
is disabled for secure-storage compatibility; Apple runners have keychain entitlements.
Linux secure storage requires the system Secret Service and libsecret development
package. Native plugin operation still needs validation on target hardware.

Authenticated `/api/v1/sync` snapshots populate profiles/FTP, workout library,
upcoming calendar items and training history. Envelopes retain revision, deleted,
shared, publisher and unknown fields. Tombstones are excluded from presentation;
only completed sessions with a matching plan_id complete a plan, as in static JS.
Unknown record kinds remain preserved. Actual selected workouts now execute locally
and completed/stopped sessions upload through the existing POST sync contract.
Profile, workout and calendar editing remain deferred.
Absent network/data/devices show explicit unavailable/empty/disconnected states.

## Architecture

- `lib/core`: pure project-owned device/preferences/diagnostic ports and connection
  phases, with no Flutter or BLE-plugin imports.
- `lib/application`: the reusable ChangeNotifier-based connection controller.
- `lib/features/trainer`: FTMS protocol, transport contract and trainer controller.
  A successful transport connection means discovery, subscriptions and Request
  Control all succeeded. Existing power range checks and Start/Pause/Stop remain.
- `lib/features/heart_rate`: plugin-independent HR transport, measurement parser
  and separate controller. Scan `180D`, explicitly select a sensor, subscribe
  `2A37`; decode 8/16-bit little-endian BPM and ignore optional trailing fields.
- `lib/features/workout`: pure Dart models and deterministic engine. No Flutter,
  BLE, timers, persistence, network or trainer commands.
- `lib/infrastructure/ble`: universal_ble adapters and shared scan ownership.
  Only one scan runs at once; trainer and HR can remain connected together.
  Stream routing uses per-device subscriptions, not global callback replacement.
- `lib/infrastructure/preferences`: two small atomic JSON files using `dart:io`.
  `path_provider` supplies the app-support directory; no extra preferences plugin.
- `lib/infrastructure/logging`: serialized, flushed file appends and desktop save
  through Flutter's `file_selector`. The diagnostic port is widget-independent.
- `lib/features/account`: API ports/config and observable session state.
- `lib/features/catalog`: pure Dart typed server records with original payloads.
- `lib/infrastructure/account`: HTTP, secure tokens and atomic server preferences.
- `lib/presentation`: responsive shell, account/catalog screens and device panels.
  Diagnostics and export are secondary support content in Einstellungen.
  `main.dart` composes dependencies; tests inject fakes.

## Connection and diagnostics behavior

Each selected device has idle/connecting/connected/reconnecting/failed phases;
scanning is shown separately because it can coexist with an existing connection.
Disconnect or Bluetooth-off triggers at most five retries after 1, 2, 4, 8 and
16 seconds. Attempts are serialized; explicit disconnect cancels retries and
invalidates late setup completion. Setup can take up to plugin operation timeouts
before cancellation cleanup finishes. Disposal cancels timers and subscriptions,
waits for pending setup cleanup, then closes transports and logging.

Trainer reconnect discovers services, subscribes again and requests control before
ERG-ready. It **never** sends a target or Start automatically. The session
coordinator requires explicit Resume and a new positive power measurement. Last trainer and HR IDs/names
are saved under app support `devices/`; on startup they appear as explicit
reconnect buttons. There is no automatic connection on app launch.

The shared log retains 250 lines in memory and appends timestamped events and raw
FTMS command/response bytes to app support `diagnostics/cados.log`, across launches.
The active file rotates at 1 MiB and retains three bounded generations. It contains
device names and telemetry, no account credentials or tokens. Copy uses the bounded
view; **Datei speichern** flushes and streams the current bounded file to the selected
location on Linux, Windows and macOS. The macOS sandbox permits user-selected writes.
Android/iOS keep the durable file and clipboard; a mobile share action is deferred.
Web is not supported by this `dart:io` application composition. Disk write failures
are surfaced by export.

## Exact workout parity slice

`test/workout_engine_test.dart` references the representative Python fixtures in
`tests/test_workout_engine.py` and `cados/models/workout.py`:

- FTP resolution: explicit FTP, template reference, default 200 W; percentages
  override absolute watts. Python ties-to-even rounding is explicit.
- 10-second 40–80% ramp at FTP 250: 100/150/200 W at 0/5/10 seconds.
  Following 88% steady block resolves to 176/220/264 W at FTP 200/250/300.
- Start waits for supplied positive power without advancing time. Five-second
  startup ramp begins at 30 W; three-second block transition smoothing.
- Deterministic ticks cross block boundaries and clamp completion. Negative dt
  becomes zero; gaps over five seconds manually pause without counting time.
- Two seconds of zero power auto-pause; supplied positive telemetry resumes with
  a ramp. Disconnect pauses without counting missing time. Manual pause/resume,
  stop/restart, cumulative watt adjustment and target clamp 0–32767 are covered.

This is **not full Python WorkoutEngine parity**: adaptive ERG, block navigation,
profile editing and zones remain deferred. Time-weighted local metrics, FTP-test
cadence termination, local FTP-test assessment and normalized power/TSS summaries
now use submitted real samples. The server still independently verifies and can
augment FTP-test results. Session execution, journal
and acknowledgement are now integrated as described below. The Dart constructor rejects empty/nonpositive-duration blocks
and nonfinite inputs instead of accepting malformed templates. No rider input or
wall-clock timer is needed to execute these tests.

## Lokales Training und Wiederherstellung

`WorkoutParser` prüft die Kombination aus Servervalidierung und Python WorkoutLoader:
1–2000 Steady-/Ramp-Blöcke, positive ganzzahlige Dauer/Kadenz, positive endliche
FTP-Anteile, ganzzahlige absolute Wattziele bis 32767 und höchstens 24 Stunden/
2 MB pro Workout. FTP-Anteile haben Vorrang vor absoluten Zielen. Für den Produktstart
wird genau ein synchronisiertes Profil mit FTP 30–2000 W verlangt; es gibt keinen
Standard-FTP und kein Ersatzworkout. Metadaten/Originalpayload bleiben erhalten.
Heute übernimmt die echte Plan-ID, Workouts bereitet das echte Bibliotheksworkout vor.

Der `WorkoutSessionController` serialisiert Zeitgeber, FTMS-Befehle und Sicherungen.
Vor Start wird die Einheit gesichert, dann der reale FTMS-Start bestätigt. Die Engine
wartet auf eine neue positive Messung. Zielwatt werden nur laufend, höchstens einmal
pro Sekunde und nur bei geändertem effektivem Wert gesendet; Trainerbereich und
Schrittweite gelten. Die angezeigte Zielleistung ist der zuletzt bestätigte Wert.
Start-/Übergangsrampen und ±5 W verwenden die bestehende reine Dart-Engine.

Pause/Fortsetzen/Beenden verwenden reale bestätigte FTMS-Befehle. Fehlgeschlagene
Befehle werden sichtbar und niemals als Erfolg gewertet. Nach Verbindungsverlust,
mehr als drei Sekunden fehlender Leistung, einer Zeitlücke über fünf Sekunden oder
App-Hintergrund wird pausiert; Wiederverbindung startet nichts automatisch.
Auch nach Nullleistungs-Autopause ist ausdrückliches Fortsetzen erforderlich.
HR-Ausfall pausiert das Workout nicht; fehlende/veraltete Werte bleiben leer.
Gerätewahl liegt in Einstellungen; beliebige Test-Wattknöpfe sind entfernt.

Das atomare Journal unter App-Support `training/journal.json` enthält Sicherung und
Outbox gemeinsam. Sicherungen erfolgen etwa alle fünf Sekunden sowie vor Start,
bei Pause/Hintergrund/Beenden. Eine erfolgreiche Finalisierung entfernt die Sicherung
und legt die Session im selben atomaren Dateiaustausch in die Outbox. Temporäre,
unvollständige Schreibvorgänge ersetzen keine gültige Datei. Fehler werden sichtbar;
beschädigte oder zu große Dateien werden nicht überschrieben. Die Grenze beträgt
64 MiB insgesamt und 20 ausstehende Sessions; Messwerte je Einheit sind auf
16 MiB/86401 Einträge begrenzt. Bei einer Grenze pausiert das Training mit Fehlermeldung.
Der Upload prüft zusätzlich die Servergrenze von 20 MB. Keine Tokens im Journal.
Das Journal verwendet Dateiflush und atomare Umbenennung; die Sicherheit bei hartem
Stromverlust hängt zusätzlich von Dateisystem und Gerät ab. Gleichzeitige Prozesse,
die dasselbe Journal öffnen, werden derzeit nicht unterstützt.

Nach Neustart wird eine unvollständige Einheit angeboten: Wiederherstellen lädt
Workoutpayload, Profil/FTP, Zeiten, Plan-ID, Messwerte und stabile Session-UUID
pausiert. Erst die explizite Fortsetzung mit ursprünglichem Konto und realem Trainer
startet wieder. Verwerfen verlangt eine bewusste Bestätigung. Beenden benötigt eine
bestätigte Trainerantwort; bei unterbrochener BLE-Verbindung bleibt die Sicherung
erhalten, bis erneut verbunden und beendet wird.

Samples verwenden die Python-Felder `segment`, `elapsed_sec`, `duration_sec`,
`workout_elapsed_sec`, `watts`, `cadence`, `heart_rate`, `target_watts`, ergänzt um
`block_index`. Pausenzeiten werden nicht als gefahrene Zeit gezählt. Fehlende Kadenz/
HR bleiben null. Start-/Abschlusszeitstempel stehen im Sessionpayload. Die App
berechnet aus realen Samples tick-unabhängig Durchschnitt und Maximum für Leistung,
Kadenz und Herzfrequenz sowie beste Minute, mechanische Arbeit, Normalized Power,
Intensity Factor und TSS. Der vollständige Messverlauf rekonstruiert diese Werte
nach einer Wiederherstellung; Pausen unterbrechen gleitende Leistungsfenster.
FTP-Rampentests enden nur im Step-/Stufe-Teil nach zuvor gemessener positiver Kadenz,
nicht bei fehlender Kadenz. Die lokale 75-%-Auswertung verwendet ausschließlich die
beste zusammenhängende Minute gemessener Leistung aus diesem Belastungsteil. Der
Server prüft und ergänzt die Auswertung weiterhin autoritativ.

Outbox-Uploads sind an ursprüngliches Konto und Server gebunden. POST `/api/v1/sync`
sendet `{changes:[record]}` mit `kind=session`, `shared=false`, `deleted=false`,
`revision=0` und stabiler UUID. Nur passende autoritative Bestätigung und anschließender
Katalog-Refresh entfernen den lokalen Eintrag. 401/409/Netzwerkfehler behalten ihn.
Ein späterer Versuch erkennt bereits gespeicherte Sessions anhand UUID und Payload
(unter Berücksichtigung der serverseitig ergänzten HR-/FTP-Auswertung). Konflikte
werden nie überschrieben. Nach Anmeldung/Refresh und per Schaltfläche wird erneut
versucht; Profil-Maximalpuls wird aus dem aktualisierten GET-Snapshot übernommen.

## Validation and remaining hardware evidence

Observed on real hardware: Windows KICKR CORE FTMS scan/connect, subscriptions,
Request Control, target power, Start and Stop acceptance; simultaneous Garmin Fenix
HR reception and HR reconnect. HR diagnostics record the first value and each 25th
value per connection, without raw packet spam. Physical resistance while pedaling
remains deferred. No pedaling test was performed or requested in this migration.
Native export dialogs and broader platform lifecycle behavior still need validation.

```bash
cd flutter_app
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
# From repository root:
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
git diff --check
```

GitHub Actions runs formatting, analysis and tests only. No build is part of this
phase; eventual builds are reserved for Windows after the entire migration.
