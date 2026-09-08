import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton
    from cados.ui.dialogs import AccountStartDialog
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is required for UI tests")
class AccountDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_saved_account_chooser_never_contains_password_fields(self):
        dialog = AccountStartDialog([
            {"url": "https://cados.example", "email": "one@example.test", "token": "one"},
            {"url": "https://cados.example", "email": "two@example.test", "token": "two"},
        ])
        self.assertEqual(dialog.findChildren(QLineEdit), [])
        labels = [button.text() for button in dialog.findChildren(QPushButton)]
        self.assertTrue(any("one@example.test" in label for label in labels))
        self.assertTrue(any("Weiteres Konto hinzufügen" in label for label in labels))