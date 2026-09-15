from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QMessageBox, QInputDialog
import os

class SelectUsernameWindow(QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/select_username.ui", self)

        self.username = None
        self.password = None
        self.main_window = None

        self.saveBtn.clicked.connect(self.save_credentials)
        self.linkBtn.clicked.connect(self.show_link)

        self.load_saved_credentials()

    # -----------------------------
    # بارگذاری یوزرنیم + پسورد از فایل
    # -----------------------------
    def load_saved_credentials(self):
        if os.path.exists("credentials.txt"):
            with open("credentials.txt", "r", encoding="utf-8") as f:
                lines = f.read().split("\n")
                if len(lines) >= 2:
                    self.username = lines[0].split("=")[1].strip()
                    self.password = lines[1].split("=")[1].strip()

            if self.username:
                self.txtUsername.setText(self.username)
                self.txtUsername.setEnabled(False)

            if self.password:
                self.txtPassword.setText(self.password)
                self.txtPassword.setEnabled(False)

            if self.username and self.password:
                self.saveBtn.setEnabled(False)

                # انتقال به MainWindow
                if self.main_window:
                    self.main_window.username = self.username
                    self.main_window.gamenet_password = self.password

    # -----------------------------
    # ذخیره یوزرنیم + پسورد
    # -----------------------------
    def save_credentials(self):
        username = self.txtUsername.text().strip()
        password = self.txtPassword.text().strip()

        if username == "" or password == "":
            QMessageBox.warning(self, "خطا", "یوزرنیم و پسورد باید وارد شوند.")
            return

        self.username = username
        self.password = password

        # ذخیره در فایل
        with open("credentials.txt", "w", encoding="utf-8") as f:
            f.write("username=" + username + "\n" + "password=" + password)

        # جلوگیری از تغییر دوباره
        self.txtUsername.setEnabled(False)
        self.txtPassword.setEnabled(False)
        self.saveBtn.setEnabled(False)

        QMessageBox.information(self, "ذخیره شد", "یوزرنیم و پسورد ذخیره شدند.")

        # انتقال به MainWindow
        if self.main_window:
            self.main_window.username = self.username
            self.main_window.gamenet_password = self.password

    # -----------------------------
    # نمایش لینک سایت
    # -----------------------------
    def show_link(self):
        if not self.username:
            QMessageBox.warning(self, "خطا", "ابتدا یوزرنیم را ذخیره کنید.")
            return

        link = f"https://gamenet-web.onrender.com/login.html"

        QInputDialog.getText(
            self,
            "لینک سایت",
            "لینک مخصوص شما:",
            text=link
        )