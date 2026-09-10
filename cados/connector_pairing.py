"""Pair in the browser; the connector never needs the account password."""
import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
from cados.services.workout_library import WorkoutLibraryClient


class ConnectorPairing(QDialog):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle('CADOS · Mit Browser koppeln')
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        text = QLabel('Melde dich auf der Webseite an und bestätige dort diesen Connector. Dein Passwort bleibt im Browser.')
        text.setWordWrap(True)
        layout.addWidget(text)
        self.url = QLineEdit(config.workout_library_url or 'https://cados.saibot.at')
        layout.addWidget(self.url)
        self.message = QLabel('Bereit zur Kopplung.')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.button = QPushButton('Im Browser anmelden')
        layout.addWidget(self.button)
        self.button.clicked.connect(self.begin)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.secret = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.finished.connect(self.cleanup)

    def begin(self):
        self.client = WorkoutLibraryClient(self.url.text().strip(), '', timeout=10)
        self.button.setEnabled(False)
        self.url.setEnabled(False)
        self.message.setText('Kopplung wird vorbereitet …')
        self.secret = None
        self.future = self.executor.submit(self.client._request, '/api/v1/connector/pair/begin', method='POST', payload={})
        self.timer.start(250)

    def poll(self):
        if self.future is None:
            if time.monotonic() >= self.next_poll:
                self.future = self.executor.submit(self.client._request, '/api/v1/connector/pair/poll', method='POST', payload={'secret': self.secret})
            return
        if not self.future.done():
            return
        try:
            result = self.future.result()
            if self.secret is None:
                self.secret = result['secret']
                self.message.setText('Bestätige die Kopplung im Browser. Gültig für 5 Minuten.\nKennung: ' + result['code'])
                QDesktopServices.openUrl(QUrl(result['url']))
            elif 'token' in result:
                user = result['user']
                account = self.config.remember_account(self.client.base_url, user['email'], token=result['token'], user_id=user['id'])
                self.config.select_account(account)
                self.accept()
                return
            self.future = None
            self.next_poll = time.monotonic() + 2
        except Exception as exc:
            self.timer.stop()
            self.message.setText(str(exc))
            self.button.setEnabled(True)
            self.url.setEnabled(True)

    def cleanup(self, *_):
        self.timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
