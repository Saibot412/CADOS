"""Desktop window and menu-bar host for the local CADOS Connector."""
from __future__ import annotations

import asyncio
import logging
import sys
import threading

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget

from cados.config import AppConfig
from cados.connector import ConnectorService
from cados.logging_utils import configure_logging

logger = logging.getLogger(__name__)


class StatusBridge(QObject):
    changed = Signal(dict)


class ConnectorWindow(QMainWindow):
    def __init__(self, config: AppConfig, quit_callback) -> None:
        super().__init__()
        self.config, self.quit_callback = config, quit_callback
        self.setWindowTitle("CADOS Connector")
        self.setWindowIcon(QIcon(str(config.paths.app_icon_path)))
        self.setFixedSize(460, 445)
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
        )):
            caption = QLabel(label)
            caption.setObjectName("caption")
            value = QLabel("–")
            value.setObjectName("value")
            grid.addWidget(caption, row, 0)
            grid.addWidget(value, row, 1)
            self.values[key] = value
        layout.addWidget(card)
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
            QPushButton:hover { background: #0f6a63; }
            QPushButton#secondary:hover { background: #d2e1dd; }
        """)

    def open_web(self) -> None:
        if self.config.workout_library_url:
            QDesktopServices.openUrl(QUrl(self.config.workout_library_url))

    def update_status(self, data: dict) -> None:
        connected = bool(data.get("connected"))
        message = str(data.get("message") or data.get("error") or "Mit CADOS verbunden")
        self.connection.setText("● " + message)
        self.connection.setProperty("online", connected)
        self.connection.style().unpolish(self.connection)
        self.connection.style().polish(self.connection)
        if data.get("auto_close"):
            QTimer.singleShot(1500, self.quit_callback)
        if not connected:
            return
        self.values["trainer"].setText(str(data.get("trainer_name") or "Nicht verbunden") if data.get("trainer_connected") else "Nicht verbunden")
        self.values["hr"].setText(str(data.get("hr_name") or "Nicht verbunden") if data.get("hr_connected") else "Nicht verbunden")
        self.values["workout"].setText(str(data.get("workout_name") or "Kein Training aktiv"))
        self.values["state"].setText(str(data.get("state") or "bereit").capitalize())
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
    app = QApplication(sys.argv)
    app.setApplicationName("CADOS Connector")
    app.setQuitOnLastWindowClosed(False)
    bridge = StatusBridge()
    service: ConnectorService | None = None

    def quit_connector() -> None:
        if service is not None:
            service.close()
        app.quit()

    window = ConnectorWindow(config, quit_connector)
    bridge.changed.connect(window.update_status)
    icon = QIcon(str(config.paths.app_icon_path))
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("CADOS Connector")
    menu = QMenu()
    show_action = QAction("Fenster anzeigen", menu)
    show_action.triggered.connect(window.showNormal)
    menu.addAction(show_action)
    menu.addSeparator()
    quit_action = QAction("Connector beenden", menu)
    quit_action.triggered.connect(quit_connector)
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: window.showNormal() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()
    service = ConnectorService(config, status_callback=bridge.changed.emit)

    def run_service() -> None:
        try:
            asyncio.run(service.run())
        except Exception as exc:
            logger.exception("CADOS Connector konnte nicht gestartet werden")
            bridge.changed.emit({"connected": False, "error": str(exc)})

    thread = threading.Thread(target=run_service, name="cados-connector", daemon=True)
    thread.start()
    window.show()
    exit_code = app.exec()
    service.close()
    thread.join(timeout=5)
    return exit_code
