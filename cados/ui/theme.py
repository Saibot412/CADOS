from __future__ import annotations

from PySide6.QtWidgets import QApplication

LIGHT_STYLESHEET = """
/* ── Base ────────────────────────────────────────────── */
QWidget {
    background: transparent;
    color: #142033;
    font-family: "SF Pro Display", "SF Pro Text", "Segoe UI Variable", "Segoe UI", "Aptos";
    font-size: 13px;
}
QMainWindow, QWidget[appRoot="true"], QStackedWidget {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #f4f5f7,
        stop:0.5 #fbfbfc,
        stop:1 #f1f3f6);
}

/* ── Dialogs ────────────────────────────────────────── */
QDialog {
    background: #f8f9fb;
    border-radius: 16px;
}
QMessageBox {
    background: #f8f9fb;
}
QMessageBox QLabel {
    background: transparent;
    color: #142033;
    font-size: 13px;
}
QDialogButtonBox QPushButton {
    min-width: 80px;
}
QFormLayout {
    background: transparent;
}

/* ── Cards ───────────────────────────────────────────── */
QFrame[card="true"] {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid #e1e6ed;
    border-radius: 18px;
}
QFrame[card="true"][surface="toolbar"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(255, 255, 255, 0.84),
        stop:1 rgba(250, 251, 253, 0.90));
    border: 1px solid #e2e6ec;
}
QFrame[card="true"][surface="subtle"] {
    background: #f8fafc;
    border: 1px solid #e5e9ef;
}
QFrame[card="true"][surface="hero"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #e8eff8,
        stop:0.5 #e2ebf5,
        stop:1 #dce6f1);
    border: 1px solid #c8d6e5;
}
QFrame[card="true"][surface="metric"] {
    background: #ffffff;
    border: 1px solid #e4e8ee;
}
QFrame[card="true"][surface="focus"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #edf2f8,
        stop:1 #e5ecf4);
    border: 1px solid #d0dae8;
}
QDialog#accountLoginDialog, QDialog#accountStartDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #f8fbff,
        stop:0.55 #eef4fb,
        stop:1 #e8f0f8);
}
QFrame[card="true"][surface="login"] {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(183, 200, 219, 0.72);
    border-radius: 20px;
}

/* ── Status & Dividers ───────────────────────────────── */
QFrame[statusPill="true"] {
    background: rgba(255, 255, 255, 0.86);
    border: 1px solid #dde3ea;
    border-radius: 999px;
}
QFrame[divider="true"] {
    background: #e7ebf0;
    border: none;
    border-radius: 1px;
}
QFrame[dividerDark="true"] {
    background: rgba(0, 0, 0, 0.08);
    border: none;
    border-radius: 1px;
}

/* ── Labels ──────────────────────────────────────────── */
QLabel[dimmed="true"] {
    color: #6d7a8b;
}
QLabel[hero="true"] {
    font-size: 34px;
    font-weight: 700;
}
QLabel[metric="true"] {
    font-size: 36px;
    font-weight: 700;
}
QLabel[eyebrow="true"] {
    font-size: 11px;
    font-weight: 700;
    color: #7a90a7;
}
QLabel[toolbarMeta="true"] {
    color: #627284;
    font-size: 12px;
    font-weight: 600;
}
QLabel[statusTitle="true"] {
    color: #18263a;
    font-size: 12px;
    font-weight: 700;
}
QLabel[statusValue="true"] {
    color: #6d7b8c;
    font-size: 12px;
    font-weight: 600;
}
QLabel[focusTitle="true"] {
    color: #7a8ea5;
    font-size: 11px;
    font-weight: 700;
}
QLabel[focusValue="true"] {
    color: #15263c;
    font-size: 52px;
    font-weight: 700;
}
QLabel[focusDetail="true"] {
    color: #6d7b8c;
    font-size: 13px;
    font-weight: 600;
}
QLabel[cardTitle="true"] {
    color: #7a8ea5;
    font-size: 14px;
    font-weight: 700;
}
QLabel[cardValue="true"] {
    color: #15263c;
    font-size: 34px;
    font-weight: 700;
}
QLabel[cardDetail="true"] {
    color: #6d7b8c;
    font-size: 16px;
    font-weight: 600;
}
QLabel[blockValue="true"] {
    color: #15263c;
    font-size: 34px;
    font-weight: 700;
}
QLabel[sectionTitle="true"] {
    font-size: 16px;
    font-weight: 700;
    color: #18283d;
}
QLabel[brand="true"] {
    color: #102a43;
    font-size: 19px;
    font-weight: 800;
    letter-spacing: 1.5px;
}
QLabel[brandCaption="true"] {
    color: #6d8195;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.2px;
}
QLabel[pageLabel="true"] {
    color: #5e7389;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding-left: 12px;
    border-left: 1px solid #dce3ea;
}
QLabel[profileSummary="true"] {
    color: #38536d;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 4px 6px 10px;
}
QLabel[heroText="true"] {
    color: #18283d;
}
QLabel[heroDimmed="true"] {
    color: #7186a0;
}
QLabel[chip="default"] {
    background: #eef4fb;
    border: 1px solid #dbe6f0;
    border-radius: 999px;
    color: #33516e;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 10px;
}
QLabel[chip="hero"] {
    background: rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 999px;
    color: #3d5a80;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 10px;
}
QLabel[loginTitle="true"] {
    color: #102a43;
    font-size: 31px;
    font-weight: 700;
}
QLabel[loginSubtitle="true"] {
    color: #63788d;
    font-size: 13px;
}
QLabel[chooserBrand="true"] {
    color: #0a84ff;
    font-size: 20px;
    font-weight: 800;
    letter-spacing: 3px;
}

/* ── Buttons ─────────────────────────────────────────── */
QPushButton {
    background: rgba(255, 255, 255, 0.96);
    border: 1px solid #d7dce4;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 600;
    min-height: 18px;
}
QPushButton:hover {
    background: #ffffff;
    border-color: #c0c9d6;
}
QPushButton:pressed {
    background: #f0f2f5;
}
QPushButton:disabled {
    color: #95a1ae;
    border-color: #e2e7ed;
    background: #f5f7f9;
}
QPushButton[accent="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0a84ff,
        stop:1 #3696ff);
    border: none;
    color: #ffffff;
}
QPushButton[accent="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #0a78e5,
        stop:1 #2b8aee);
}
QPushButton[accent="true"]:disabled {
    background: rgba(10, 132, 255, 0.35);
    color: rgba(255, 255, 255, 0.6);
}
QPushButton[danger="true"] {
    background: #c63d4b;
    border: 1px solid #c63d4b;
    color: #ffffff;
}
QPushButton[danger="true"]:hover {
    background: #b43441;
}
QPushButton[ghost="true"] {
    background: rgba(0, 0, 0, 0.04);
    border: 1px solid rgba(0, 0, 0, 0.08);
    color: #18283d;
}
QPushButton[ghost="true"]:hover {
    background: rgba(0, 0, 0, 0.08);
}
QPushButton[soft="true"] {
    background: #f5f7fa;
    border: 1px solid #dfe4eb;
    color: #265eaa;
}
QPushButton[soft="true"]:hover {
    background: #ffffff;
}
QPushButton[soft="true"]:disabled {
    color: #a0b0c4;
    border-color: #e8ecf1;
    background: #f8f9fb;
}
QPushButton[softDanger="true"] {
    background: #fff3f4;
    border: 1px solid #ffd9de;
    color: #c63d4b;
}
QPushButton[softDanger="true"]:hover {
    background: #ffe8eb;
}
QPushButton[compact="true"] {
    border-radius: 11px;
    padding: 7px 12px;
    min-height: 14px;
}
QPushButton[modeToggle="true"] {
    color: #536b83;
    background: #f6f8fb;
    border-color: #dfe6ee;
}
QPushButton[modeToggle="true"]:checked {
    color: #ffffff;
    background: #1677d2;
    border-color: #1677d2;
}
QPushButton[accountCard="true"] {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid #d6e1ed;
    border-radius: 17px;
    color: #18324b;
    padding: 10px 18px;
    text-align: left;
    font-size: 14px;
    font-weight: 650;
}
QPushButton[accountCard="true"]:hover {
    background: #ffffff;
    border-color: #80b9f2;
}
QPushButton[link="true"] {
    background: transparent;
    border: none;
    color: #6d8195;
    padding: 5px;
    font-size: 12px;
}
QPushButton[link="true"]:hover {
    color: #0a84ff;
}

/* ── Inputs ──────────────────────────────────────────── */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #d8dee6;
    border-radius: 11px;
    padding: 7px 10px;
}
QComboBox {
    padding-right: 34px;
    min-height: 22px;
}
QComboBox[compact="true"] {
    border-radius: 10px;
    padding: 5px 9px;
    padding-right: 30px;
    min-height: 18px;
}
QComboBox[compact="true"]::drop-down {
    width: 26px;
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: 1px solid #e1e5eb;
    border-top-right-radius: 11px;
    border-bottom-right-radius: 11px;
    background: #f6f8fa;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #d8dee6;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #e2efff;
    selection-color: #10233a;
    outline: 0;
}
QComboBox QAbstractItemView::item {
    background: #ffffff;
    color: #142033;
    padding: 6px 10px;
    min-height: 20px;
    border-radius: 4px;
    margin: 1px 0px;
}
QComboBox QAbstractItemView::item:hover {
    background: #f0f4fa;
}
QComboBox QAbstractItemView::item:selected {
    background: #e2efff;
    color: #10233a;
}
QComboBox QWidget {
    background: #ffffff;
}
QComboBox QFrame {
    background: #ffffff;
    border: 1px solid #d8dee6;
    border-radius: 8px;
}

/* ── Tooltips ───────────────────────────────────────── */
QToolTip {
    background: #ffffff;
    color: #142033;
    border: 1px solid #dbe4ed;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ── Lists & Tables ──────────────────────────────────── */
QListWidget, QTableWidget {
    background: #fbfcfd;
    border: 1px solid #e1e6ec;
    border-radius: 16px;
    gridline-color: #e8edf2;
    alternate-background-color: #f6f8fb;
}
QListWidget::item {
    padding: 12px 14px;
    margin: 3px 0;
    border-radius: 10px;
    font-size: 16px;
    font-weight: 600;
}
QListWidget::item:hover {
    background: #eef5ff;
}
QListWidget::item:selected, QTableWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e3efff,
        stop:1 #d8e8ff);
    color: #10233a;
}
QHeaderView::section {
    background: transparent;
    border: none;
    border-bottom: 1px solid #e2e7ec;
    padding: 10px 8px;
    color: #728195;
    font-weight: 600;
}

/* ── Status Bar ──────────────────────────────────────── */
QStatusBar {
    background: #f8f9fb;
    border-top: 1px solid #e2e6eb;
    color: #6b7787;
}

/* ── Splitter & Scrollbars ───────────────────────────── */
QSplitter::handle {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 14px;
    margin: 6px 4px 6px 0;
}
QScrollBar::handle:vertical {
    background: #bccad7;
    min-height: 34px;
    border-radius: 7px;
}
QScrollBar::handle:vertical:hover {
    background: #9fb3c7;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 14px;
    margin: 0 6px 4px 6px;
}
QScrollBar::handle:horizontal {
    background: #bccad7;
    min-width: 34px;
    border-radius: 7px;
}
QScrollBar::handle:horizontal:hover {
    background: #9fb3c7;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
"""


def normalize_theme_mode(theme_mode: str | None) -> str:
    del theme_mode
    return "light"


def apply_theme(app: QApplication, theme_mode: str) -> str:
    normalized = normalize_theme_mode(theme_mode)
    app.setStyle("Fusion")
    app.setStyleSheet(LIGHT_STYLESHEET)
    return normalized
