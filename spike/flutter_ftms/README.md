# CADOS Flutter migration alpha

Flutter 3.47.3 / Dart 3.13.3, `universal_ble 2.3.0`. This remains an isolated
client under `spike/flutter_ftms`; the Python connector and FastAPI/PostgreSQL
server are preserved. No workout is recorded or sent to the server yet.

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
- `lib/presentation`: trainer screen, HR panel and shared diagnostic panel.
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
ERG-ready. It **never** sends a target or Start automatically. The pure workout
engine is not wired to these transport controls. Last trainer and HR IDs/names
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

This is **not full Python WorkoutEngine parity**: adaptive ERG, metrics, FTP-test
cadence termination/results, session/checkpoint persistence, session acknowledgement,
block navigation, profile management, catalog/JSON loading, zones and network sync
remain deferred. The Dart constructor rejects empty/nonpositive-duration blocks
and nonfinite inputs instead of accepting malformed templates. No rider input or
wall-clock timer is needed to execute these tests.

## Validation and remaining hardware evidence

Existing Windows KICKR CORE evidence establishes scan/connect, FTMS subscription,
Request Control, 100 W target, Start and Stop success responses. It does not prove
physical resistance under load. New simultaneous trainer/HR operation, actual HR
sensor packets, Bluetooth toggle/power-loss recovery, desktop save dialogs and
platform lifecycle behavior still require future device validation. Physical
resistance under load stays deferred. **No pedaling or rider test is requested
for this development block.**

```bash
cd spike/flutter_ftms
flutter pub get
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build linux --release
# From repository root:
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests
git diff --check
```

GitHub Actions runs on pushes and pull requests, uploads Linux/macOS/Android/Windows
artifacts, and performs a no-codesign iOS build. Desktop export uses the installed
package API; non-Linux builds and GitHub-hosted workflow execution are not locally
verified.
