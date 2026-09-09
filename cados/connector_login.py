"""Account setup for the connector, independent of the former desktop UI."""
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton

from cados.services.workout_library import WorkoutLibraryClient


class ConnectorLogin(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("CADOS Connector · Anmelden")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)
        hint = QLabel("Melde dich mit demselben Konto wie auf der CADOS-Webseite an.")
        hint.setWordWrap(True)
        layout.addRow(hint)
        self.url = QLineEdit(config.workout_library_url or "https://cados.saibot.at")
        self.email = QLineEdit((config.current_account or {}).get("email", ""))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Server", self.url)
        layout.addRow("E-Mail", self.email)
        layout.addRow("Passwort", self.password)
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addRow(self.message)
        self.submit = QPushButton("Anmelden")
        layout.addRow(self.submit)
        self.submit.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.finish_login)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.finished.connect(lambda _: self.executor.shutdown(wait=False))

    def login(self):
        if self.future is not None:
            return
        if not self.email.text().strip() or not self.password.text():
            self.message.setText("Bitte E-Mail und Passwort eingeben.")
            return
        self.client = WorkoutLibraryClient(self.url.text().strip(), "")
        self.login_email = self.email.text().strip()
        self.future = self.executor.submit(self.client.login, self.login_email, self.password.text())
        self.submit.setEnabled(False)
        self.message.setText("Anmeldung läuft …")
        self.timer.start(100)

    def finish_login(self):
        if not self.future.done():
            return
        self.timer.stop()
        try:
            user = self.future.result()
            account = self.config.remember_account(self.client.base_url, self.login_email,
                                                   token=self.client.token, user_id=user["id"])
            self.config.select_account(account)
        except Exception as exc:
            self.message.setText(str(exc))
            self.future = None
            self.submit.setEnabled(True)
            return
        self.password.clear()
        self.accept()

    def reject(self):
        self.timer.stop()
        super().reject()
