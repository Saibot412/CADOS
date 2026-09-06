from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from cados.core.hr_zones import HR_ZONES
from cados.core.zones import POWER_ZONES
from cados.ui.widgets import WorkoutTimelineWidget

from cados.ui.library_widgets import _NoScrollComboBox, _WorkoutListDelegate


class MainWindowView(QMainWindow):
    """Window layout and widget construction; behavior lives in MainWindow."""

    def _fit_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = min(1460, avail.width() - 40)
            h = min(920, avail.height() - 40)
            self.resize(w, h)
            # Centre on screen
            self.move(
                avail.x() + (avail.width() - w) // 2,
                avail.y() + (avail.height() - h) // 2,
            )
        else:
            self.resize(1460, 920)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setProperty("appRoot", True)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("topHeader")
        header.setProperty("card", True)
        header.setProperty("surface", "toolbar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        self.brand_logo_label = QLabel("Cados")
        self.brand_logo_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.brand_logo_label.setProperty("sectionTitle", True)

        self.profile_combo = _NoScrollComboBox()
        self.profile_combo.setFixedWidth(200)
        self.profile_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.new_profile_button = QPushButton("Neuer Benutzer")
        self.new_profile_button.setProperty("soft", True)
        self.edit_profile_button = QPushButton("Bearbeiten")
        self.edit_profile_button.setProperty("soft", True)

        for control in (
            self.profile_combo,
            self.new_profile_button,
            self.edit_profile_button,
        ):
            control.setProperty("compact", True)

        profile_label = QLabel("Benutzer")
        profile_label.setProperty("eyebrow", True)

        profile_row = QHBoxLayout()
        profile_row.setContentsMargins(0, 0, 0, 0)
        profile_row.setSpacing(8)
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.profile_combo)
        profile_row.addWidget(self.new_profile_button)
        profile_row.addWidget(self.edit_profile_button)

        profile_container = QWidget()
        profile_container.setLayout(profile_row)

        self.trainer_status_pill = QFrame()
        self.trainer_status_pill.setProperty("statusPill", True)
        self.trainer_status_pill.setFixedWidth(260)
        trainer_status_layout = QHBoxLayout(self.trainer_status_pill)
        trainer_status_layout.setContentsMargins(14, 7, 14, 7)
        trainer_status_layout.setSpacing(10)

        self.trainer_status_dot = QLabel()
        self.trainer_status_dot.setFixedSize(10, 10)
        self.trainer_status_title_label = QLabel("Trainer")
        self.trainer_status_title_label.setProperty("statusTitle", True)
        self.trainer_status_value_label = QLabel("Suche Wahoo...")
        self.trainer_status_value_label.setProperty("statusValue", True)
        self.trainer_status_value_label.setMinimumWidth(0)

        trainer_status_layout.addWidget(self.trainer_status_dot)
        trainer_status_layout.addWidget(self.trainer_status_title_label)
        trainer_status_layout.addWidget(self.trainer_status_value_label, 1)

        # Training state pill (visible only during training)
        self.training_state_pill = QFrame()
        self.training_state_pill.setProperty("statusPill", True)
        self.training_state_pill.setMaximumWidth(180)
        training_state_layout = QHBoxLayout(self.training_state_pill)
        training_state_layout.setContentsMargins(14, 7, 14, 7)
        training_state_layout.setSpacing(10)
        self.training_state_dot = QLabel()
        self.training_state_dot.setFixedSize(10, 10)
        self.training_state_value_label = QLabel("Bereit")
        self.training_state_value_label.setProperty("statusValue", True)
        self.training_state_value_label.setMinimumWidth(0)
        training_state_layout.addWidget(self.training_state_dot)
        training_state_layout.addWidget(self.training_state_value_label)
        self.training_state_pill.setVisible(False)

        self.training_exit_button = QPushButton("Beenden")
        self.training_exit_button.setProperty("softDanger", True)
        self.training_exit_button.setProperty("compact", True)
        self.training_exit_button.setVisible(False)

        # User label shown during training (replaces profile combo)
        self.training_user_label = QLabel("")
        self.training_user_label.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #18283d;"
        )
        self.training_user_label.setVisible(False)

        self.profile_container = profile_container

        # HR status pill
        self.hr_status_pill = QFrame()
        self.hr_status_pill.setProperty("statusPill", True)
        self.hr_status_pill.setFixedWidth(220)
        hr_status_layout = QHBoxLayout(self.hr_status_pill)
        hr_status_layout.setContentsMargins(14, 7, 14, 7)
        hr_status_layout.setSpacing(10)
        self.hr_status_dot = QLabel()
        self.hr_status_dot.setFixedSize(10, 10)
        self.hr_status_title_label = QLabel("HR")
        self.hr_status_title_label.setProperty("statusTitle", True)
        self.hr_status_value_label = QLabel("Suche...")
        self.hr_status_value_label.setProperty("statusValue", True)
        self.hr_status_value_label.setMinimumWidth(0)
        hr_status_layout.addWidget(self.hr_status_dot)
        hr_status_layout.addWidget(self.hr_status_title_label)
        hr_status_layout.addWidget(self.hr_status_value_label, 1)


        header_layout.addWidget(self.brand_logo_label, 0, Qt.AlignLeft)
        header_layout.addWidget(self.profile_container, 1)
        header_layout.addWidget(self.training_user_label, 1)
        header_layout.addStretch(1)
        header_layout.addWidget(self.training_state_pill, 0, Qt.AlignRight)
        header_layout.addWidget(self.hr_status_pill, 0, Qt.AlignRight)
        header_layout.addWidget(self.trainer_status_pill, 0, Qt.AlignRight)
        header_layout.addWidget(self.training_exit_button, 0, Qt.AlignRight)
        root_layout.addWidget(header)

        self.stack = QStackedWidget()
        self.library_page = self._build_library_page()
        self.training_page = self._build_training_page()
        self.stack.addWidget(self.library_page)
        self.stack.addWidget(self.training_page)
        root_layout.addWidget(self.stack, 1)

    def _load_brand_logo_pixmap(self) -> QPixmap | None:
        if not self.config.paths.logo_path.exists():
            return None
        pixmap = QPixmap(str(self.config.paths.logo_path))
        if pixmap.isNull():
            return None
        return pixmap.scaled(156, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        page.setProperty("page", True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(0)
        layout.addWidget(splitter, 1)

        left_card = QFrame()
        left_card.setProperty("card", True)
        left_card.setProperty("surface", "subtle")
        left_card.setFixedWidth(320)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        left_top = QHBoxLayout()
        left_top.addWidget(QLabel("Workouts"))
        left_top.addStretch(1)
        self.refresh_workouts_button = QPushButton("Aktualisieren")
        self.refresh_workouts_button.setProperty("soft", True)
        left_top.addWidget(self.refresh_workouts_button)
        left_layout.addLayout(left_top)

        library_actions = QHBoxLayout()
        library_actions.setSpacing(6)
        self.import_workout_button = QPushButton("Importieren")
        self.import_workout_button.setProperty("soft", True)
        self.sync_workouts_button = QPushButton("Synchronisieren")
        self.sync_workouts_button.setProperty("soft", True)
        self.library_settings_button = QPushButton("Anmelden")
        self.library_settings_button.setProperty("soft", True)
        library_actions.addWidget(self.import_workout_button)
        library_actions.addWidget(self.sync_workouts_button)
        library_actions.addWidget(self.library_settings_button)
        left_layout.addLayout(library_actions)

        self.workout_list = QListWidget()
        self.workout_list.setAlternatingRowColors(True)
        self.workout_list.setItemDelegate(_WorkoutListDelegate(self.workout_list))
        left_layout.addWidget(self.workout_list, 1)

        splitter.addWidget(left_card)

        preview_card = QFrame()
        preview_card.setProperty("card", True)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 14, 16, 14)
        preview_layout.setSpacing(6)

        self.preview_eyebrow_label = QLabel("WORKOUT PREVIEW")
        self.preview_eyebrow_label.setProperty("eyebrow", True)

        preview_top = QHBoxLayout()
        preview_top.setSpacing(8)
        preview_title_layout = QVBoxLayout()
        preview_title_layout.setContentsMargins(0, 0, 0, 0)
        preview_title_layout.setSpacing(2)
        preview_title_row = QHBoxLayout()
        preview_title_row.setContentsMargins(0, 0, 0, 0)
        preview_title_row.setSpacing(8)

        self.preview_name_label = QLabel("Kein Workout gewählt")
        self.preview_name_label.setStyleSheet("font-size: 24px; font-weight: 700; color: #18283d;")
        self.preview_name_label.setWordWrap(True)
        self.preview_duration_label = QLabel("-")
        self.preview_duration_label.setVisible(False)
        self.preview_duration_label.setStyleSheet(
            "background: #eef4fb; border: 1px solid #dbe6f0; border-radius: 999px; "
            "color: #33516e; font-size: 12px; font-weight: 700; padding: 4px 10px;"
        )
        preview_title_row.addWidget(self.preview_name_label, 1)
        preview_title_row.addWidget(self.preview_duration_label, 0, Qt.AlignVCenter)
        preview_title_layout.addLayout(preview_title_row)

        self.start_workout_button = QPushButton("Workout starten")
        self.start_workout_button.setProperty("accent", True)
        self.start_workout_button.setProperty("compact", True)
        self.start_workout_button.setFixedHeight(34)

        preview_top.addLayout(preview_title_layout, 1)
        preview_top.addWidget(self.start_workout_button)

        self.preview_description_label = QLabel("Wähle links ein Workout oder lade eine vergangene Session erneut.")
        self.preview_description_label.setWordWrap(True)
        self.preview_description_label.setProperty("dimmed", True)
        self.preview_description_label.setStyleSheet("font-size: 12px; color: #6d7a8b;")
        self.preview_guidance_label = QLabel("")
        self.preview_guidance_label.setWordWrap(True)
        self.preview_guidance_label.setTextFormat(Qt.RichText)
        self.preview_guidance_label.setVisible(False)
        self.preview_guidance_label.setStyleSheet("color: #35506d; font-size: 12px;")

        self.preview_timeline = WorkoutTimelineWidget()
        self.preview_timeline.set_variant("focus")
        self.preview_timeline.setMinimumHeight(136)
        self.preview_timeline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_zone_stats_card, self.preview_zone_rows, self.preview_hr_zone_labels = self._build_zone_summary_card("Zonenverteilung")
        self.block_table = QTableWidget(0, 4)
        self.block_table.setHorizontalHeaderLabels(["#", "Block", "Dauer", "Ziel"])
        self.block_table.verticalHeader().setVisible(False)
        self.block_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.block_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.block_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.block_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.block_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.block_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.block_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.block_table.setVisible(False)

        preview_layout.addWidget(self.preview_eyebrow_label)
        preview_layout.addLayout(preview_top)
        preview_layout.addWidget(self.preview_description_label)
        preview_layout.addWidget(self.preview_guidance_label)
        preview_layout.addWidget(self.preview_timeline)
        preview_layout.addWidget(self.preview_zone_stats_card)

        self.repeat_session_button = QPushButton("Erneut laden")
        self.repeat_session_button.setProperty("soft", True)
        self.repeat_session_button.setProperty("compact", True)
        self.repeat_session_button.setVisible(False)

        self.session_table = QTableWidget(0, 5)
        self.session_table.setHorizontalHeaderLabels(["Datum", "Workout", "Dauer", "Status", "Quelle"])
        self.session_table.verticalHeader().setVisible(False)
        self.session_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.session_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.session_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.session_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.session_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.session_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.session_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.session_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.session_table.setVisible(False)

        splitter.addWidget(preview_card)
        splitter.setSizes([320, 1040])
        splitter.handle(1).setEnabled(False)
        return page

    def _build_training_page(self) -> QWidget:
        page = QWidget()
        page.setProperty("page", True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Hero Power Card ─────────────────────────────────
        power_card = QFrame()
        power_card.setProperty("card", True)
        power_card.setProperty("surface", "metric")
        power_outer = QHBoxLayout(power_card)
        power_outer.setContentsMargins(14, 10, 14, 10)
        power_outer.setSpacing(0)

        current_col = QVBoxLayout()
        current_col.setSpacing(2)
        current_title = QLabel("AKTUELL")
        current_title.setProperty("cardTitle", True)
        self.current_watts_value = QLabel("0 W")
        self.current_watts_value.setStyleSheet("font-size: 36px; font-weight: 700; color: #162840;")
        self.current_watts_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.current_watts_value.setMinimumWidth(0)
        self.current_watts_detail_label = QLabel("Live vom Trainer")
        self.current_watts_detail_label.setProperty("cardDetail", True)
        current_col.addWidget(current_title)
        current_col.addWidget(self.current_watts_value)
        current_col.addWidget(self.current_watts_detail_label)

        power_divider = QFrame()
        power_divider.setProperty("divider", True)
        power_divider.setFixedWidth(1)
        power_divider.setFixedHeight(64)

        target_col = QVBoxLayout()
        target_col.setSpacing(2)
        target_content_row = QHBoxLayout()
        target_content_row.setSpacing(12)
        target_info_col = QVBoxLayout()
        target_info_col.setSpacing(2)
        target_title = QLabel("ZIEL")
        target_title.setProperty("cardTitle", True)
        target_info_col.addWidget(target_title)

        self.target_watts_value = QLabel("0 W")
        self.target_watts_value.setStyleSheet("font-size: 36px; font-weight: 700; color: #6d7a8b;")
        self.target_watts_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.target_watts_value.setMinimumWidth(0)
        target_info_col.addWidget(self.target_watts_value)

        self.target_pct_detail_label = QLabel("")
        self.target_pct_detail_label.setProperty("cardDetail", True)
        target_info_col.addWidget(self.target_pct_detail_label)

        target_controls_col = QVBoxLayout()
        target_controls_col.setContentsMargins(0, 0, 0, 0)
        target_controls_col.setSpacing(6)
        control_width = 112
        control_height = 32
        self.plus_button = QPushButton("+5 W")
        self.plus_button.setProperty("soft", True)
        self.plus_button.setProperty("compact", True)
        self.plus_button.setFixedSize(control_width, control_height)
        self.plus_button.setStyleSheet("font-size: 13px; font-weight: 600; padding: 4px 14px; min-height: 0;")
        self.minus_button = QPushButton("-5 W")
        self.minus_button.setProperty("soft", True)
        self.minus_button.setProperty("compact", True)
        self.minus_button.setFixedSize(control_width, control_height)
        self.minus_button.setStyleSheet("font-size: 13px; font-weight: 600; padding: 4px 14px; min-height: 0;")
        self.training_adjustment_label = QLabel("Bias +0 W")
        self.training_adjustment_label.setAlignment(Qt.AlignCenter)
        self.training_adjustment_label.setFixedSize(control_width, control_height)
        self.training_adjustment_label.setStyleSheet(
            "background: #f5f7fa; "
            "border: 1px solid #dfe4eb; "
            "border-radius: 11px; "
            "color: #265eaa; "
            "font-size: 13px; "
            "font-weight: 600; "
            "padding: 4px 14px;"
        )
        target_controls_col.addWidget(self.plus_button, 0, Qt.AlignRight | Qt.AlignTop)
        target_controls_col.addStretch(1)
        target_controls_col.addWidget(self.training_adjustment_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        target_controls_col.addStretch(1)
        target_controls_col.addWidget(self.minus_button, 0, Qt.AlignRight | Qt.AlignBottom)

        target_content_row.addLayout(target_info_col, 1)
        target_content_row.addLayout(target_controls_col)
        target_col.addLayout(target_content_row)

        cadence_divider = QFrame()
        cadence_divider.setProperty("divider", True)
        cadence_divider.setFixedWidth(1)
        cadence_divider.setFixedHeight(64)

        current_cad_col = QVBoxLayout()
        current_cad_col.setSpacing(2)
        current_cad_title = QLabel("KADENZ")
        current_cad_title.setProperty("cardTitle", True)
        self.current_cadence_value = QLabel("0 rpm")
        self.current_cadence_value.setStyleSheet("font-size: 36px; font-weight: 700; color: #162840;")
        self.current_cadence_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.current_cadence_value.setMinimumWidth(0)
        self.current_cadence_detail_label = QLabel("Live vom Trainer")
        self.current_cadence_detail_label.setProperty("cardDetail", True)
        current_cad_col.addWidget(current_cad_title)
        current_cad_col.addWidget(self.current_cadence_value)
        current_cad_col.addWidget(self.current_cadence_detail_label)

        cad_divider2 = QFrame()
        cad_divider2.setProperty("divider", True)
        cad_divider2.setFixedWidth(1)
        cad_divider2.setFixedHeight(64)

        target_cad_col = QVBoxLayout()
        target_cad_col.setSpacing(2)
        target_cad_title = QLabel("ZIEL KADENZ")
        target_cad_title.setProperty("cardTitle", True)
        self.target_cadence_value = QLabel("- rpm")
        self.target_cadence_value.setStyleSheet("font-size: 36px; font-weight: 700; color: #6d7a8b;")
        self.target_cadence_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.target_cadence_value.setMinimumWidth(0)
        self.target_cadence_detail_label = QLabel("")
        self.target_cadence_detail_label.setProperty("cardDetail", True)
        target_cad_col.addWidget(target_cad_title)
        target_cad_col.addWidget(self.target_cadence_value)
        target_cad_col.addWidget(self.target_cadence_detail_label)

        power_outer.addLayout(current_col, 1)
        power_outer.addSpacing(10)
        power_outer.addWidget(power_divider, 0, Qt.AlignVCenter)
        power_outer.addSpacing(10)
        power_outer.addLayout(target_col, 1)
        power_outer.addSpacing(10)
        power_outer.addWidget(cadence_divider, 0, Qt.AlignVCenter)
        power_outer.addSpacing(10)
        power_outer.addLayout(current_cad_col, 1)
        power_outer.addSpacing(10)
        power_outer.addWidget(cad_divider2, 0, Qt.AlignVCenter)
        power_outer.addSpacing(10)
        power_outer.addLayout(target_cad_col, 1)
        layout.addWidget(power_card)

        # ── Stats Row (4 compact metric cards) ──────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(6)

        self.time_summary_value, self.time_summary_detail_label = self._build_stat_card(
            stats_row, "ZEIT", "00:00 / 00:00", "Gefahren / Im Workout verbleibend",
        )
        self.zone_value, self.zone_detail_label = self._build_stat_card(
            stats_row, "ZONE", "-", "",
        )
        self.block_value, self.block_detail_label = self._build_stat_card(
            stats_row, "BLOCK", "-", "Aktueller Block", value_property="blockValue",
        )
        self.hr_value, self.hr_detail_label = self._build_stat_card(
            stats_row, "HERZFREQUENZ", "- bpm", "",
        )
        layout.addLayout(stats_row)

        # ── Metrics Row (averages, NP, TSS, calories) ────
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(6)
        self.avg_watts_value, self.avg_watts_detail = self._build_compact_stat_card(
            metrics_row, "\u00D8 LEISTUNG", "0 W", "NP: 0 W",
        )
        self.avg_cadence_value, self.avg_cadence_detail = self._build_compact_stat_card(
            metrics_row, "\u00D8 KADENZ", "0 rpm", "",
        )
        self.avg_hr_value, self.avg_hr_detail = self._build_compact_stat_card(
            metrics_row, "\u00D8 HF", "- bpm", "",
        )
        self.tss_value, self.tss_detail = self._build_compact_stat_card(
            metrics_row, "TSS", "0", "IF: 0.00",
        )
        self.calories_value, self.calories_detail = self._build_compact_stat_card(
            metrics_row, "KCAL", "0", "",
        )
        layout.addLayout(metrics_row)

        # ── Timeline Card ───────────────────────────────────
        timeline_card = QFrame()
        timeline_card.setProperty("card", True)
        timeline_card.setProperty("surface", "focus")
        timeline_layout = QVBoxLayout(timeline_card)
        timeline_layout.setContentsMargins(18, 8, 18, 8)
        timeline_layout.setSpacing(4)

        timeline_header = QHBoxLayout()
        timeline_header.setSpacing(10)
        self.training_chart_title_label = QLabel("Workout Verlauf")
        self.training_chart_title_label.setProperty("sectionTitle", True)
        self.training_chart_title_label.setProperty("heroText", True)
        self.training_chart_context_label = QLabel("Kein Block")
        self.training_chart_context_label.setProperty("chip", "hero")
        self.prev_block_button = QPushButton("Vorheriger Block")
        self.prev_block_button.setProperty("soft", True)
        self.prev_block_button.setProperty("compact", True)
        self.skip_button = QPushButton("Nächster Block")
        self.skip_button.setProperty("soft", True)
        self.skip_button.setProperty("compact", True)
        self.training_timeline = WorkoutTimelineWidget()
        self.training_timeline.set_variant("focus")
        self.training_timeline.setMinimumHeight(80)
        self.training_timeline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        timeline_header.addWidget(self.training_chart_title_label)
        timeline_header.addStretch(1)
        timeline_header.addWidget(self.training_chart_context_label)
        timeline_header.addWidget(self.prev_block_button)
        timeline_header.addWidget(self.skip_button)
        timeline_layout.addLayout(timeline_header)
        timeline_layout.addWidget(self.training_timeline)
        layout.addWidget(timeline_card, 1)

        return page

    def _build_stat_card(
        self,
        row: QHBoxLayout,
        title: str,
        value: str,
        detail: str,
        value_property: str = "cardValue",
    ) -> tuple[QLabel, QLabel]:
        card = QFrame()
        card.setProperty("card", True)
        card.setProperty("surface", "metric")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setProperty("cardTitle", True)
        value_label = QLabel(value)
        value_label.setProperty(value_property, True)
        value_label.setMinimumWidth(0)
        detail_label = QLabel(detail)
        detail_label.setProperty("cardDetail", True)
        detail_label.setMinimumWidth(0)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card_layout.addWidget(detail_label)
        row.addWidget(card, 1)
        return value_label, detail_label

    def _build_compact_stat_card(
        self,
        row: QHBoxLayout,
        title: str,
        value: str,
        detail: str,
    ) -> tuple[QLabel, QLabel]:
        card = QFrame()
        card.setProperty("card", True)
        card.setProperty("surface", "metric")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setProperty("cardTitle", True)
        value_label = QLabel(value)
        value_label.setProperty("cardValue", True)
        value_label.setMinimumWidth(0)
        detail_label = QLabel(detail)
        detail_label.setProperty("cardDetail", True)
        detail_label.setMinimumWidth(0)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        card_layout.addWidget(detail_label)
        row.addWidget(card, 1)
        return value_label, detail_label

    def _metric_card(
        self,
        layout: QGridLayout,
        row: int,
        column: int,
        title: str,
        value: str,
        hero: bool = False,
        detail: str | None = None,
    ) -> QLabel | tuple[QLabel, QLabel]:
        card = QFrame()
        card.setProperty("card", True)
        card.setProperty("surface", "metric")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        title_label = QLabel(title)
        title_label.setProperty("eyebrow", True)
        value_label = QLabel(value)
        if hero:
            value_label.setProperty("metric", True)
        else:
            value_label.setStyleSheet("font-size: 24px; font-weight: 600;")
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        detail_label: QLabel | None = None
        if detail is not None:
            detail_label = QLabel(detail)
            detail_label.setProperty("dimmed", True)
            card_layout.addWidget(detail_label)
        layout.addWidget(card, row, column)
        if detail_label is not None:
            return value_label, detail_label
        return value_label

    def _build_zone_summary_card(self, title: str) -> tuple[QFrame, list[tuple[QLabel, QLabel, QLabel]], list[QLabel]]:
        card = QFrame()
        card.setProperty("card", True)
        card.setProperty("surface", "subtle")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        title_label = QLabel(title)
        title_label.setProperty("sectionTitle", True)
        outer.addWidget(title_label)

        # Single grid: cols 0-4 = Power Zones, col 5 = spacer, cols 6-8 = HR Zones
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        outer.addLayout(grid)

        # ── Power zone headers (cols 0-4) ──
        for col, hdr in [(1, "Leistungszone"), (2, "Bereich"), (3, "Zeit"), (4, "Anteil")]:
            h = QLabel(hdr)
            h.setProperty("dimmed", True)
            grid.addWidget(h, 0, col, alignment=Qt.AlignLeft | Qt.AlignVCenter)

        # ── Spacer column ──
        spacer = QLabel()
        spacer.setFixedWidth(20)
        grid.addWidget(spacer, 0, 5)

        # ── HR zone headers (cols 6-8) ──
        for col, hdr in [(7, "Herzfrequenzzone"), (8, "Bereich")]:
            h = QLabel(hdr)
            h.setProperty("dimmed", True)
            grid.addWidget(h, 0, col, alignment=Qt.AlignLeft | Qt.AlignVCenter)

        # ── Power zone rows ──
        power_rows: list[tuple[QLabel, QLabel, QLabel]] = []
        for ri, zone in enumerate(POWER_ZONES, start=1):
            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background: {zone.color}; border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 6px;"
            )
            zl = QLabel(zone.label)
            zl.setStyleSheet("font-weight: 600;")
            rl = QLabel("-")
            rl.setProperty("dimmed", True)
            tl = QLabel("00:00")
            pl = QLabel("0%")
            grid.addWidget(swatch, ri, 0, alignment=Qt.AlignCenter)
            grid.addWidget(zl, ri, 1)
            grid.addWidget(rl, ri, 2)
            grid.addWidget(tl, ri, 3, alignment=Qt.AlignLeft | Qt.AlignVCenter)
            grid.addWidget(pl, ri, 4, alignment=Qt.AlignLeft | Qt.AlignVCenter)
            power_rows.append((rl, tl, pl))

        # ── HR zone rows ──
        hr_range_labels: list[QLabel] = []
        for ri, zone in enumerate(HR_ZONES, start=1):
            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background: {zone.color}; border: 1px solid rgba(0, 0, 0, 0.08); border-radius: 6px;"
            )
            zl = QLabel(zone.label)
            zl.setStyleSheet("font-weight: 600;")
            rl = QLabel("-")
            rl.setProperty("dimmed", True)
            grid.addWidget(swatch, ri, 6, alignment=Qt.AlignCenter)
            grid.addWidget(zl, ri, 7)
            grid.addWidget(rl, ri, 8)
            hr_range_labels.append(rl)

        return card, power_rows, hr_range_labels
