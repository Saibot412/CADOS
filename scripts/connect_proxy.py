"""Attach CADOS persistently to an existing Nginx Proxy Manager Docker network."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "# Managed by CADOS scripts/connect_proxy.py\n"


def docker(*args):
    return subprocess.run(["docker", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def choose_proxy(containers, requested=None):
    matches = [c for c in containers if c["Names"] == requested] if requested else [
        c for c in containers if "nginx-proxy-manager" in c["Image"].lower()]
    if len(matches) != 1:
        raise ValueError("Proxy nicht eindeutig erkannt. Bitte erneut mit --container NAME starten. "
                         "Laufende Container: " + ", ".join(c["Names"] for c in containers))
    return matches[0]["Names"]


def choose_network(networks, requested=None):
    candidates = [n for n in networks if n["Name"] not in {"bridge", "host", "none"}
                  and n.get("Driver") == "bridge" and not n.get("Internal")]
    if requested:
        candidates = [n for n in candidates if n["Name"] == requested]
    if len(candidates) > 1:
        defaults = [n for n in candidates if (n.get("Labels") or {}).get("com.docker.compose.network") == "default"]
        if len(defaults) == 1:
            candidates = defaults
    if len(candidates) != 1:
        raise ValueError("Proxy-Netz nicht eindeutig erkannt. Bitte --network NAME angeben. "
                         "Verfügbare Netze: " + ", ".join(n["Name"] for n in networks))
    return candidates[0]["Name"]


def override(network):
    # JSON is valid YAML; Docker network names are encoded, never interpolated as shell code.
    return MARKER + json.dumps({
        "services": {"cados": {"networks": {"default": {}, "npm": {"aliases": ["cados-web"]}}}},
        "networks": {"default": {}, "npm": {"external": True, "name": network}},
    }, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container")
    parser.add_argument("--network")
    args = parser.parse_args()
    if os.getenv("COMPOSE_FILE"):
        raise ValueError("COMPOSE_FILE ist gesetzt. Bitte ohne diese Variable erneut starten.")
    destination = ROOT / "compose.override.yaml"
    if destination.exists() and not destination.read_text().startswith(MARKER):
        raise ValueError("Eine eigene compose.override.yaml existiert bereits; sie wurde nicht verändert.")
    for name in ("compose.override.yml", "docker-compose.override.yml", "docker-compose.override.yaml"):
        if (ROOT / name).exists():
            raise ValueError(f"Vorhandene {name} zuerst prüfen; keine Änderung vorgenommen.")
    containers = [json.loads(line) for line in docker("ps", "--format", "{{json .}}").splitlines()]
    proxy = choose_proxy(containers, args.container)
    attached = json.loads(docker("inspect", "--format", "{{json .NetworkSettings.Networks}}", proxy))
    networks = json.loads(docker("network", "inspect", *attached)) if attached else []
    network = choose_network(networks, args.network)
    content = override(network)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", dir=ROOT, delete=False) as file:
            temporary = Path(file.name)
            file.write(content)
        docker("compose", "-f", "compose.yaml", "-f", str(temporary), "config", "--quiet")
        temporary.replace(destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f"Proxy: {proxy}\nGemeinsames Netz: {network}", flush=True)
    subprocess.run(["docker", "compose", "up", "-d", "--no-build", "cados"], cwd=ROOT, check=True)
    print("In Nginx Proxy Manager eintragen: Scheme http, Forward Hostname cados-web, Forward Port 8000.")
    print("Die Netzverbindung bleibt bei docker compose up -d --build erhalten.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("Einrichtung fehlgeschlagen:", str(exc))
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr)
        raise SystemExit(1)
