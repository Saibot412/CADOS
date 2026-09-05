from __future__ import annotations

import html
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QStatusBar,
    QTableWidgetItem,
)

from cados.config import AppConfig
from cados.core.workout_engine import TrainingSnapshot, WorkoutEngine
from cados.core.workout_loader import WorkoutValidationError
from cados.core.hr_zones import HR_ZONES, hr_zone_for_bpm, hr_zone_range_label, hr_zone_pct_label
from cados.core.zones import (
    POWER_ZONES,
    ZoneSummaryEntry,
    build_zone_summary,
    power_zone_for_watts,
    summarize_workout_zones,
    zone_pct_range_label,
    zone_watt_range_label,
)
from cados.models.profile import UserProfile, iso_now
from cados.models.session import WorkoutSessionRecord
from cados.models.workout import DEFAULT_FTP_WATTS, ResolvedWorkout, WorkoutTemplate
from cados.services.hr_monitor import HRMonitorService
from cados.services.storage import DataStore
from cados.services.trainer import TrainerController, TrainerDevice
from cados.services.workout_catalog import WorkoutCatalog
from cados.services.workout_library import WorkoutLibraryClient
from cados.ui.dialogs import FTPResultDialog, ProfileDialog, WorkoutLibraryDialog
from cados.ui.main_window_view import MainWindowView
from cados.ui.library_widgets import (
    format_duration,
    format_timestamp,
    WORKOUT_ITEM_COUNT_ROLE,
    WORKOUT_ITEM_HEADER_ROLE,
)

logger = logging.getLogger(__name__)

WORKOUT_CATEGORY_ORDER: dict[str, int] = {
    "Regeneration": 10,
    "Grundlage": 20,
    "Tempo / Sweet Spot": 30,
    "Schwelle": 40,
    "VO2max": 50,
    "Tests": 60,
}


@dataclass(slots=True)
class AutoConnectResult:
    state: str
    devices: list[TrainerDevice]
    device_name: str | None = None
    error_message: str | None = None


class MainWindowSignals(QObject):
    auto_connect_finished = Signal(object)
    hr_connect_finished = Signal(object)
    library_finished = Signal(object)


