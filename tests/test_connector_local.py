import asyncio
import json
import unittest
from types import SimpleNamespace
from websockets.exceptions import ConnectionClosed
from cados.connector_local import LocalTransport, PORT


class Socket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []
        self.closed = None
    async def recv(self):
        return next(self.messages)
    async def send(self, data):
        self.sent.append(json.loads(data))
    async def close(self, code, reason):
        self.closed = code
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration


class LocalTransportTests(unittest.IsolatedAsyncioTestCase):
    def make_transport(self):
        self.commands = []
        async def handle(command, send):
            self.commands.append(command)
        return LocalTransport(SimpleNamespace(config=SimpleNamespace(workout_library_url='https://cados.saibot.at'),
            _handle_command=handle, _recovery=lambda: {'type':'recovery','payload':{}},
            _telemetry=lambda: {'type':'telemetry','payload':{}}, _browser_connected=True))

    async def test_wrong_token_receives_no_telemetry(self):
        transport = self.make_transport()
        socket = Socket([json.dumps({'token':'wrong'})])
        await transport.handle(socket)
        self.assertEqual(socket.closed, 1008)
        self.assertEqual(socket.sent, [])

    async def test_authenticated_local_pause_and_no_offline_new_start(self):
        transport = self.make_transport()
        socket = Socket([json.dumps({'token':transport.token}), json.dumps({'command':{'name':'pause'}}),
                         json.dumps({'command':{'name':'start'}})])
        await transport.handle(socket)
        self.assertEqual(self.commands, [{'name':'pause'}])
        self.assertEqual(socket.sent[-1]['type'], 'error')
        self.assertFalse(transport.clients)

    async def test_unrelated_site_and_dns_rebinding_host_are_rejected(self):
        transport = self.make_transport()
        connection = SimpleNamespace(respond=lambda status, message: status)
        req = SimpleNamespace(headers={'Host':f'127.0.0.1:{PORT}', 'Upgrade':'websocket', 'Origin':'https://evil.example'},path='/live')
        self.assertEqual(await transport.request(connection,req),403)
        req.headers['Origin']='https://cados.saibot.at'
        req.headers['Host']=f'evil.example:{PORT}'
        self.assertEqual(await transport.request(connection,req),403)
