from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from cados.core.workout_loader import WorkoutLoader
from cados.core.zwo_importer import parse_zwo
from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord
from server.app.database import migrate, records, tokens, users
from server.app.security import hash_password, token_hash, verify_password
from server.app.validation import validate_workout_payload

class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)

class Registration(Credentials):
    password_confirmation: str = Field(max_length=256)
    name: str = Field(min_length=1, max_length=200)
    ftp: int = Field(ge=30, le=2000)
    weight_kg: float = Field(ge=10, le=500)

class UserStatus(BaseModel):
    active: bool

class Change(BaseModel):
    id: str
    kind: str
    revision: int = Field(ge=0)
    deleted: bool = False
    shared: bool = False
    payload: dict

class Changes(BaseModel):
    changes: list[Change] = Field(max_length=100)

def create_app(database_url=None, public_url=None, *, bootstrap=None):
    database_url = database_url or os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not database_url:
        raise RuntimeError("DATABASE_URL fehlt")
    public_url = (public_url or os.environ.get("CADOS_PUBLIC_URL", "https://www.cados.saibot.at")).rstrip("/")
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    attempts = defaultdict(deque)
    attempt_lock = threading.Lock()
    dummy_password = hash_password(secrets.token_urlsafe(32))

    @asynccontextmanager
    async def lifespan(app):
        migrate(engine)
        initial = bootstrap or (os.getenv("CADOS_ADMIN_EMAIL"), os.getenv("CADOS_ADMIN_PASSWORD"))
        with engine.begin() as connection:
            if not connection.execute(sa.select(users.c.id).limit(1)).first():
                if not all(initial):
                    raise RuntimeError("Erster Start benötigt CADOS_ADMIN_EMAIL und CADOS_ADMIN_PASSWORD")
                connection.execute(users.insert().values(id=str(uuid4()), email=initial[0].strip().casefold(),
                    password=hash_password(initial[1]), admin=True))
            for path in (Path(__file__).parents[2] / "cados/assets/workouts").glob("*.json"):
                identifier = str(uuid5(NAMESPACE_URL, "cados:bundled:" + path.name))
                if not connection.execute(sa.select(records.c.id).where(records.c.id == identifier)).first():
                    payload = WorkoutLoader(path.parent).load_path(path).to_dict()
                    payload["source_name"] = path.name
                    connection.execute(records.insert().values(id=identifier, owner=None, kind="workout",
                        revision=1, deleted=False, payload=payload))
        yield
        engine.dispose()

    app = FastAPI(title="CADOS", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.engine = engine

    @app.middleware("http")
    async def protect(request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != public_url:
                return JSONResponse({"detail": "Ungültiger Ursprung"}, status_code=403)
            if request.cookies.get("cados_session") and request.headers.get("x-cados-request") != "1":
                return JSONResponse({"detail": "CSRF-Prüfung fehlgeschlagen"}, status_code=403)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 20_000_000:
                    return JSONResponse({"detail": "Anfrage größer als 20 MB"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    def current_user(request: Request):
        header = request.headers.get("authorization", "")
        token = header[7:] if header.startswith("Bearer ") else request.cookies.get("cados_session", "")
        with engine.connect() as connection:
            row = connection.execute(sa.select(users).join(tokens, tokens.c.user_id == users.c.id).where(
                tokens.c.hash == token_hash(token), tokens.c.expires > time.time(), users.c.active.is_(True))).mappings().first()
        if row is None:
            raise HTTPException(401, "Bitte anmelden.")
        return dict(row)

    def public_user(user):
        return {key: user[key] for key in ("id", "email", "admin", "active")}

    def create_user(credentials: Credentials, profile=None):
        email = credentials.email.strip().casefold()
        if "@" not in email:
            raise HTTPException(422, "Ungültige E-Mail-Adresse")
        try:
            encoded = hash_password(credentials.password)
            user_id = str(uuid4())
            with engine.begin() as connection:
                connection.execute(users.insert().values(
                    id=user_id, email=email, password=encoded, admin=False))
                if profile is not None:
                    connection.execute(records.insert().values(id=profile["id"], owner=user_id, kind="profile",
                        revision=1, deleted=False, payload=profile))
            return user_id
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except IntegrityError as exc:
            raise HTTPException(409, "Für diese E-Mail-Adresse gibt es bereits ein Konto.") from exc

    @app.post("/api/v1/auth/register")
    def register(registration: Registration):
        if registration.password != registration.password_confirmation:
            raise HTTPException(422, "Die Passwörter stimmen nicht überein.")
        profile = UserProfile(id=str(uuid4()), name=registration.name.strip(), ftp=registration.ftp,
                              weight_kg=registration.weight_kg).to_dict()
        if not profile["name"]:
            raise HTTPException(422, "Der Benutzername darf nicht leer sein.")
        create_user(registration, profile)
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    def login(credentials: Credentials, request: Request, response: Response):
        email = credentials.email.strip().casefold()
        key = request.client.host if request.client else "unknown"
        now = time.time()
        with attempt_lock:
            for expired in [k for k, values in attempts.items() if not values or values[-1] < now - 900]:
                del attempts[expired]
            for bucket in ("ip:" + key, "email:" + email):
                while attempts[bucket] and attempts[bucket][0] < now - 900:
                    attempts[bucket].popleft()
                if len(attempts[bucket]) >= 20:
                    raise HTTPException(429, "Zu viele Anmeldeversuche. Bitte später erneut versuchen.")
                attempts[bucket].append(now)
        with engine.begin() as connection:
            user = connection.execute(sa.select(users).where(users.c.email == email)).mappings().first()
            valid = verify_password(credentials.password, user["password"] if user else dummy_password)
            if not user or not user["active"] or not valid:
                raise HTTPException(401, "E-Mail oder Passwort stimmt nicht.")
            token = secrets.token_urlsafe(48)
            connection.execute(tokens.delete().where(tokens.c.expires <= now))
            connection.execute(tokens.insert().values(hash=token_hash(token), user_id=user["id"], expires=now+30*86400))
        response.set_cookie("cados_session", token, httponly=True, secure=public_url.startswith("https:"),
            samesite="strict", max_age=30*86400)
        return {"token": token, "user": public_user(user)}

    @app.get("/api/v1/auth/me")
    def me(user=Depends(current_user)):
        return public_user(user)

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response, user=Depends(current_user)):
        header = request.headers.get("authorization", "")
        token = header[7:] if header.startswith("Bearer ") else request.cookies.get("cados_session", "")
        with engine.begin() as connection:
            connection.execute(tokens.delete().where(tokens.c.hash == token_hash(token)))
        response.delete_cookie("cados_session")
        return {"ok": True}

    @app.post("/api/v1/auth/password")
    def password(credentials: Credentials, user=Depends(current_user)):
        try:
            encoded = hash_password(credentials.password)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with engine.begin() as connection:
            connection.execute(users.update().where(users.c.id == user["id"]).values(password=encoded))
            connection.execute(tokens.delete().where(tokens.c.user_id == user["id"]))
        return {"ok": True}

    @app.post("/api/v1/users")
    def add_user(credentials: Credentials, user=Depends(current_user)):
        if not user["admin"]:
            raise HTTPException(403, "Nur Administratoren dürfen Benutzer anlegen.")
        create_user(credentials)
        return {"ok": True}

    def require_admin(user):
        if not user["admin"]:
            raise HTTPException(403, "Nur Administratoren dürfen Benutzer verwalten.")

    @app.get("/api/v1/users")
    def list_users(user=Depends(current_user)):
        require_admin(user)
        with engine.connect() as connection:
            rows = connection.execute(sa.select(users.c.id, users.c.email, users.c.admin, users.c.active)
                                      .order_by(users.c.email)).mappings().all()
        return {"users": [dict(row) for row in rows]}

    @app.patch("/api/v1/users/{user_id}")
    def set_user_status(user_id: str, status: UserStatus, user=Depends(current_user)):
        require_admin(user)
        if user_id == user["id"]:
            raise HTTPException(422, "Das eigene Administratorkonto kann hier nicht deaktiviert werden.")
        with engine.begin() as connection:
            target = connection.execute(sa.select(users.c.id).where(users.c.id == user_id)).first()
            if target is None:
                raise HTTPException(404, "Benutzer nicht gefunden.")
            connection.execute(users.update().where(users.c.id == user_id).values(active=status.active))
            if not status.active:
                connection.execute(tokens.delete().where(tokens.c.user_id == user_id))
        return {"ok": True}

    @app.delete("/api/v1/users/{user_id}")
    def delete_user(user_id: str, user=Depends(current_user)):
        require_admin(user)
        if user_id == user["id"]:
            raise HTTPException(422, "Das eigene Administratorkonto kann hier nicht gelöscht werden.")
        with engine.begin() as connection:
            target = connection.execute(sa.select(users.c.id).where(users.c.id == user_id)).first()
            if target is None:
                raise HTTPException(404, "Benutzer nicht gefunden.")
            connection.execute(records.delete().where(records.c.owner == user_id))
            connection.execute(tokens.delete().where(tokens.c.user_id == user_id))
            connection.execute(users.delete().where(users.c.id == user_id))
        return {"ok": True}

    def visible(user):
        return sa.or_(records.c.owner == user["id"], sa.and_(records.c.owner.is_(None), records.c.kind == "workout"))

    def serialize(row):
        return {"id": row["id"], "kind": row["kind"], "revision": row["revision"],
                "deleted": row["deleted"], "shared": row["owner"] is None, "payload": row["payload"]}

    @app.get("/api/v1/sync")
    def snapshot(user=Depends(current_user)):
        with engine.connect() as connection:
            rows = connection.execute(sa.select(records).where(visible(user))).mappings().all()
        return {"records": [serialize(row) for row in rows]}

    @app.post("/api/v1/sync")
    def sync(batch: Changes, user=Depends(current_user)):
        result = []
        try:
            with engine.begin() as connection:
                for change in batch.changes:
                    try:
                        UUID(change.id)
                        if change.kind in {"profile", "session"}:
                            change.payload["id"] = change.id
                        payload = validate_record(change.kind, change.payload, change.deleted)
                    except (ValueError, TypeError, KeyError) as exc:
                        raise HTTPException(422, str(exc)) from exc
                    if change.shared and (change.kind != "workout" or not user["admin"]):
                        raise HTTPException(403, "Nur Administratoren verwalten gemeinsame Workouts.")
                    row = connection.execute(sa.select(records).where(records.c.id == change.id).with_for_update()).mappings().first()
                    owner = None if change.shared else user["id"]
                    if row:
                        if row["owner"] != user["id"] and not (row["owner"] is None and user["admin"]):
                            raise HTTPException(403, "Kein Schreibzugriff.")
                        if row["kind"] != change.kind:
                            raise HTTPException(422, "Datensatztyp darf nicht geändert werden.")
                        if row["revision"] != change.revision:
                            raise HTTPException(409, {"message": "Daten wurden inzwischen geändert. Neu laden und Änderungen prüfen.", "record": serialize(row)})
                        if row["owner"] != owner:
                            raise HTTPException(422, "Zum Ändern der Freigabe bitte eine Kopie anlegen.")
                        connection.execute(records.update().where(records.c.id == change.id).values(
                            revision=row["revision"]+1, payload=payload, deleted=change.deleted))
                    else:
                        if change.revision != 0:
                            raise HTTPException(409, "Datensatz fehlt. Bitte synchronisieren.")
                        connection.execute(records.insert().values(id=change.id, kind=change.kind, owner=owner,
                            revision=1, payload=payload, deleted=change.deleted))
                    saved = connection.execute(sa.select(records).where(records.c.id == change.id)).mappings().one()
                    result.append(serialize(saved))
        except IntegrityError as exc:
            raise HTTPException(409, "Gleichzeitige Änderung. Bitte erneut synchronisieren.") from exc
        return {"records": result}

    @app.post("/api/v1/import")
    async def import_workout(request: Request, filename: str, shared: bool = False, user=Depends(current_user)):
        suffix = Path(filename).suffix.lower()
        raw = await request.body()
        if len(raw) > 2_000_000 or suffix not in {".json", ".zwo"}:
            raise HTTPException(422, "JSON oder ZWO bis 2 MB auswählen.")
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / ("import" + suffix)
                path.write_bytes(raw)
                loader = WorkoutLoader(Path(directory))
                workout = parse_zwo(path, loader) if suffix == ".zwo" else loader.load_path(path)
                payload = workout.to_dict()
                payload["source_name"] = Path(filename.replace("\\", "/")).stem + ".json"
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return sync(Changes(changes=[Change(id=str(uuid4()), kind="workout", revision=0, shared=shared, payload=payload)]), user)

    @app.get("/health")
    def health():
        with engine.connect() as connection:
            connection.execute(sa.text("SELECT 1"))
        return {"status": "ok"}

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")
    return app

def validate_record(kind, payload, deleted=False):
    if kind not in {"workout", "profile", "session", "settings"}:
        raise ValueError("Unbekannter Datensatztyp")
    json.dumps(payload, allow_nan=False)
    if deleted:
        return payload
    if kind == "workout":
        validate_workout_payload(payload)
        WorkoutLoader(Path(".")).load_payload(payload, Path("workout.json"))
    elif kind == "profile":
        profile = UserProfile.from_dict(payload)
        if not 30 <= profile.ftp <= 2000 or len(profile.name) > 200:
            raise ValueError("Ungültiges Profil oder FTP")
        if profile.weight_kg is not None and not 10 <= profile.weight_kg <= 500:
            raise ValueError("Ungültiges Gewicht")
        if profile.max_hr is not None and not 50 <= profile.max_hr <= 250:
            raise ValueError("Ungültige maximale Herzfrequenz")
    elif kind == "session":
        session = WorkoutSessionRecord.from_dict(payload)
        if not 0 <= session.duration_sec <= 86400 or len(session.samples) > 400000:
            raise ValueError("Ungültige Trainingsdauer oder Messwertanzahl")
    elif kind == "settings":
        if set(payload) - {"default_ftp", "tick_interval_ms"}:
            raise ValueError("Diese Einstellungen sind gerätespezifisch.")
        for key, low, high in (("default_ftp", 100, 2000), ("tick_interval_ms", 100, 1000)):
            if key in payload and (type(payload[key]) is not int or not low <= payload[key] <= high):
                raise ValueError("Ungültige Einstellung")
    return payload
