# CADOS – Gerätekompatibilität nach dem 80/20-Prinzip

Stand: 10. September 2026. Diese Einteilung beschreibt Protokoll-Unterstützung,
keine mit allen genannten Modellen durchgeführten Hardwaretests. Eine belegte
80-%-Marktabdeckung lässt sich aus den öffentlichen Listen nicht ableiten.

## Ergebnis des Vergleichs

Zwift führt unterschiedliche Hardwareklassen: Nicht jeder dort nutzbare Trainer
kann den Widerstand automatisch steuern. Für CADOS ist ERG eine Voraussetzung.
[Zwift: kompatible Hardware](https://support.zwift.com/en_us/compatible-cycling-hardware-BkPlq7gr)

MyWhoosh empfiehlt unter anderem Wahoo KICKR/Core, Elite Direto XR/Suito T/Justo,
Tacx Neo und JetBlack Volt; bei Pulssensoren nennt es Garmin und Wahoo.
[MyWhoosh: Smart Equipment](https://mywhoosh.com/docs/which-smart-equipment-works-with-mywhoosh/)

ROUVY unterscheidet zahlreiche Modelle, Verbindungstypen und Zusatzfunktionen.
Die dortige Kompatibilität ist deshalb keine automatische Zusage für CADOS.
[ROUVY: Trainerliste](https://support.rouvy.com/hc/en-us/articles/14059132272529-Supported-Trainers)

**Entscheidung:** Zunächst markenübergreifende Bluetooth-Standards verbessern,
Geräte bewusst auswählen lassen und tatsächliche Fähigkeiten beim Verbinden prüfen.
Proprietäre Sonderprotokolle und neue Funkhardware werden nicht auf Verdacht ergänzt.

## Trainer

| Gruppe | CADOS 0.4.1 |
|---|---|
| Bluetooth-FTMS-Trainer mit Indoor Bike Data und ERG-Control-Point | Unterstützter Verbindungspfad; Leistungsbereich wird gelesen, sofern verfügbar. |
| Aktuelle Modelle der Familien Wahoo/KICKR, Elite, JetBlack und weitere Hersteller | Über denselben FTMS-Pfad, sofern Modell und Firmware diesen tatsächlich bereitstellen. Kein pauschales Markenversprechen. |
| Tacx, Saris, ältere Wahoo/Elite und andere Generationen | Modell/Firmware entscheidend. Ein gelisteter Markenname genügt nicht; ohne FTMS-ERG wird die Verbindung verständlich abgewiesen. |
| Unbekannte Marke mit FTMS-Service | Wird ebenfalls gefunden; keine Markenfreigabeliste nötig. |
| Reiner Leistungssensor, klassischer Rollentrainer, Bike ohne steuerbare Ziel-Leistung | Kein CADOS-ERG-Training in diesem Schritt. |
| Nur ANT+ FE-C, proprietäre Bluetooth-Steuerung, WLAN/Direct Connect, virtuelle Schaltung | Nicht ergänzt. Zwift/ROUVY-Unterstützung dieser Wege darf nicht auf CADOS übertragen werden. |

[Bluetooth SIG: Fitness Machine Service](https://www.bluetooth.com/specifications/specs/fitness-machine-service-1-0/)

## Herzfrequenz

Standardisierte Bluetooth-Herzfrequenzübertragung (HRS) funktioniert unabhängig von
der Marke. Damit ist der Verbindungspfad für entsprechende Gurte/Armsensoren von
Polar, Garmin, Wahoo, COROS, Coospo, Magene und unbekannten Herstellern vorhanden.
Es müssen das konkrete Modell und dessen aktivierter Sendemodus passen.

Zwift unterstützt ebenfalls BLE-/ANT+-Pulssensoren breit. CADOS verwendet hier
**nur Bluetooth**, nicht dessen komplette ANT+- und Zubehörabdeckung.
[Zwift: Zubehör und Herzfrequenz](https://support.zwift.com/ja/-ryfy2ixY)

Uhren müssen Herzfrequenz als Bluetooth-Sensor senden können. Eine Bluetooth-Verbindung
zur Hersteller-App allein reicht nicht. „Broadcast HR“, „Herzfrequenz senden“ oder
„Sensor-Modus“ aktivieren; bei belegter Verbindung die andere App trennen.
COROS beschreibt dafür einen eigenen Bluetooth-Sendemodus und mögliche
Verbindungsbeschränkungen. [COROS: Broadcast HR](https://support.coros.com/hc/en-us/articles/360040256991-Broadcasting-Heart-Rate)

ANT+-only-Gurte/Uhren sowie eine direkte Apple-Watch-Anbindung sind nicht enthalten.
Die Spezial- oder Companion-Anbindung anderer Plattformen wird damit nicht nachgebaut.
Ein Gerät, das ein Signal selbst als standardisiertes BLE-HRS bereitstellt, kann
wie jeder andere HRS-Sensor ausgewählt werden; es gibt keine CADOS-ANT+-Bridge.

## Was sich technisch verbessert hat

- Auswahl und getrenntes Merken von Trainer und Pulssensor auf diesem Computer.
- Wiederverbindung nur zu den gemerkten Geräten; kein automatischer Wechsel zu fremden Gurten.
- Erkennung über Service-UUIDs, auch ohne bekannten Namen; Markenbegriffe sind lediglich Suchhinweise.
- Verwendung des gefundenen BLE-Geräteobjekts, um zusätzliche implizite Scans zu vermeiden.
- Prüfung von ERG-Fähigkeit und optionalem Leistungsbereich samt Watt-Schrittweite.
- Getrennte FTMS-Pakete überschreiben fehlende Werte nicht mit Null.
- Ein fehlender/veralteter Kadenzwert beendet keinen FTP-Test. Gemessene 0 rpm weiterhin schon.
- Veraltete Leistung pausiert ein laufendes Training; veralteter Puls wird nicht weiter als aktuelle Messung verwendet.
- 8-/16-Bit-Puls, optionale Energiedaten/RR-Intervalle und Kontaktverlust werden berücksichtigt.

Automatisierte Prüfungen verwenden simulierte BLE-Geräte und Protokollpakete.
Für verbindliche Modellzusagen fehlen weiterhin Tests an realen Geräten verschiedener Hersteller.


## Flutter-Anwendung: tatsächlich beobachtete Hardware

In `flutter_app/` wurden mit dem realen universal_ble-Pfad KICKR CORE FTMS-
Befehlsannahme (Request Control, Zielwatt, Start/Stop), gleichzeitiger Garmin-Fenix-
Herzfrequenzempfang und HR-Reconnect beobachtet. Dies bestätigt die Kommunikation;
physischer Widerstand beim Treten bleibt ausdrücklich ungetestet und aufgeschoben.
HR-Diagnostik protokolliert den ersten sowie jeden 25. Wert je Verbindung.
Andere Modelle/Firmwarestände bleiben gesondert zu validieren. Diese Beobachtungen
ersetzen keine allgemeine Herstellerfreigabe.


Die Flutter-Trainingsausführung nutzt jetzt dieselben realen FTMS-/HR-Controller
für synchronisierte Workouts. Zielwatt sind auf gemeldeten Leistungsbereich und
Schritte begrenzt; nur bestätigte Befehle gelten als erfolgreich. Verbindungsverlust,
veraltete Leistung und Hintergrundbetrieb erzwingen Pause mit ausdrücklichem
Fortsetzen. HR-Verlust wird als fehlender Puls angezeigt und stoppt das Training nicht.
Journal/Outbox und Wiederherstellung sind automatisiert getestet. Diese Softwaretests
sind keine neue Hardwarevalidierung: das tatsächliche Widerstandsverhalten beim
Treten sowie native Journal-/Lifecycle-/Secure-Storage-Integration auf Windows
bleiben gesondert zu prüfen. In diesem Arbeitsschritt wurden keine Builds ausgeführt.
