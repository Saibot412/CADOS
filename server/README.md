# CADOS Workout-Bibliothek

Die Server-Anwendung speichert ausschließlich Workout-Vorlagen in PostgreSQL.
Profile, gefahrene Sessions und Messwerte verbleiben in der lokalen SQLite-Datei.

## Betrieb

Benötigt werden eine vorhandene PostgreSQL-Datenbank und ein HTTPS-Reverse-Proxy.
Die Tabelle `cados_workout_library` wird beim Start automatisch angelegt.

```bash
docker build -f server/Dockerfile -t cados-library .
docker run --rm -p 127.0.0.1:8000:8000 \
  --env-file server/.env cados-library
```

Der Reverse-Proxy veröffentlicht Port 8000 anschließend unter einer HTTPS-Adresse.
In CADOS werden diese Adresse und derselbe `CADOS_LIBRARY_TOKEN` über die
Schaltfläche **Server** eingetragen. Verwende ein zufälliges Token mit mindestens
24 Zeichen. Port 8000 und PostgreSQL sollten nicht direkt ins Internet gestellt
werden.

Die API stellt folgende Endpunkte bereit:

- `GET /health` für die Betriebsprüfung
- `GET /api/v1/workouts` für den Katalog
- `POST /api/v1/workouts` zum Anlegen oder Aktualisieren
- `DELETE /api/v1/workouts/{id}` zum Entfernen

Alle Workout-Endpunkte benötigen `Authorization: Bearer <token>`.
