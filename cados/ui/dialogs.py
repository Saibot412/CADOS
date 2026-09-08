from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator, QDoubleValidator
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from cados.models.profile import UserProfile, iso_now
from uuid import uuid4


class ProfileDialog(QDialog):
    def __init__(self, profile: UserProfile | None = None, parent=None, *, default_ftp: int = 250):
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Benutzerprofil")
        self.setModal(True)
        self.setFixedSize(380, 280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(form)

        self.name_edit = QLineEdit(profile.name if profile else "")
        self.name_edit.setPlaceholderText("Benutzername eingeben")

        self.ftp_edit = QLineEdit(str(profile.ftp if profile else default_ftp))
        self.ftp_edit.setPlaceholderText("z.B. 250")
        self.ftp_edit.setValidator(QIntValidator(100, 500))

        self.max_hr_edit = QLineEdit()
        if profile and profile.max_hr is not None:
            self.max_hr_edit.setText(str(profile.max_hr))
        self.max_hr_edit.setPlaceholderText("Optional, z.B. 190")
        self.max_hr_edit.setValidator(QIntValidator(100, 230))

        self.weight_edit = QLineEdit()
        if profile and profile.weight_kg is not None:
            self.weight_edit.setText(str(profile.weight_kg))
        self.weight_edit.setPlaceholderText("Optional, z.B. 75.0")
        self.weight_edit.setValidator(QDoubleValidator(0.0, 200.0, 1))

        form.addRow("Name", self.name_edit)
        form.addRow("FTP (W)", self.ftp_edit)
        form.addRow("Max HF (bpm)", self.max_hr_edit)
        form.addRow("Gewicht (kg)", self.weight_edit)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Fehlender Name", "Bitte einen Namen eingeben.")
            return
        ftp_text = self.ftp_edit.text().strip()
        if not ftp_text or not ftp_text.isdigit() or not (100 <= int(ftp_text) <= 500):
            QMessageBox.warning(self, "Ungültiger FTP", "FTP muss zwischen 100 und 500 W liegen.")
            return
        self.accept()

    def build_profile(self) -> UserProfile:
        now = iso_now()
        ftp = int(self.ftp_edit.text().strip())
        weight_text = self.weight_edit.text().strip()
        weight = float(weight_text) if weight_text else None
        if weight is not None and weight <= 0:
            weight = None
        max_hr_text = self.max_hr_edit.text().strip()
        max_hr = int(max_hr_text) if max_hr_text else None
        if max_hr is not None and max_hr <= 0:
            max_hr = None
        return UserProfile(
            id=self.profile.id if self.profile else str(uuid4()),
            name=self.name_edit.text().strip(),
            ftp=ftp,
            weight_kg=weight,
            max_hr=max_hr,
            created_at=self.profile.created_at if self.profile else now,
            updated_at=now,
        )


class AccountLoginDialog(QDialog):
    def __init__(self, url, parent=None, *, email=""):
        super().__init__(parent)
        self.setWindowTitle("Bei CADOS anmelden")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        info = QLabel("Melde dich mit deinem Web-Konto an. Vorhandene lokale Profile und Trainings werden diesem Konto zugeordnet.")
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self.url = QLineEdit(url or "https://cados.saibot.at")
        self.email = QLineEdit(email)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("Server", self.url)
        form.addRow("E-Mail", self.email)
        form.addRow("Passwort", self.password)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Anmelden")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return self.url.text().strip().rstrip("/"), self.email.text().strip(), self.password.text()


class AccountStartDialog(QDialog):
    """Select a previously used account before asking for its password again."""

    def __init__(self, accounts: list[dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("CADOS starten")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        info = QLabel("Mit welchem Konto möchtest du CADOS verwenden?")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.accounts = accounts
        self.account = QComboBox()
        for item in accounts:
            self.account.addItem(item["email"], item)
        self.account.addItem("Anderes Konto", None)
        layout.addWidget(self.account)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Weiter zur Anmeldung")
        buttons.button(QDialogButtonBox.Cancel).setText("Ohne Konto starten")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_account(self) -> dict[str, str]:
        return self.account.currentData() or {"url": "https://cados.saibot.at", "email": ""}


class FTPResultDialog(QDialog):
    """Shows FTP test results and lets the user accept or keep the old value."""

    def __init__(self, current_ftp: int, calculated_ftp: int, best_1min: int, parent=None):
        super().__init__(parent)
        self.calculated_ftp = calculated_ftp
        self.setWindowTitle("FTP Test Ergebnis")
        self.setModal(True)
        self.setFixedSize(420, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        title = QLabel("FTP Test abgeschlossen")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #18283d;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        detail = QLabel(f"Beste 1-Minuten-Leistung: {best_1min} W")
        detail.setStyleSheet("font-size: 13px; color: #6d7a8b; font-weight: 600;")
        detail.setAlignment(Qt.AlignCenter)
        layout.addWidget(detail)

        # Side-by-side comparison
        compare_row = QHBoxLayout()
        compare_row.setSpacing(16)

        current_card = self._build_ftp_card("AKTUELLER FTP", f"{current_ftp} W", "#6d7a8b")
        new_card = self._build_ftp_card("NEUER FTP (75% Best 1min)", f"{calculated_ftp} W", "#0a84ff")
        compare_row.addWidget(current_card, 1)
        compare_row.addWidget(new_card, 1)
        layout.addLayout(compare_row)

        layout.addStretch(1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        keep_btn = QPushButton("Beibehalten")
        keep_btn.setProperty("soft", True)
        keep_btn.clicked.connect(self.reject)
        accept_btn = QPushButton(f"FTP auf {calculated_ftp} W setzen")
        accept_btn.setProperty("accent", True)
        accept_btn.clicked.connect(self.accept)
        btn_row.addWidget(keep_btn, 1)
        btn_row.addWidget(accept_btn, 1)
        layout.addLayout(btn_row)

    @staticmethod
    def _build_ftp_card(title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setProperty("card", True)
        card.setProperty("surface", "metric")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 10px; font-weight: 700; color: #7a90a7;")
        title_label.setAlignment(Qt.AlignCenter)
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 32px; font-weight: 700; color: {color};")
        value_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card
