"""Reconcile local records against acknowledged server revisions, retaining conflicts."""
import json
from pathlib import Path
from uuid import uuid4

from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord
from cados.services.storage import encode, workout_hash


class AccountSync:
    def __init__(self, store, client, config):
        self.store, self.client, self.config = store, client, config
        with store.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS account_binding (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sync_state (id TEXT PRIMARY KEY, record TEXT NOT NULL, local_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sync_conflicts (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS hidden_workouts (source_name TEXT PRIMARY KEY);
            ''')

    def bind(self, user):
        identity = self.client.base_url + ":" + user["id"]
        with self.store.connection() as db:
            row = db.execute("SELECT identity FROM account_binding WHERE id=1").fetchone()
            if row and row[0] != identity:
                raise ValueError("Diese lokale Datenbank gehört zu einem anderen Konto. Bitte das bisherige Konto verwenden oder CADOS mit einem separaten CADOS_DATA_DIR starten.")
            db.execute("INSERT OR IGNORE INTO account_binding VALUES (1, ?)", (identity,))

    def local_records(self):
        result = {}
        for kind, items in (("profile", self.store.list_profiles()), ("session", self.store.list_sessions())):
            for item in items:
                result[item.id] = {"id": item.id, "kind": kind, "payload": item.to_dict()}
        for item in self.store.list_workouts():
            result[item["id"]] = {"id": item["id"], "kind": "workout", "payload": {**item["payload"], "source_name": item["source_name"]}}
        return result

    def run(self):
        user = self.client._request("/api/v1/auth/me")
        self.bind(user)
        initial = self.local_records()
        remote = {r["id"]: r for r in self.client._request("/api/v1/sync")["records"]}
        with self.store.connection() as db:
            states = {r["id"]: (json.loads(r["record"]), r["local_hash"]) for r in db.execute("SELECT * FROM sync_state")}
        conflicts = 0
        for identifier, local in initial.items():
            prior, prior_hash = states.get(identifier, ({"revision": 0, "shared": False}, ""))
            digest = workout_hash(local["payload"])
            current = remote.get(identifier)
            changed = digest != prior_hash
            if not changed:
                continue
            if current and not current["deleted"] and current["payload"] == local["payload"]:
                continue  # A previous upload succeeded but its response was lost.
            if current and (current["revision"] != prior["revision"] or current["shared"] and not user["admin"]):
                with self.store.connection() as db:
                    db.execute("INSERT OR REPLACE INTO sync_conflicts VALUES (?, ?)", (identifier, encode(local)))
                conflicts += 1
                continue
            change = {**local, "revision": prior["revision"], "shared": prior.get("shared", False), "deleted": False}
            saved = self.client._request("/api/v1/sync", method="POST", payload={"changes": [change]})["records"][0]
            remote[identifier] = saved

        # Protect edits made on the UI thread while a network request was in flight.
        now = self.local_records()
        for identifier, record in remote.items():
            if identifier in now and now.get(identifier) != initial.get(identifier):
                continue
            prior, prior_hash = states.get(identifier, (None, ""))
            current_hash = workout_hash(now[identifier]["payload"]) if identifier in now else ""
            if prior == record and current_hash == prior_hash:
                continue
            self.apply(record)
        return len(remote), conflicts

    def apply(self, record):
        identifier, kind, payload = record["id"], record["kind"], record["payload"]
        deleted = record["deleted"]
        local_payload = None
        if kind == "profile":
            if deleted:
                with self.store.connection() as db:
                    db.execute("DELETE FROM profiles WHERE id=?", (identifier,))
            else:
                profile = UserProfile.from_dict({**payload, "id": identifier})
                self.store.save_profile(profile)
                local_payload = profile.to_dict()
        elif kind == "session":
            if deleted:
                with self.store.connection() as db:
                    db.execute("DELETE FROM sessions WHERE id=?", (identifier,))
            else:
                session = WorkoutSessionRecord.from_dict({**payload, "id": identifier})
                self.store.save_session(session)
                local_payload = session.to_dict()
        elif kind == "workout":
            source = Path(payload.get("source_name", identifier + ".json")).name
            with self.store.connection() as db:
                if deleted:
                    db.execute("DELETE FROM workouts WHERE id=?", (identifier,))
                    db.execute("INSERT OR IGNORE INTO hidden_workouts VALUES (?)", (source,))
                else:
                    db.execute("DELETE FROM hidden_workouts WHERE source_name=?", (source,))
            if not deleted:
                clean = {k: v for k, v in payload.items() if k != "source_name"}
                # Server identity is authoritative; preserve same-name local imports separately.
                with self.store.connection() as db:
                    existing = db.execute("SELECT id FROM workouts WHERE source_name=?", (source,)).fetchone()
                    if existing and existing[0] != identifier:
                        source = identifier + ".json"
                    db.execute('''INSERT INTO workouts(id, source_name, name, payload, content_hash, origin, revision)
                        VALUES (?, ?, ?, ?, ?, 'server', ?) ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name, payload=excluded.payload, content_hash=excluded.content_hash,
                        revision=excluded.revision''',
                        (identifier, source, clean["name"], encode(clean), workout_hash({"id": identifier, "payload": clean}), record["revision"]))
                local_payload = {**clean, "source_name": source}
        elif kind == "settings" and not deleted:
            self.config.save_settings(payload)
            # Applied to Qt timers on the UI thread after synchronization.
        # Store the local normalized representation so defaults do not cause perpetual uploads.
        digest = workout_hash(local_payload) if local_payload is not None else ""
        with self.store.connection() as db:
            db.execute("INSERT OR REPLACE INTO sync_state VALUES (?, ?, ?)", (identifier, encode(record), digest))
