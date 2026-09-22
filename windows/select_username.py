from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QMessageBox, QInputDialog
import os

class SelectUsernameWindow(QDialog):
    def __init__(self):
        super().__init__()
        import sys, os
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)

        uic.loadUi(os.path.join(base_path, "ui", "select_username.ui"), self)

        self.username = None
        self.password = None
        self.main_window = None

        self.linkBtn.clicked.connect(self.show_link)

        # فقط نمایش اطلاعاتی که MainWindow ست کرده
        self.load_credentials_from_main()

    def load_credentials_from_main(self):
        if self.main_window:
            self.username = self.main_window.username
            self.password = self.main_window.gamenet_password

            if self.username:
                self.txtUsername.setText(self.username)
                self.txtUsername.setEnabled(False)

            if self.password:
                self.txtPassword.setText(self.password)
                self.txtPassword.setEnabled(False)

    def show_link(self):
        if not self.username:
            QMessageBox.warning(self, "خطا", "یوزرنیم هنوز دریافت نشده.")
            return

        link = "https://gamenet-web.onrender.com/login.html"

        dlg = QInputDialog(self)
        dlg.setWindowTitle("لینک سایت")
        dlg.setLabelText("لینک مخصوص شما:")
        dlg.setTextValue(link)
        dlg.resize(400, 120)
        dlg.exec()