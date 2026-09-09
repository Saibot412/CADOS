"""Upgrade only unchanged shipped FTP-test blocks; preserve customizations and deletions."""
import hashlib
import json

LEGACY_FTP_BLOCKS_HASH = "d30d66ea6d1e367056a7e4b721a476f09ff424fd7cf3bb2750c56276449ac59c"


def update_ftp_blocks(payload, replacement):
    digest = hashlib.sha256(json.dumps(payload.get("blocks", []), sort_keys=True).encode()).hexdigest()
    if digest != LEGACY_FTP_BLOCKS_HASH:
        return None
    return {**payload, "blocks": replacement["blocks"], "description": replacement["description"] if payload.get("description") == "FTP-Rampentest für Indoor-Standards mit klarer Kadenzvorgabe." else payload.get("description", "")}
