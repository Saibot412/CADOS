# CADOS Web und Synchronisation

Weboberfläche und API laufen gemeinsam in einem Container. Die vorhandene PostgreSQL-
Instanz bleibt bestehen. Es werden nur neue Tabellen mit dem Präfix `cados_` angelegt;
die bisherige Workout-Tabelle und fremde Tabellen werden nicht verändert.

## Installation auf dem Server

Voraussetzung: Docker mit Compose sowie ein HTTPS-Reverse-Proxy auf diesem Server.
Im CADOS-Projektordner:

```sh
cp server/.env.example server/.env
chmod 600 server/.env
```

In `server/.env` einmalig konfigurieren:

* `DATABASE_URL`: vorhandene PostgreSQL-Verbindung, aus dem Container erreichbar.
  Beispiel: `postgresql+psycopg://cados:URL_ENCODED_PASSWORD@DB_HOST:5432/cados`.
  `localhost` bezeichnet im Container den Container selbst. Sonderzeichen in Benutzer
  und Passwort müssen URL-kodiert sein. Bei einer entfernten Datenbank SSL nach Vorgabe
  des Datenbankbetreibers konfigurieren, z. B. `?sslmode=verify-full` mit passendem CA-Zertifikat.
* `CADOS_PUBLIC_URL=https://www.cados.saibot.at`
* `CADOS_ADMIN_EMAIL`: dein erstes Benutzerkonto.
* `CADOS_ADMIN_PASSWORD`: einzigartiges Passwort mit mindestens 12 Zeichen.

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail=80 cados
curl --fail http://127.0.0.1:8000/health
```

Der Erststart legt das Administratorkonto und die 26 mitgelieferten Workouts an.
Danach `CADOS_ADMIN_PASSWORD` aus `.env` entfernen und den Container mit
`docker compose up -d --force-recreate` neu erstellen. Bestehende Passwörter werden
bei einem Neustart nicht überschrieben.

## Domain und HTTPS

Wenn Nginx Proxy Manager auf demselben Docker-Server läuft:

```sh
python3 scripts/connect_proxy.py
```

Der Helfer erkennt den Proxy-Container und dessen vorhandenes Docker-Netz, prüft
die Compose-Konfiguration und verbindet CADOS über eine lokale, Git-ignorierte
`compose.override.yaml` dauerhaft damit. Die eigene CADOS-Netzverbindung bleibt
erhalten. Eigene Override-Dateien werden nicht überschrieben. Bei mehreren Proxys
oder Netzen sind `--container NAME` und `--network NAME` möglich.
In NPM als Ziel **http**, **cados-web**, **8000** eintragen. Keine Container-IP verwenden.
Danach für `www.cados.saibot.at` ein Zertifikat anfordern und Force SSL aktivieren.
Port 8000 bleibt auf dem Host nur an Loopback gebunden.

Die Verbindung verwendet ein [externes Compose-Netz](https://docs.docker.com/compose/how-tos/networking/).

In World4You muss **www.cados.saibot.at** auf die öffentliche Serveradresse zeigen.
Der HTTPS-Reverse-Proxy leitet diese Domain auf `127.0.0.1:8000` weiter. Eine Vorlage
für einen auf dem Host laufenden Caddy liegt in `server/Caddyfile.example`.
DNS allein richtet weder Docker noch das TLS-Zertifikat ein.
Bei einem Reverse-Proxy in Docker stattdessen ein gemeinsames privates Docker-Netz
verwenden und auf `cados:8000` zeigen; Port 8000 nicht öffentlich freigeben.

## Benutzung

Benutzer registrieren sich im Browser und verwalten dort ihr Profil, Workouts und Kalender.
JSON/ZWO-Import und der Workout-Builder unterstützen konstante Blöcke und Rampen.
Administratoren verwalten Benutzer und veröffentlichen gemeinsame Workouts.

Den Connector von der Webseite herunterladen und mit demselben Konto anmelden.
Er übernimmt Bluetooth und Training; die gesamte Workout-Verwaltung erfolgt im Browser.
Gespeicherte Anmeldungen werden wiederverwendet. **Anmeldung ändern …** im Connector-Menü
ermöglicht eine erneute Anmeldung. Weitere Konten erhalten getrennte lokale Datenbanken.

## Synchronisationsregeln

* Der Connector synchronisiert beim Start und nach abgeschlossenen Trainings.
  Fehlgeschlagene Übertragungen werden wiederholt.
* Web-Einstellungen werden lokal übernommen. Trainings werden lokal gespeichert
  und zum Server übertragen. Bluetooth-Kennungen bleiben lokal.
* Änderungen tragen Revisionen; veraltete Schreibversuche ergeben HTTP 409.
* Bei Konflikten bleibt die lokale Fassung in `sync_conflicts` gesichert,
  während die Serverfassung übernommen wird.
* Löschmarkierungen erreichen auch Geräte, die zwischenzeitlich offline waren.
* Ein bereits gestartetes Training läuft bei Internetausfall weiter.
  Lokale Tasten im Connector ermöglichen Pause, Fortsetzen und Beenden.
* Laufende Trainings sind nicht fortlaufend auf dem Server gesichert.
  Ein erzwungenes Prozessende kann die laufende Session verlieren.
* Der Abgleich lädt derzeit den vollständigen Kontostand; Antworten sind auf 100 MB begrenzt.

## Betrieb und Wiederherstellung

Passwörter liegen als gesalzene scrypt-Hashes vor. Anmeldetokens sind zufällig, gelten
30 Tage und werden auf dem Server nur gehasht gespeichert. Browser verwenden HttpOnly-
Cookies, SameSite und CSRF-Prüfung. Passwortänderung widerruft alle Anmeldungen des Kontos.
Der Connector speichert sein Token in den lokalen Benutzereinstellungen (unter macOS mit
Dateimodus 0600); das Passwort wird nicht gespeichert.
Abmelden entfernt die Anmeldung; bereits heruntergeladene Daten bleiben lokal verfügbar.

Die Anmelderate wird pro Prozess begrenzt. Deshalb zunächst genau einen API-Worker
betreiben; für mehrere Instanzen ist ein gemeinsamer Rate-Limiter erforderlich.
Da der Container Proxy-Header nicht vertraut, teilen Zugriffe hinter einem Reverse-Proxy
derzeit das IP-Limit (20 Versuche in 15 Minuten); zusätzlich besteht ein E-Mail-Limit.

Regelmäßige PostgreSQL-Backups mit `pg_dump` und Wiederherstellung mit `pg_restore`
über die vorhandene Serveradministration einrichten. Vor jedem Update ein Backup anlegen.
Lokale SQLite-Sicherungen sind über **Konto → Lokale Daten sichern** möglich.
Ein Backup einer laufenden SQLite-Datenbank erfolgt über die Backup-API, nicht durch
einfaches Kopieren der Hauptdatei ohne WAL.

Schemaänderungen stehen in `server/app/database.py`. Version 1 ist additiv und durch
eine PostgreSQL-Transaktionssperre gegen parallele Migrationen geschützt. Künftige
Änderungen müssen als neue versionierte Migrationen ergänzt werden.

## Tests

```sh
python -m pip install -e . -r server/requirements.txt httpx
python -m unittest discover -s tests -v
```

API-Integrationstests verwenden temporäres SQLite mit derselben SQLAlchemy-Schemadefinition.
Tests werden lokal ausgeführt. Automatische GitHub-Actions-Workflows sind nicht eingerichtet.
Containerstart und Reverse-Proxy müssen zusätzlich auf dem Zielserver geprüft werden.
Der optional ausführbare Browser-Test verwendet ausschließlich Testdaten:

```sh
python -m pip install playwright
python -m playwright install chromium
python scripts/smoke_web.py
```
