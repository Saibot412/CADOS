from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from cados.config import AppConfig
from cados.logging_utils import configure_logging
from cados.services.storage import DataStore
from cados.services.trainer import TrainerController
from cados.services.workout_catalog import WorkoutCatalog
from cados.services.workout_library import WorkoutLibraryClient
from cados.ui.main_window import MainWindow
from cados.ui.theme import apply_theme

logger = logging.getLogger(__name__)


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("cados.desktop")
    except Exception:
        logger.debug("Windows AppUserModelID konnte nicht gesetzt werden.", exc_info=True)


def run() -> int:
    config = AppConfig.load()
    configure_logging(config.paths.logs_dir)
    logger.info("Starte Cados.")
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("Cados")
    apply_theme(app, config.theme_mode)
    if config.paths.app_icon_path.exists():
        app.setWindowIcon(QIcon(str(config.paths.app_icon_path)))

    store = DataStore(config.paths.database_path)
    migrated = store.migrate_legacy_json(
        config.paths.legacy_profiles_path, config.paths.legacy_sessions_path
    )
    if migrated["profiles"] or migrated["sessions"]:
        logger.info("Altdaten nach SQLite übernommen: %s", migrated)
    loader = WorkoutCatalog(config.paths.bundled_workouts_dir, store)
    library = WorkoutLibraryClient(
        config.workout_library_url, config.workout_library_token
    )
    trainer = TrainerController(config.trainer_scan_timeout_sec)

    window = MainWindow(
        config=config, loader=loader, store=store, trainer=trainer,
        workout_library=library,
    )
    if config.paths.app_icon_path.exists():
        window.setWindowIcon(QIcon(str(config.paths.app_icon_path)))
    app.aboutToQuit.connect(window.shutdown)
    window.showMaximized()
    return app.exec()
