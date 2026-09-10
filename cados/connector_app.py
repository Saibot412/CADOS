"""Desktop window and menu-bar host for the local CADOS Connector."""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer, QUrl, Signal, QLockFile
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QMenu, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget

from cados.config import AppConfig
from cados.connector import ConnectorService
from cados.connector_pairing import ConnectorPairing
from cados.logging_utils import configure_logging

logger = logging.getLogger(__name__)


class StatusBridge(QObject):
    changed = Signal(dict)


class ConnectorApplication(QApplication):
    open_requested = Signal(str)

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.FileOpen and event.url().scheme() == 'cados-connector':
            self.open_requested.emit(event.url().host())
            return True
        return super().event(event)


class ConnectorWindow(QMainWindow):
    def __init__(self, config: AppConfig, quit_callback) -> None:
        super().__init__()
        self.config, self.quit_callback = config, quit_callback
        self.setWindowTitle("CADOS Connector")
        self.setWindowIcon(QIcon(str(config.paths.app_icon_path)))
        self.setMinimumSize(550, 650)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        title = QLabel("CADOS Connector")
        title.setObjectName("title")
        subtitle = QLabel("Verbindet deinen Mac mit CADOS, Trainer und Herzfrequenzsensor.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.connection = QLabel("Verbindung wird hergestellt …")
        self.connection.setObjectName("connection")
        self.connection.setProperty("online", False)
        self.connection.setWordWrap(True)
        layout.addWidget(self.connection)
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(10)
        self.values: dict[str, QLabel] = {}
        for row, (key, label) in enumerate((
            ("trainer", "Trainer"), ("hr", "Herzfrequenz"), ("workout", "Training"),
            ("state", "Status"), ("power", "Leistung"), ("cadence", "Kadenz"),
            ("browser", "Webseite"),
            ("device_status", "Geräte"),
        )):
            caption = QLabel(label)
            caption.setObjectName("caption")
            value = QLabel("–")
            value.setObjectName("value")
            grid.addWidget(caption, row, 0)
            grid.addWidget(value, row, 1)
            self.values[key] = value
        layout.addWidget(card)
        self.local_command = lambda name: None
        controls = QHBoxLayout()
        self.training_buttons = {}
        for name, label in (("pause", "Pause"), ("resume", "Fortsetzen"), ("stop", "Training beenden")):
            control = QPushButton(label)
            control.setEnabled(False)
            control.clicked.connect(lambda checked=False, command=name: self.local_command(command))
            controls.addWidget(control)
            self.training_buttons[name] = control
        layout.addLayout(controls)
        self.recovery = QLabel()
        self.recovery.setWordWrap(True)
        layout.addWidget(self.recovery)
        recovery_actions = QHBoxLayout()
        self.recovery_buttons = []
        for command, label in (("restore", "Einheit wiederherstellen"), ("save_recovered", "Einheit speichern")):
            control = QPushButton(label)
            control.clicked.connect(lambda checked=False, name=command: self.local_command(name))
            recovery_actions.addWidget(control)
            self.recovery_buttons.append(control)
            control.hide()
        layout.addLayout(recovery_actions)
        self.local_web_button = QPushButton("Lokale Trainingsansicht öffnen")
        self.local_web_button.clicked.connect(lambda: self.open_local())
        layout.addWidget(self.local_web_button)
        self.open_local = lambda: None
        self.update_button = QPushButton("Nach Update suchen und installieren")
        self.update_button.clicked.connect(lambda: self.local_command('update'))
        layout.addWidget(self.update_button)
        self.update_note = QLabel()
        self.update_note.setWordWrap(True)
        layout.addWidget(self.update_note)
        layout.addStretch()
        actions = QHBoxLayout()
        web_button = QPushButton("CADOS im Browser öffnen")
        web_button.setObjectName("secondary")
        web_button.clicked.connect(self.open_web)
        quit_button = QPushButton("Beenden")
        quit_button.clicked.connect(self.quit_callback)
        actions.addWidget(web_button)
        actions.addStretch()
        actions.addWidget(quit_button)
        layout.addLayout(actions)
        self.setCentralWidget(root)
        self.setStyleSheet("""
            QMainWindow { background: #f7faf9; color: #18323a; }
            QLabel#title { font-size: 24px; font-weight: 700; }
            QLabel#subtitle { color: #647780; font-size: 13px; }
            QLabel#connection { background: #edf3f2; border: 1px solid #d6e4e1; border-radius: 9px; padding: 11px 12px; color: #425b62; }
            QLabel#connection[online="true"] { background: #e7f5ef; border-color: #b9e3d1; color: #156348; }
            QFrame#card { background: white; border: 1px solid #dce7e4; border-radius: 11px; }
            QLabel#caption { color: #6b7e84; font-size: 12px; }
            QLabel#value { color: #19363e; font-weight: 600; }
            QPushButton { background: #137c73; color: white; border: 0; border-radius: 8px; padding: 9px 13px; font-weight: 600; }
            QPushButton#secondary { background: #e2ece9; color: #245057; }
            QPushButton:disabled { background: #e4eae7; color: #8a9790; }
            QPushButton:hover { background: #0f6a63; }
            QPushButton#secondary:hover { background: #d2e1dd; }
        """)

    def open_web(self) -> None:
        if self.config.workout_library_url:
            url = QUrl(self.config.workout_library_url)
            url.setFragment('connector-ready')
            QDesktopServices.openUrl(url)

    def update_status(self, data: dict) -> None:
        if data.get('update_message'):
            self.update_note.setText(data['update_message'])
        if data.get('error'):
            self.update_note.setText(data['error'])
        if 'state' in data:
            active = data['state'] in {'running', 'paused', 'waiting_for_pedal'}
            self.update_button.setEnabled(not active and not data.get('updating') and not data.get('recovery_available'))
            recovery = data.get('recovery_available')
            self.recovery.setText(('Unterbrochene Einheit: ' + recovery['name']) if recovery else '')
            for control in self.recovery_buttons:
                control.setVisible(bool(recovery))
        connected = bool(data.get("connected"))
        message = str(data.get("message") or data.get("error") or "Mit CADOS verbunden")
        self.connection.setText("● " + message)
        self.connection.setProperty("online", connected)
        self.connection.style().unpolish(self.connection)
        self.connection.style().polish(self.connection)
        if data.get("auto_close"):
            QTimer.singleShot(1500, self.quit_callback)
        state = data.get("state")
        if state is None:
            return
        self.training_buttons["pause"].setEnabled(state in {"running", "waiting_for_pedal"})
        self.training_buttons["resume"].setEnabled(state == "paused" and bool(data.get("trainer_connected")))
        self.training_buttons["stop"].setEnabled(state in {"running", "waiting_for_pedal", "paused"})
        self.values["device_status"].setText(str(data.get("device_status") or "Auswahl in der Web- oder lokalen Trainingsansicht"))
        self.values["device_status"].setWordWrap(True)
        self.values["trainer"].setText(str(data.get("trainer_name") or "Nicht verbunden") if data.get("trainer_connected") else "Nicht verbunden")
        self.values["hr"].setText(str(data.get("hr_name") or "Nicht verbunden") if data.get("hr_connected") else "Nicht verbunden")
        self.values["workout"].setText(str(data.get("workout_name") or "Kein Training aktiv"))
        self.values["state"].setText({"idle": "Bereit", "ready": "Bereit", "running": "Training läuft", "paused": "Pausiert", "waiting_for_pedal": "Warte auf Treten", "completed": "Abgeschlossen", "stopped": "Beendet"}.get(data.get("state"), "Bereit"))
        watts, cadence = data.get("current_watts"), data.get("current_cadence")
        self.values["power"].setText(f"{round(watts)} W" if watts is not None else "–")
        self.values["cadence"].setText(f"{round(cadence)} rpm" if cadence is not None else "–")
        if data.get("browser_connected"):
            self.values["browser"].setText("Verbunden")
        elif data.get("auto_close_deferred"):
            self.values["browser"].setText("Training läuft – bleibt offen")
        elif data.get("auto_close_remaining_sec") is not None:
            seconds = int(data["auto_close_remaining_sec"])
            self.values["browser"].setText(f"Nicht verbunden · Ende in {seconds // 60}:{seconds % 60:02d}")
        else:
            self.values["browser"].setText("Warte auf CADOS-Webseite")

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()


def run() -> int:
    config = AppConfig.load()
    configure_logging(config.paths.logs_dir)
    app = ConnectorApplication(sys.argv)
    app.setApplicationName("CADOS Connector")
    app.setQuitOnLastWindowClosed(False)
    instance_lock = QLockFile(str(config.paths.data_dir / 'connector.lock'))
    if not instance_lock.tryLock(0):
        QMessageBox.information(None, 'CADOS Connector', 'Der Connector läuft bereits. Öffne sein Fenster über das Symbol in der Menüleiste.')
        return 0
    if "--login" in sys.argv or any(arg.startswith('cados-connector://pair') for arg in sys.argv) or not (config.workout_library_url and config.workout_library_token):
        if not ConnectorPairing(config).exec():
            return 0
    bridge = StatusBridge()
    service: ConnectorService | None = None
    change_login = False
    pending_update = None

    def quit_connector() -> None:
        if service is not None:
            service.close()
        app.quit()

    window = ConnectorWindow(config, quit_connector)
    def show_connector() -> None:
        window.showNormal()
        window.raise_()
        window.activateWindow()
        window.open_web()
    app.open_requested.connect(lambda action: request_login() if action == "pair" else show_connector())
    bridge.changed.connect(window.update_status)
    def receive_update(data):
        nonlocal pending_update
        if data.get('update_ready'):
            pending_update = data['update_ready']
            quit_connector()
    bridge.changed.connect(receive_update)
    icon = QIcon(str(config.paths.app_icon_path))
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("CADOS Connector")
    menu = QMenu()
    show_action = QAction("Fenster anzeigen", menu)
    show_action.triggered.connect(window.showNormal)
    menu.addAction(show_action)
    login_action = QAction("Anmeldung ändern …", menu)
    def request_login():
        nonlocal change_login
        if service.engine.state in {"running", "paused", "waiting_for_pedal"}:
            window.showNormal()
            window.connection.setText("Bitte zuerst das Training beenden, um die Anmeldung zu ändern.")
            return
        change_login = True
        quit_connector()
    login_action.triggered.connect(request_login)
    menu.addAction(login_action)
    menu.addSeparator()
    quit_action = QAction("Connector beenden", menu)
    quit_action.triggered.connect(quit_connector)
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: window.showNormal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()
    service = ConnectorService(config, status_callback=bridge.changed.emit)
    window.local_command = service.submit_local_command
    window.open_local = lambda: QDesktopServices.openUrl(QUrl(service.local.page_url))

    def run_service() -> None:
        try:
            asyncio.run(service.run())
        except Exception as exc:
            logger.exception("CADOS Connector konnte nicht gestartet werden")
            bridge.changed.emit({"connected": False, "error": str(exc)})

    thread = threading.Thread(target=run_service, name="cados-connector", daemon=True)
    thread.start()
    window.show()
    QTimer.singleShot(0, window.open_web)
    exit_code = app.exec()
    service.close()
    thread.join(timeout=5)
    if pending_update:
        from cados.connector_update import launch_installer
        import os
        try:
            launch_installer(pending_update, Path(sys.executable).parents[2], os.getpid())
        except Exception:
            logger.exception("Automatische Installation nicht möglich")
            QDesktopServices.openUrl(QUrl.fromLocalFile(pending_update['path']))
    if change_login and not thread.is_alive():
        import subprocess
        command = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "cados"]
        subprocess.Popen([*command, "--login"])
    return exit_code
