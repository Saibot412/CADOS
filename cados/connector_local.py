"""Loopback-only browser transport, authenticated per connector process."""
import asyncio
import json
import secrets
from pathlib import Path
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

PORT = 48732


class LocalTransport:
    def __init__(self, service):
        self.service = service
        self.token = secrets.token_urlsafe(48)
        self.clients = set()
        self.ready = False
        self.origin = service.config.workout_library_url.rstrip('/')

    @property
    def access(self):
        return {'token': self.token, 'port': PORT} if self.ready else None

    @property
    def page_url(self):
        return f'http://127.0.0.1:{PORT}/#{self.token}'

    async def request(self, connection, request):
        if request.headers.get('Host') != f'127.0.0.1:{PORT}':
            return connection.respond(403, 'Ungültiger Host')
        if request.headers.get('Upgrade', '').lower() == 'websocket':
            if request.headers.get('Origin') not in {self.origin, f'http://127.0.0.1:{PORT}'} or request.path != '/live':
                return connection.respond(403, 'Ungültiger Ursprung')
            return None
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/local.js': ('local.js', 'text/javascript'),
                 '/local.css': ('local.css', 'text/css')}
        if request.path not in files:
            return connection.respond(404, 'Nicht gefunden')
        name, mime = files[request.path]
        body = (Path(__file__).parent / 'assets/local' / name).read_text()
        response = connection.respond(200, body)
        response.headers['Content-Type'] = mime
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; connect-src ws://127.0.0.1:48732; frame-ancestors 'none'; base-uri 'none'"
        return response

    async def handle(self, socket):
        try:
            first = json.loads(await asyncio.wait_for(socket.recv(), 5))
            if not isinstance(first, dict) or not secrets.compare_digest(str(first.get('token', '')), self.token):
                await socket.close(1008, 'Kopplung erforderlich')
                return
            self.clients.add(socket)
            async def send(message):
                await socket.send(json.dumps(message))
            await send({'type': 'status', 'version': __import__('cados').__version__})
            await send(self.service._recovery())
            async def publish():
                while True:
                    await send(self.service._telemetry())
                    await asyncio.sleep(.5)
            publisher = asyncio.create_task(publish())
            try:
                async for raw in socket:
                    message = json.loads(raw)
                    command = message.get('command') if isinstance(message, dict) else None
                    if not isinstance(command, dict) or command.get('name') not in {'snapshot', 'pause', 'resume', 'stop', 'erg_mode', 'connect', 'restore', 'save_recovered', 'scan_devices', 'select_device', 'disconnect_device'}:
                        await send({'type': 'error', 'message': 'Dieser Befehl benötigt die Serververbindung.'})
                        continue
                    await self.service._handle_command(command, send)
            finally:
                publisher.cancel()
                await asyncio.gather(publisher, return_exceptions=True)
        except ConnectionClosed:
            pass
        except (TimeoutError, ValueError):
            await socket.close(1008, 'Ungültige Anfrage')
        finally:
            self.clients.discard(socket)
            if not self.clients and not self.service._browser_connected:
                self.service._set_browser_connected(False)

    async def run(self):
        try:
            async with serve(self.handle, '127.0.0.1', PORT, process_request=self.request,
                             max_size=65536, ping_interval=10, ping_timeout=10):
                self.ready = True
                while not self.service._stopping:
                    await asyncio.sleep(.5)
        except OSError:
            self.service._report_status(error='Lokale Verbindung belegt. Prüfe, ob bereits ein Connector läuft.')
        finally:
            self.ready = False
