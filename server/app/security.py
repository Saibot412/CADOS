import hashlib
import secrets

def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 256:
        raise ValueError("Das Passwort benötigt 12 bis 256 Zeichen.")
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return salt + ":" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    if len(password) > 256:
        return False
    salt, digest = stored.split(":")
    candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return secrets.compare_digest(candidate.hex(), digest)

def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
