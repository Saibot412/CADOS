# CADOS Flutter FTMS Spike

Technischer Test für die geplante CADOS-Flutter-App. Diese App prüft ausschließlich,
ob ein Bluetooth-FTMS-Smarttrainer plattformübergreifend gefunden, ausgelesen und im
ERG-Modus gesteuert werden kann. Sie ersetzt noch nicht CADOS und speichert keine
Trainingseinheit.

## Unterstützte Tests

- Scan ausschließlich nach Fitness Machine Service `0x1826`
- bewusste Auswahl eines Trainers
- Prüfung von Indoor Bike Data `0x2AD2` und Control Point `0x2AD9`
- optionale Prüfung der FTMS-Features und des Leistungsbereichs
- Anzeige von Leistung und Kadenz
- Request Control
- Zielleistung 100, 150 und 200 Watt
- Start/Fortsetzen, Pause und Stop
- lesbares Diagnoseprotokoll mit Rohbytes der Steuerbefehle und Antworten

BLE wird über `universal_ble 2.3.0` hinter einer eigenen `TrainerTransport`-Schnittstelle
angesprochen. Die reine FTMS-Protokolllogik ist vom Plugin und von Flutter-Widgets getrennt.

## Sicherheit

Dies ist ein experimenteller Hardwaretest.

1. Rad und Trainer sicher aufstellen.
2. Andere Apps wie Zwift, MyWhoosh und den bisherigen CADOS-Connector vollständig schließen.
3. Beim Trainer bleiben.
4. Immer zuerst `100 W` senden.
5. Erst danach Start/Pause/Stop und 150/200 W prüfen.
6. Bei unerwartetem Widerstand sofort aufhören zu treten und den Trainer vom Strom trennen.

## Auf einem Mac starten

Flutter Stable installieren und dann im Repository:

```bash
cd spike/flutter_ftms
flutter pub get
flutter doctor -v
flutter run -d macos
```

macOS muss den Bluetooth-Zugriff erlauben. Wenn der Zugriff zuvor abgelehnt wurde:

`Systemeinstellungen → Datenschutz & Sicherheit → Bluetooth → CADOS FTMS Test`

Alternativ erzeugt der GitHub-Actions-Workflow **CADOS Flutter FTMS Spike** ein
nicht notarisiertes macOS-ZIP. Nach dem Entpacken kann deshalb
`Rechtsklick → Öffnen` oder die Freigabe unter Datenschutz & Sicherheit nötig sein.

## Testablauf mit dem echten Trainer

1. Trainer einschalten und auf der App **8 Sekunden nach FTMS suchen** wählen.
2. Den richtigen Trainer anhand Name und RSSI verbinden.
3. Prüfen, ob oben **ERG bereit** erscheint.
4. 20–30 Sekunden locker treten. Leistung und Kadenz müssen regelmäßig aktualisiert werden.
5. `100 W` drücken und die Control-Antwort **Erfolg** im Protokoll prüfen.
6. `Start/Fortsetzen` drücken und etwa eine Minute treten.
7. Nacheinander `150 W`, `200 W` und wieder `100 W` senden. Widerstandsänderung und jede Antwort notieren.
8. `Pause`, danach `Start/Fortsetzen`, zuletzt `Stop` testen.
9. Während 100 W Bluetooth kurz deaktivieren oder den Trainer kurz stromlos machen. Die App darf nicht abstürzen und muss **Verbindung getrennt** zeigen.
10. Erneut scannen, verbinden und 100 W senden.
11. **Protokoll kopieren** und zusammen mit Plattform, Betriebssystem, Trainer-Modell und Firmware zurückmelden.

## Go-Kriterien

- Trainer wird auf Mac, Windows und Android gefunden.
- Indoor-Bike-Daten laufen ohne längere Aussetzer.
- Request Control und alle Steuerbefehle werden mit Erfolg bestätigt.
- Die reale ERG-Leistung folgt 100/150/200 W plausibel.
- Trennung erzeugt keinen App-Absturz oder unkontrollierten Widerstand.
- erneutes Verbinden funktioniert.

Der Spike ist noch kein Nachweis für zuverlässigen Hintergrundbetrieb oder vollständiges
Offline-Training. Diese Lebenszyklus-Tests folgen erst nach bestandenem FTMS-Grundtest.

## Entwicklung und Prüfung

```bash
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter build linux --release
```

Aktueller lokaler Referenzstand: Flutter 3.47.3, Dart 3.13.3.