class MainWindow(MainWindowView):
    def __init__(
        self,
        config: AppConfig,
        loader: WorkoutCatalog,
        store: DataStore,
        trainer: TrainerController,
        workout_library: WorkoutLibraryClient | None = None,
    ):
        super().__init__()
        self.config = config
        self.loader = loader
        self.store = store
        self.trainer = trainer
        self.workout_library = workout_library or WorkoutLibraryClient("", "")
        self.hr_monitor = HRMonitorService()
        self.engine = WorkoutEngine(trainer, self.hr_monitor)
        self._brand_logo_pixmap = self._load_brand_logo_pixmap()

        self.profiles: list[UserProfile] = []
        self.workouts: list[WorkoutTemplate] = []
        self.session_records: list[WorkoutSessionRecord] = []
        self.current_profile: UserProfile | None = None
        self.current_workout_template: WorkoutTemplate | None = None
        self.current_workout: ResolvedWorkout | None = None
        self._signals = MainWindowSignals()
        self._known_trainer_devices: list[TrainerDevice] = []
        self._last_tick = time.monotonic()
        self._auto_connect_started = False
        self._auto_connect_in_progress = False
        self._auto_connect_status = "initializing"
        self._hr_auto_connect_in_progress = False
        self._hr_auto_connect_status = "initializing"
        self._shutting_down = False
        self._next_session_save_attempt = 0.0
        self._library_request_in_progress = False

        self.setWindowTitle("Cados")
        self._fit_to_screen()
        self.setStatusBar(QStatusBar(self))

        self._build_ui()
        self._connect_signals()
        self._signals.auto_connect_finished.connect(self._handle_auto_connect_finished)
        self._signals.hr_connect_finished.connect(self._handle_hr_connect_finished)
        self._signals.library_finished.connect(self._handle_library_finished)
        # Global key event filter to catch keys even when child widgets have focus
        QApplication.instance().installEventFilter(self)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(self.config.tick_interval_ms)

        self.reconnect_timer = QTimer(self)
        self.reconnect_timer.timeout.connect(self._auto_connect_trainer)
        self.reconnect_timer.start(8000)

        self.hr_reconnect_timer = QTimer(self)
        self.hr_reconnect_timer.timeout.connect(self._auto_connect_hr)
        self.hr_reconnect_timer.start(10000)

        self._reload_profiles()
        self._reload_workouts()
        self._refresh_status_labels()
        self._apply_training_snapshot(self.engine.snapshot())
        if self.workout_library.enabled:
            QTimer.singleShot(500, self._sync_workouts)

    def _apply_zone_summary_rows(
        self,
        rows: list[tuple[QLabel, QLabel, QLabel]],
        summary: tuple[ZoneSummaryEntry, ...],
    ) -> None:
        summary_by_index = {entry.zone.index: entry for entry in summary}
        for zone, widgets in zip(POWER_ZONES, rows):
            range_label, time_label, percent_label = widgets
            entry = summary_by_index.get(zone.index)
            if entry is None:
                range_label.setText("-")
                time_label.setText("00:00")
                percent_label.setText("0%")
                continue

            range_label.setText(f"{entry.watt_range_label} | {entry.pct_range_label}")
            time_label.setText(format_duration(entry.duration_sec))
            percent_label.setText(self._format_percentage(entry.percentage))

    def _apply_hr_zone_labels(self, labels: list[QLabel]) -> None:
        max_hr = self.current_profile.max_hr if self.current_profile and self.current_profile.max_hr else None
        for zone, label in zip(HR_ZONES, labels):
            if max_hr and max_hr > 0:
                label.setText(f"{hr_zone_range_label(zone, max_hr)} | {hr_zone_pct_label(zone)}")
            else:
                label.setText(hr_zone_pct_label(zone))

    @staticmethod
    def _format_percentage(value: float) -> str:
        if abs(value - round(value)) < 0.05:
            return f"{round(value)}%"
        return f"{value:.1f}%"

    def _workout_session_count(self, workout: WorkoutTemplate) -> int:
        source_name = workout.source_path.name
        count = 0
        for session in self.session_records:
            if session.duration_sec <= 0:
                continue
            if session.workout_file_name:
                if session.workout_file_name == source_name:
                    count += 1
            elif session.workout_name == workout.name:
                count += 1
        return count

    @staticmethod
    def _workout_sort_key(workout: WorkoutTemplate) -> tuple[int, str, int, str]:
        category = workout.category.strip() or "Sonstiges"
        return (
            WORKOUT_CATEGORY_ORDER.get(category, 999),
            category.lower(),
            workout.sort_order,
            workout.name.lower(),
        )

    def _refresh_workout_list_counts(self) -> None:
        for row in range(self.workout_list.count()):
            item = self.workout_list.item(row)
            if item is None:
                continue
            if bool(item.data(WORKOUT_ITEM_HEADER_ROLE)):
                continue
            key = item.data(Qt.UserRole)
            workout = next((entry for entry in self.workouts if str(entry.source_path) == key), None)
            if workout is None:
                continue
            item.setText(workout.name)
            item.setData(WORKOUT_ITEM_COUNT_ROLE, f"{self._workout_session_count(workout)}x")
            item.setSizeHint(QSize(0, 34))
        self.workout_list.viewport().update()

    def _connect_signals(self) -> None:
        self.refresh_workouts_button.clicked.connect(self._reload_workouts)
        self.import_workout_button.clicked.connect(self._import_workout)
        self.sync_workouts_button.clicked.connect(self._sync_workouts)
        self.library_settings_button.clicked.connect(self._configure_workout_library)
        self.workout_list.currentItemChanged.connect(lambda current, _: self._display_selected_workout(current))
        self.start_workout_button.clicked.connect(self._start_selected_workout)
        self.prev_block_button.clicked.connect(lambda: self._apply_training_snapshot(self.engine.previous_block()))
        self.skip_button.clicked.connect(lambda: self._apply_training_snapshot(self.engine.skip_block()))
        self.plus_button.clicked.connect(lambda: self._apply_training_snapshot(self.engine.adjust_target(5)))
        self.minus_button.clicked.connect(lambda: self._apply_training_snapshot(self.engine.adjust_target(-5)))
        self.training_exit_button.clicked.connect(self._exit_training)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.new_profile_button.clicked.connect(self._create_profile)
        self.edit_profile_button.clicked.connect(self._edit_profile)
        self.repeat_session_button.clicked.connect(self._repeat_selected_session)
        self.session_table.itemDoubleClicked.connect(lambda _: self._repeat_selected_session())

    def _reload_profiles(self) -> None:
        selected_id = self.current_profile.id if self.current_profile else None
        self.profiles = self.store.list_profiles()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in self.profiles:
            self.profile_combo.addItem(f"{profile.name} ({profile.ftp_watts} W FTP)", profile.id)
        self.profile_combo.blockSignals(False)

        if not self.profiles:
            self.current_profile = None
            return

        index = 0
        if selected_id:
            for row, profile in enumerate(self.profiles):
                if profile.id == selected_id:
                    index = row
                    break
        self.profile_combo.setCurrentIndex(index)
        self._on_profile_changed()

    def _on_profile_changed(self) -> None:
        profile_id = self.profile_combo.currentData()
        self.current_profile = next((profile for profile in self.profiles if profile.id == profile_id), None)
        self.engine.set_profile(self.current_profile)
        self._reload_sessions()
        if self.current_workout_template is not None:
            self._display_workout_preview(self.current_workout_template)
        self._refresh_status_labels()

    def _create_profile(self) -> None:
        dialog = ProfileDialog(parent=self, default_ftp=self.config.default_ftp)
        if dialog.exec():
            self.store.save_profile(dialog.build_profile())
            self._reload_profiles()

    def _edit_profile(self) -> None:
        if self.current_profile is None:
            return
        dialog = ProfileDialog(self.current_profile, self)
        if dialog.exec():
            self.store.save_profile(dialog.build_profile())
            self._reload_profiles()

    def _configure_workout_library(self) -> None:
        dialog = WorkoutLibraryDialog(
            self.workout_library.base_url, self.workout_library.token, self
        )
        if not dialog.exec():
            return
        url, token = dialog.values()
        self.config.workout_library_url = url
        self.config.workout_library_token = token
        self.config.save_settings({
            "workout_library_url": url,
            "workout_library_token": token,
        })
        self.workout_library = WorkoutLibraryClient(url, token)
        if self.workout_library.enabled:
            self._sync_workouts()
        else:
            self.statusBar().showMessage("Zentrale Workout-Bibliothek deaktiviert", 5000)

    def _import_workout(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Workout importieren",
            "",
            "Workout-Dateien (*.json *.zwo);;CADOS JSON (*.json);;Zwift Workout (*.zwo)",
        )
        if not file_name:
            return
        try:
            workout = self.loader.import_file(Path(file_name))
        except (OSError, UnicodeError, ValueError, WorkoutValidationError) as exc:
            QMessageBox.warning(self, "Import fehlgeschlagen", str(exc))
            return
        self._reload_workouts()
        self._select_workout(workout.source_path.name)
        if self.workout_library.enabled:
            self._start_library_worker("publish", workout)
            self.statusBar().showMessage(
                f"{workout.name} importiert · Veröffentlichung läuft …"
            )
        else:
            self.statusBar().showMessage(
                f"{workout.name} lokal importiert · Server noch nicht eingerichtet", 8000
            )

    def _select_workout(self, source_name: str) -> None:
        for row in range(self.workout_list.count()):
            item = self.workout_list.item(row)
            if item is None or bool(item.data(WORKOUT_ITEM_HEADER_ROLE)):
                continue
            if Path(str(item.data(Qt.UserRole))).name == source_name:
                self.workout_list.setCurrentItem(item)
                return

    def _sync_workouts(self) -> None:
        if not self.workout_library.enabled:
            self._configure_workout_library()
            return
        self._start_library_worker("sync")
        self.statusBar().showMessage("Online-Workouts werden geladen …")

    def _start_library_worker(self, action: str, workout: WorkoutTemplate | None = None) -> None:
        if self._library_request_in_progress:
            self.statusBar().showMessage("Eine Bibliotheksanfrage läuft bereits", 4000)
            return
        self._library_request_in_progress = True
        self.sync_workouts_button.setEnabled(False)
        threading.Thread(
            target=self._run_library_worker,
            args=(action, workout),
            daemon=True,
        ).start()

    def _run_library_worker(self, action: str, workout: WorkoutTemplate | None) -> None:
        result: dict[str, object] = {"action": action, "ok": False}
        try:
            if action == "sync":
                result["count"] = self.loader.sync(self.workout_library)
            elif action == "publish" and workout is not None:
                remote = self.workout_library.publish(workout)
                self.loader.save_remote(remote)
                result["name"] = workout.name
            result["ok"] = True
        except Exception as exc:
            logger.warning("Workout-Bibliothek fehlgeschlagen: %s", exc)
            result["error"] = str(exc)
        if not self._shutting_down:
            self._signals.library_finished.emit(result)

    def _handle_library_finished(self, result: dict[str, object]) -> None:
        self._library_request_in_progress = False
        self.sync_workouts_button.setEnabled(True)
        if result.get("ok"):
            self._reload_workouts()
            if result.get("action") == "sync":
                self.statusBar().showMessage(
                    f"{result.get('count', 0)} Online-Workouts aktualisiert", 6000
                )
            else:
                self.statusBar().showMessage(
                    f"{result.get('name', 'Workout')} zentral gespeichert", 6000
                )
        else:
            QMessageBox.warning(
                self,
                "Workout-Bibliothek",
                str(result.get("error") or "Unbekannter Fehler"),
            )

    def _reload_workouts(self) -> None:
        selected_key = None
        current_item = self.workout_list.currentItem()
        if current_item is not None and not bool(current_item.data(WORKOUT_ITEM_HEADER_ROLE)):
            selected_key = current_item.data(Qt.UserRole)

        self.workouts = sorted(self.loader.scan(), key=self._workout_sort_key)
        self.workout_list.clear()
        current_category: str | None = None
        for workout in self.workouts:
            category = workout.category.strip() or "Sonstiges"
            if category != current_category:
                current_category = category
                header_item = QListWidgetItem(category)
                header_item.setData(WORKOUT_ITEM_HEADER_ROLE, True)
                header_item.setFlags(Qt.NoItemFlags)
                header_item.setSizeHint(QSize(0, 26))
                self.workout_list.addItem(header_item)
            item = QListWidgetItem(workout.name)
            item.setData(Qt.UserRole, str(workout.source_path))
            item.setData(WORKOUT_ITEM_COUNT_ROLE, "0x")
            item.setToolTip(str(workout.source_path))
            self.workout_list.addItem(item)
        self._refresh_workout_list_counts()

        if not self.workouts:
            self.current_workout = None
            self._clear_preview()
            return

        if selected_key:
            for row in range(self.workout_list.count()):
                item = self.workout_list.item(row)
                if item.data(Qt.UserRole) == selected_key:
                    self.workout_list.setCurrentItem(item)
                    return
        for row in range(self.workout_list.count()):
            item = self.workout_list.item(row)
            if item is not None and not bool(item.data(WORKOUT_ITEM_HEADER_ROLE)):
                self.workout_list.setCurrentRow(row)
                return

    def _display_selected_workout(self, item: QListWidgetItem | None) -> None:
        if item is None or bool(item.data(WORKOUT_ITEM_HEADER_ROLE)):
            self._clear_preview()
            return
        key = item.data(Qt.UserRole)
        workout = next((entry for entry in self.workouts if str(entry.source_path) == key), None)
        if workout is not None:
            self._display_workout_preview(workout)

    def _display_workout_preview(self, workout: WorkoutTemplate) -> None:
        resolved = self._resolve_workout_for_profile(workout)
        self.current_workout_template = workout
        self.current_workout = resolved
        self.preview_name_label.setText(workout.name)
        self.preview_description_label.setText(workout.description or "Keine Beschreibung vorhanden.")
        self._update_preview_workout_info(workout)
        self.preview_duration_label.setText(format_duration(workout.total_duration_sec))
        self.preview_duration_label.setVisible(True)
        self.preview_timeline.set_workout(resolved, resolved.ftp_watts)
        self.preview_timeline.set_state(-1, 0)
        self._apply_zone_summary_rows(self.preview_zone_rows, summarize_workout_zones(resolved))
        self._apply_hr_zone_labels(self.preview_hr_zone_labels)
        self._populate_block_table(workout)
        self._refresh_status_labels()

    @staticmethod
    def _workout_info_sections(workout: WorkoutTemplate) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        if workout.best_for.strip():
            sections.append(("Wofür gut", workout.best_for.strip()))
        if workout.when_to_do.strip():
            sections.append(("Wann fahren", workout.when_to_do.strip()))
        if workout.skip_if.strip():
            sections.append(("Eher nicht wenn", workout.skip_if.strip()))
        if not sections and workout.description.strip():
            sections.append(("Info", workout.description.strip()))
        return sections

    @classmethod
    def _workout_info_html(cls, workout: WorkoutTemplate) -> str:
        sections = cls._workout_info_sections(workout)
        if not sections:
            return "<b>Info</b><br>Keine Zusatzinfo vorhanden."
        label_map = {
            "Wofür gut": "Gut",
            "Wann fahren": "Wann",
            "Eher nicht wenn": "Nicht",
            "Info": "Info",
        }
        return "<br>".join(
            f"<b>{html.escape(label_map.get(title, title))}:</b> {html.escape(text).replace(chr(10), ' ')}"
            for title, text in sections
        )

    def _update_preview_workout_info(self, workout: WorkoutTemplate | None) -> None:
        if workout is None:
            self.preview_guidance_label.clear()
            self.preview_guidance_label.setVisible(False)
            return
        self.preview_guidance_label.setText(self._workout_info_html(workout))
        self.preview_guidance_label.setVisible(True)

    def _populate_block_table(self, workout: WorkoutTemplate) -> None:
        self.block_table.setRowCount(len(workout.blocks))
        for row, block in enumerate(workout.blocks):
            values = [
                str(row + 1),
                block.label,
                format_duration(block.duration_sec),
                f"{block.watts_summary} / {block.target_cadence or '-'} rpm",
            ]
            for column, value in enumerate(values):
                self.block_table.setItem(row, column, QTableWidgetItem(value))

    def _clear_preview(self) -> None:
        self.preview_name_label.setText("Kein Workout gewählt")
        self.preview_description_label.setText("Importiere eine JSON- oder ZWO-Datei oder wähle links ein Workout.")
        self.preview_duration_label.setText("-")
        self.preview_duration_label.setVisible(False)
        self._update_preview_workout_info(None)
        self.current_workout_template = None
        self.current_workout = None
        self.preview_timeline.set_workout(None)
        self._apply_zone_summary_rows(
            self.preview_zone_rows,
            build_zone_summary([0.0] * len(POWER_ZONES), self._active_ftp_watts(), 0.0),
        )
        self._apply_hr_zone_labels(self.preview_hr_zone_labels)
        self.block_table.setRowCount(0)
        self._refresh_status_labels()

    def _reload_sessions(self) -> None:
        user_id = self.current_profile.id if self.current_profile else None
        self.session_records = self.store.list_sessions(user_id, include_samples=False)
        self.session_table.setRowCount(len(self.session_records))

        for row, session in enumerate(self.session_records):
            values = [
                format_timestamp(session.timestamp),
                session.workout_name,
                format_duration(session.duration_sec),
                session.status,
                session.trainer_source,
            ]
            for column, value in enumerate(values):
                self.session_table.setItem(row, column, QTableWidgetItem(value))
        self._refresh_workout_list_counts()

    def _selected_session(self) -> WorkoutSessionRecord | None:
        row = self.session_table.currentRow()
        if row < 0 or row >= len(self.session_records):
            return None
        return self.session_records[row]

    def _repeat_selected_session(self) -> None:
        session = self._selected_session()
        if session is None:
            return

        workout = self._workout_from_session(session)
        if workout is None:
            QMessageBox.warning(self, "Workout nicht verfügbar", "Die Session enthält kein wieder ladbares Workout.")
            return
        self.stack.setCurrentWidget(self.library_page)
        self._show_training_header(False)
        self._display_workout_preview(workout)

    def _workout_from_session(self, session: WorkoutSessionRecord) -> WorkoutTemplate | None:
        if session.workout_file_name:
            candidate = self.loader.get_by_source_name(session.workout_file_name)
            if candidate is not None:
                return candidate

        if session.workout_payload:
            source_name = session.workout_file_name or f"history_{session.id}.json"
            try:
                return self.loader.load_payload(session.workout_payload, Path(self.config.paths.workouts_dir / source_name))
            except (WorkoutValidationError, ValueError) as exc:
                logger.warning("Workout aus Session-Payload konnte nicht geladen werden: %s", exc)
        return None

    def _start_selected_workout(self) -> None:
        if self.current_workout_template is None:
            return
        if not self.trainer.ready_for_workout():
            QMessageBox.warning(
                self,
                "Trainer nicht bereit",
                "Es besteht noch keine Verbindung zum Wahoo-Trainer.",
            )
            return

        if not self._persist_pending_session(force=True):
            return
        self.engine.set_profile(self.current_profile)
        self.engine.load_workout(self.current_workout_template, ftp_watts=self._active_ftp_watts())
        self.current_workout = self.engine.workout
        snapshot = self.engine.start()
        self._last_tick = time.monotonic()
        self.stack.setCurrentWidget(self.training_page)
        self._show_training_header(True)
        self.training_timeline.set_workout(self.current_workout, self.current_workout.ftp_watts if self.current_workout else None)
        self._apply_training_snapshot(snapshot)

    def _show_training_header(self, visible: bool) -> None:
        self.training_state_pill.setVisible(visible)
        self.training_exit_button.setVisible(visible)
        self.profile_container.setVisible(not visible)
        if visible and self.current_profile:
            self.training_user_label.setText(f"\U0001F6B4 {self.current_profile.name}")
        self.training_user_label.setVisible(visible)

    def _stop_workout(self) -> None:
        snapshot = self.engine.stop()
        self._apply_training_snapshot(snapshot)
        self._persist_pending_session()

    def _apply_training_snapshot(self, snapshot: TrainingSnapshot) -> None:
        self._apply_training_state_label(snapshot.state, auto_paused=snapshot.auto_paused)

        # ── Watts with zone coloring ────────────────────────
        ftp = self.current_workout.ftp_watts if self.current_workout else 250
        current_zone = power_zone_for_watts(snapshot.current_watts, ftp)
        target_zone = power_zone_for_watts(snapshot.target_watts, ftp)

        self.current_watts_value.setText(f"{snapshot.current_watts} W")
        self.current_watts_value.setStyleSheet(f"font-size: 36px; font-weight: 700; color: {current_zone.color};")
        self.current_watts_detail_label.setText("Live vom Trainer")
        self.target_watts_value.setText(f"{snapshot.target_watts} W")
        self.target_watts_value.setStyleSheet(f"font-size: 36px; font-weight: 700; color: {target_zone.color};")
        target_detail = snapshot.target_pct_label or ""
        if snapshot.ramping:
            target_detail = "Rampe\u2026" + (f" ({target_detail})" if target_detail else "")
        self.target_pct_detail_label.setText(target_detail)

        # ── Cadence with green/red coloring ─────────────────
        self.current_cadence_value.setText(f"{snapshot.current_cadence} rpm")
        if snapshot.target_cadence is not None and snapshot.state in {"running", "waiting_for_pedal"}:
            diff = abs(snapshot.current_cadence - snapshot.target_cadence)
            cad_color = "#2FBF71" if diff <= 5 else "#EB5757"
        else:
            cad_color = "#162840"
        self.current_cadence_value.setStyleSheet(f"font-size: 36px; font-weight: 700; color: {cad_color};")
        self.current_cadence_detail_label.setText("Live vom Trainer")
        target_cadence_text = f"{snapshot.target_cadence} rpm" if snapshot.target_cadence is not None else "- rpm"
        self.target_cadence_value.setText(target_cadence_text)
        self.target_cadence_detail_label.setText("")

        # ── Time / Block / Zone ─────────────────────────────
        self.time_summary_value.setText(f"{format_duration(snapshot.active_sec)} / {format_duration(snapshot.remaining_sec)}")
        self.time_summary_detail_label.setText("Gefahren / Im Workout verbleibend")
        if snapshot.block_count > 0:
            block_text = f"{snapshot.block_index + 1}/{snapshot.block_count} {snapshot.current_block_name}"
            self.block_value.setText(block_text)
            self.block_detail_label.setText(f"Block {snapshot.block_index + 1} von {snapshot.block_count}")
            self.training_chart_context_label.setText(block_text)
        else:
            self.block_value.setText("-")
            self.block_detail_label.setText("Aktueller Block")
            self.training_chart_context_label.setText("Kein Block")
        if self.current_workout is not None:
            zone_source_watts = snapshot.current_watts if snapshot.state in {"running", "paused", "completed", "waiting_for_pedal"} else snapshot.target_watts
            zone = power_zone_for_watts(zone_source_watts, self.current_workout.ftp_watts)
            self.zone_value.setText(zone.label)
            self.zone_value.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {zone.color};")
            self.zone_detail_label.setText(
                f"{zone_watt_range_label(zone, self.current_workout.ftp_watts)} | {zone_pct_range_label(zone)}"
            )
        else:
            self.zone_value.setText(snapshot.zone_label)
            self.zone_value.setStyleSheet("font-size: 28px; font-weight: 700; color: #162840;")
            self.zone_detail_label.setText("")
        self.training_adjustment_label.setText(f"Bias {snapshot.adjustment_watts:+d} W")

        # ── Heart Rate with zone coloring ──────────────────
        max_hr = self.current_profile.max_hr if self.current_profile and self.current_profile.max_hr else None
        if snapshot.hr_connected and snapshot.heart_rate > 0:
            if max_hr and max_hr > 0:
                hr_zone = hr_zone_for_bpm(snapshot.heart_rate, max_hr)
                hr_color = hr_zone.color
                hr_range = hr_zone_range_label(hr_zone, max_hr)
                self.hr_value.setText(f"{snapshot.heart_rate} bpm")
                self.hr_detail_label.setText(f"{hr_zone.label} | {hr_range}")
            else:
                hr_color = "#162840"
                self.hr_value.setText(f"{snapshot.heart_rate} bpm")
                self.hr_detail_label.setText("Max HF im Profil setzen")
            self.hr_value.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {hr_color};")
        else:
            self.hr_value.setText("- bpm")
            self.hr_value.setStyleSheet("font-size: 28px; font-weight: 700; color: #a0a8b4;")
            self.hr_detail_label.setText("Nicht verbunden")

        # ── Live Metrics ────────────────────────────────────
        self.avg_watts_value.setText(f"{snapshot.avg_watts} W")
        self.avg_watts_detail.setText(f"NP: {snapshot.normalized_power} W")
        self.avg_cadence_value.setText(f"{snapshot.avg_cadence} rpm")
        if snapshot.avg_heart_rate > 0:
            self.avg_hr_value.setText(f"{snapshot.avg_heart_rate} bpm")
        else:
            self.avg_hr_value.setText("- bpm")
        self.tss_value.setText(f"{snapshot.tss:.0f}")
        self.tss_detail.setText(f"IF: {snapshot.intensity_factor:.2f}")
        self.calories_value.setText(f"{snapshot.calories} kcal")

        if self.current_workout is not None:
            self.training_timeline.set_state(snapshot.block_index, snapshot.elapsed_sec)
        self._update_training_controls(snapshot)
        self._refresh_status_labels()

    def _update_training_controls(self, snapshot: TrainingSnapshot) -> None:
        self.start_workout_button.setEnabled(self.current_workout_template is not None and self.trainer.ready_for_workout())
        active = snapshot.state in {"running", "paused", "waiting_for_pedal"}
        self.skip_button.setEnabled(active)
        self.plus_button.setEnabled(active)
        self.minus_button.setEnabled(active)
        self.training_exit_button.setEnabled(self.current_workout_template is not None or snapshot.state != "idle")

    def _apply_training_state_label(self, state: str, auto_paused: bool = False) -> None:
        dot_colors = {
            "idle": "#c0c7d1",
            "ready": "#c0c7d1",
            "waiting_for_pedal": "#0a84ff",
            "running": "#34c759",
            "paused": "#ff9f0a",
            "completed": "#0a84ff",
            "stopped": "#ff3b30",
        }
        labels = {
            "idle": "Bereit",
            "ready": "Bereit",
            "waiting_for_pedal": "Warte auf Tritt",
            "running": "Aktiv",
            "paused": "Pausiert",
            "completed": "Abgeschlossen",
            "stopped": "Gestoppt",
        }
        text = labels.get(state, "Status")
        dot_color = dot_colors.get(state, "#c0c7d1")
        if state == "paused" and auto_paused:
            text = "Warte auf Tritt"
            dot_color = "#0a84ff"
        self.training_state_value_label.setText(text)
        self.training_state_dot.setStyleSheet(
            f"background: {dot_color}; border-radius: 5px; min-width: 10px; min-height: 10px;"
        )

    def _refresh_status_labels(self) -> None:
        storage_status = self.store.status_label
        trainer_tooltip = self._refresh_trainer_status_pill()
        self._refresh_hr_status_pill()
        self.statusBar().showMessage(f"{storage_status} | {trainer_tooltip}")

    def _refresh_trainer_status_pill(self) -> str:
        snapshot = self.trainer.bluetooth.read_snapshot()
        if snapshot.connected:
            device_name = snapshot.device_name if snapshot.device_name != "Nicht verbunden" else "Wahoo"
            self._set_trainer_status_pill("connected", device_name, "Verbunden")
            tooltip = f"{device_name} | Verbunden"
        elif not self.trainer.bluetooth.available:
            self._set_trainer_status_pill("error", "Trainer", "Bluetooth nicht verfügbar")
            tooltip = "Bluetooth nicht verfügbar"
        elif self._auto_connect_in_progress or self._auto_connect_status == "initializing":
            self._set_trainer_status_pill("searching", "Trainer", "Suche Wahoo...")
            tooltip = "Suche automatisch nach Wahoo/KICKR"
        elif self._auto_connect_status == "not_found":
            self._set_trainer_status_pill("idle", "Trainer", "Wahoo nicht gefunden")
            tooltip = "Kein Wahoo/KICKR gefunden"
        elif self._auto_connect_status == "error":
            self._set_trainer_status_pill("error", "Trainer", "Verbindung fehlgeschlagen")
            tooltip = self.trainer.status_text()
        else:
            self._set_trainer_status_pill("idle", "Trainer", "Nicht verbunden")
            tooltip = self.trainer.status_text()

        self.trainer_status_pill.setToolTip(tooltip)
        self.trainer_status_title_label.setToolTip(tooltip)
        self.trainer_status_value_label.setToolTip(tooltip)
        return tooltip

    def _set_trainer_status_pill(self, state: str, title: str, value: str) -> None:
        state_styles = {
            "connected": ("#34c759", "#1c2a3d"),
            "searching": ("#ff9f0a", "#6d7b8c"),
            "error": ("#ff3b30", "#b23a35"),
            "idle": ("#c0c7d1", "#7c8796"),
        }
        dot_color, value_color = state_styles.get(state, state_styles["idle"])
        self.trainer_status_title_label.setText(title)
        self.trainer_status_value_label.setText(value)
        self.trainer_status_dot.setStyleSheet(
            f"background: {dot_color}; border-radius: 5px; min-width: 10px; min-height: 10px;"
        )
        self.trainer_status_value_label.setStyleSheet(f"color: {value_color};")

    def _refresh_hr_status_pill(self) -> None:
        hr_snap = self.hr_monitor.read_snapshot()
        if hr_snap.connected:
            device = hr_snap.device_name if hr_snap.device_name != "Nicht verbunden" else "HR"
            hr_text = f"{hr_snap.heart_rate} bpm" if hr_snap.heart_rate > 0 else "Verbunden"
            self._set_hr_status_pill("connected", device, hr_text)
        elif not self.hr_monitor.available:
            self._set_hr_status_pill("error", "HR", "Nicht verfügbar")
        elif self._hr_auto_connect_in_progress:
            self._set_hr_status_pill("searching", "HR", "Suche...")
        elif self._hr_auto_connect_status == "not_found":
            self._set_hr_status_pill("idle", "HR", "Nicht gefunden")
        else:
            self._set_hr_status_pill("idle", "HR", "Nicht verbunden")

    def _set_hr_status_pill(self, state: str, title: str, value: str) -> None:
        state_styles = {
            "connected": ("#34c759", "#1c2a3d"),
            "searching": ("#ff9f0a", "#6d7b8c"),
            "error": ("#ff3b30", "#b23a35"),
            "idle": ("#c0c7d1", "#7c8796"),
        }
        dot_color, value_color = state_styles.get(state, state_styles["idle"])
        self.hr_status_title_label.setText(title)
        self.hr_status_value_label.setText(value)
        self.hr_status_dot.setStyleSheet(
            f"background: {dot_color}; border-radius: 5px; min-width: 10px; min-height: 10px;"
        )
        self.hr_status_value_label.setStyleSheet(f"color: {value_color};")

    def _on_tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        snapshot = self.engine.tick(dt)
        self._apply_training_snapshot(snapshot)
        self._persist_pending_session()

    def _persist_pending_session(self, *, force: bool = False, show_feedback: bool = True) -> bool:
        session = self.engine.pending_session
        if session is None:
            return True
        if not force and time.monotonic() < self._next_session_save_attempt:
            return False
        try:
            self.store.save_session(session)
        except Exception:
            logger.exception("Session konnte nicht gespeichert werden; bleibt für erneuten Versuch erhalten.")
            self._next_session_save_attempt = time.monotonic() + 5.0
            self.statusBar().showMessage("Speichern fehlgeschlagen. Erneuter Versuch folgt; bitte App geöffnet lassen.")
            return False
        self.engine.acknowledge_session(session.id)
        self._next_session_save_attempt = 0.0
        if not show_feedback:
            return True
        self._reload_sessions()
        self.statusBar().showMessage(f"Session gespeichert: {session.workout_name} ({session.status})", 5000)
        if self.engine.is_ftp_test and self.current_profile is not None:
            calculated_ftp = self.engine.calculate_ftp_from_ramp()
            if calculated_ftp > 50:
                self._show_ftp_result_dialog(calculated_ftp)
        return True

    def _show_ftp_result_dialog(self, calculated_ftp: int) -> None:
        if self.current_profile is None:
            return
        current_ftp = self.current_profile.ftp
        best_1min = self.engine.best_1min_avg_watts()
        dialog = FTPResultDialog(current_ftp, calculated_ftp, best_1min, parent=self)
        if dialog.exec():
            updated = UserProfile(
                id=self.current_profile.id,
                name=self.current_profile.name,
                ftp=calculated_ftp,
                weight_kg=self.current_profile.weight_kg,
                max_hr=self.current_profile.max_hr,
                created_at=self.current_profile.created_at,
                updated_at=iso_now(),
            )
            self.store.save_profile(updated)
            self._reload_profiles()
            self.statusBar().showMessage(
                f"FTP aktualisiert: {current_ftp} W \u2192 {calculated_ftp} W", 8000,
            )

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key in {Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right}:
                if self.engine.state in {"running", "paused", "waiting_for_pedal"}:
                    if key == Qt.Key_Up:
                        self._apply_training_snapshot(self.engine.adjust_target(5))
                        return True
                    if key == Qt.Key_Down:
                        self._apply_training_snapshot(self.engine.adjust_target(-5))
                        return True
                    if key == Qt.Key_Right:
                        self._apply_training_snapshot(self.engine.skip_block())
                        return True
                    if key == Qt.Key_Left:
                        self._apply_training_snapshot(self.engine.previous_block())
                        return True
        return super().eventFilter(obj, event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._auto_connect_started:
            self._auto_connect_started = True
            QTimer.singleShot(100, self._auto_connect_trainer)
            QTimer.singleShot(200, self._auto_connect_hr)

    def _exit_training(self) -> None:
        if self.engine.state in {"running", "paused", "waiting_for_pedal"}:
            snapshot = self.engine.stop()
            self._apply_training_snapshot(snapshot)
            self._persist_pending_session()
        self.stack.setCurrentWidget(self.library_page)
        self._show_training_header(False)

    def _auto_connect_trainer(self) -> None:
        if self._shutting_down:
            return
        if self._auto_connect_in_progress or self.trainer.bluetooth.connected:
            return
        if not self.trainer.bluetooth.available:
            self._auto_connect_status = "error"
            self._refresh_status_labels()
            return
        self._auto_connect_in_progress = True
        self._auto_connect_status = "searching"
        self._refresh_status_labels()
        threading.Thread(target=self._run_auto_connect_worker, daemon=True).start()

    def _run_auto_connect_worker(self) -> None:
        result = AutoConnectResult(state="idle", devices=[])
        if self._shutting_down:
            return
        if not self.trainer.bluetooth.available:
            result.state = "error"
            result.error_message = "Bluetooth nicht verfügbar"
            if not self._shutting_down:
                self._signals.auto_connect_finished.emit(result)
            return

        try:
            devices = self.trainer.scan_devices()
            result.devices = devices
            preferred = self.trainer.pick_preferred_device(devices)
            if preferred is None:
                result.state = "not_found"
            else:
                result.device_name = preferred.name
                self.trainer.connect_device(preferred.identifier, preferred.name)
                result.state = "connected" if self.trainer.bluetooth.connected else "error"
                if result.state == "error":
                    result.error_message = f"Verbindung zu {preferred.name} fehlgeschlagen"
        except Exception as exc:
            logger.warning("Automatische Trainer-Verbindung fehlgeschlagen: %s", exc)
            result.state = "error"
            result.error_message = str(exc)

        if not self._shutting_down:
            self._signals.auto_connect_finished.emit(result)

    def _handle_auto_connect_finished(self, result: AutoConnectResult) -> None:
        if self._shutting_down:
            return
        self._known_trainer_devices = result.devices
        self._auto_connect_in_progress = False
        self._auto_connect_status = result.state
        self._refresh_status_labels()

        if result.state == "connected" and result.device_name:
            self.statusBar().showMessage(f"Verbunden mit {result.device_name}", 5000)
        elif result.state == "error" and result.error_message:
            self.statusBar().showMessage(f"Trainer: {result.error_message}", 5000)
        elif result.state == "not_found":
            self.statusBar().showMessage("Kein Wahoo/KICKR gefunden", 3000)

    def _auto_connect_hr(self) -> None:
        if self._shutting_down:
            return
        if self._hr_auto_connect_in_progress or self.hr_monitor.connected:
            return
        if not self.hr_monitor.available:
            self._hr_auto_connect_status = "error"
            self._refresh_status_labels()
            return
        self._hr_auto_connect_in_progress = True
        self._hr_auto_connect_status = "searching"
        self._refresh_status_labels()
        threading.Thread(target=self._run_hr_connect_worker, daemon=True).start()

    def _run_hr_connect_worker(self) -> None:
        result = {"state": "idle", "device_name": None}
        if self._shutting_down:
            return
        try:
            devices = self.hr_monitor.scan_devices()
            if not devices:
                result["state"] = "not_found"
            else:
                chosen = devices[0]
                result["device_name"] = chosen.name
                self.hr_monitor.connect(chosen.identifier, chosen.name)
                result["state"] = "connected" if self.hr_monitor.connected else "error"
        except Exception as exc:
            logger.warning("Automatische HR-Verbindung fehlgeschlagen: %s", exc)
            result["state"] = "error"
        if not self._shutting_down:
            self._signals.hr_connect_finished.emit(result)

    def _handle_hr_connect_finished(self, result: dict) -> None:
        if self._shutting_down:
            return
        self._hr_auto_connect_in_progress = False
        self._hr_auto_connect_status = result["state"]
        self._refresh_status_labels()
        if result["state"] == "connected" and result.get("device_name"):
            self.statusBar().showMessage(f"HR verbunden: {result['device_name']}", 5000)

    def _finish_training(self) -> bool:
        if self.engine.state in {"running", "paused", "waiting_for_pedal"}:
            self.engine.stop()
        return self._persist_pending_session(force=True, show_feedback=False)

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._finish_training():
            QMessageBox.critical(self, "Session nicht gespeichert",
                                 "Die Session konnte nicht gespeichert werden. Bitte Speicherplatz und "
                                 "Dateizugriff prüfen und das Fenster anschließend erneut schließen.")
            event.ignore()
            return
        self.shutdown()
        event.accept()

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self.timer.stop()
        self.reconnect_timer.stop()
        self.hr_reconnect_timer.stop()
        self._finish_training()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        try:
            self.trainer.close()
        finally:
            self.hr_monitor.close()

    def _active_ftp_watts(self, workout: WorkoutTemplate | None = None) -> int:
        if self.current_profile is not None and self.current_profile.ftp_watts > 0:
            return self.current_profile.ftp_watts
        workout_template = workout or self.current_workout_template
        if workout_template is not None and workout_template.ftp_reference:
            return workout_template.ftp_reference
        return self.config.default_ftp

    def _resolve_workout_for_profile(self, workout: WorkoutTemplate) -> ResolvedWorkout:
        return workout.resolve(self._active_ftp_watts(workout), default_ftp_watts=DEFAULT_FTP_WATTS)
