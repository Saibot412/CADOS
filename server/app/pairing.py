"""Short-lived, single-use browser approval for connector sign-in."""
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from server.app.database import pairings, tokens, users
from server.app.security import token_hash


class PairCode(BaseModel):
    code: str = Field(min_length=8, max_length=128)


class PairSecret(BaseModel):
    secret: str = Field(min_length=32, max_length=128)


def install_pairing(app, engine, current_user, public_user, public_url):
    attempts, lock = defaultdict(deque), Lock()

    @app.post('/api/v1/connector/pair/begin')
    def begin(request: Request):
        now = time.time()
        ip = request.client.host if request.client else 'unknown'
        with lock:
            for key in list(attempts):
                if not attempts[key] or attempts[key][-1] < now - 600:
                    del attempts[key]
            bucket = attempts[ip]
            while bucket and bucket[0] < now - 600:
                bucket.popleft()
            if len(bucket) >= 20:
                raise HTTPException(429, 'Bitte später erneut koppeln.')
            bucket.append(now)
        code, secret = secrets.token_urlsafe(18), secrets.token_urlsafe(48)
        with engine.begin() as db:
            db.execute(pairings.delete().where(pairings.c.expires <= now))
            db.execute(pairings.insert().values(code_hash=token_hash(code), secret_hash=token_hash(secret), expires=now + 300))
        return {'code': code, 'secret': secret, 'expires_in': 300,
                'url': public_url + '/?pair=' + code}

    @app.post('/api/v1/connector/pair/approve')
    def approve(body: PairCode, user=Depends(current_user)):
        with engine.begin() as db:
            changed = db.execute(pairings.update().where(pairings.c.code_hash == token_hash(body.code),
                pairings.c.expires > time.time(), pairings.c.user_id.is_(None)).values(user_id=user['id']))
            if changed.rowcount != 1:
                raise HTTPException(409, 'Kopplung abgelaufen oder bereits bestätigt. Bitte im Connector neu starten.')
        return {'ok': True}

    @app.post('/api/v1/connector/pair/poll')
    def poll(body: PairSecret):
        now = time.time()
        with engine.begin() as db:
            row = db.execute(sa.select(pairings).where(pairings.c.secret_hash == token_hash(body.secret),
                pairings.c.expires > now)).mappings().first()
            if row is None:
                raise HTTPException(410, 'Kopplung abgelaufen. Bitte erneut starten.')
            if not row['user_id']:
                return {'pending': True}
            user = db.execute(sa.select(users).where(users.c.id == row['user_id'], users.c.active.is_(True))).mappings().first()
            consumed = db.execute(pairings.delete().where(pairings.c.secret_hash == token_hash(body.secret)))
            if not user or consumed.rowcount != 1:
                raise HTTPException(410, 'Kopplung nicht mehr verfügbar.')
            token = secrets.token_urlsafe(48)
            db.execute(tokens.insert().values(hash=token_hash(token), user_id=user['id'], expires=now + 30 * 86400))
        return {'token': token, 'user': public_user(user)}
