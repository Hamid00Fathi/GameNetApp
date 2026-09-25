from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QMessageBox, QInputDialog
import os ,sys

class SelectUsernameWindow(QDialog):
    def __init__(self):
        super().__init__()

        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(__file__))

        uic.loadUi(os.path.join(base_path, "ui", "select_username.ui"), self)

        # مقدار اولیه امن
        self.username = ""
        self.password = ""

        self.linkBtn.clicked.connect(self.show_link)

        # اگر فایل وجود دارد، بخوان
        if os.path.exists("credentials.txt"):
            with open("credentials.txt", "r") as f:
                lines = f.read().splitlines()
                for line in lines:
                    if line.startswith("username="):
                        self.username = line.split("=")[1].strip()
                    if line.startswith("password="):
                        self.password = line.split("=")[1].strip()

        # مقداردهی امن
        self.load_credentials_from_main(self.username , self.password)

    def load_credentials_from_main(self, user , pas):
        # اگر یوزرنیم معتبر است
        if user:
            self.txtUsername.setText(user)
            self.txtUsername.setEnabled(False)

        # اگر پسورد معتبر است
        if pas:
            self.txtPassword.setText(pas)
            self.txtPassword.setEnabled(False)

    def show_link(self):
        # اگر یوزرنیم نداریم
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