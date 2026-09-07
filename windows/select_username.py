from PyQt6 import uic
from PyQt6.QtWidgets import QDialog, QMessageBox, QInputDialog
import os

# 

class SelectUsernameWindow(QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/select_username.ui", self)

        self.username = None
        self.main_window = None

        self.saveBtn.clicked.connect(self.save_username)
        self.linkBtn.clicked.connect(self.show_link)


    def load_saved_username(self):
        if os.path.exists("username.txt"):
            with open("username.txt", "r", encoding="utf-8") as f:
                self.username = f.read().strip()

            if self.username:
                self.txtUsername.setText(self.username)
                self.txtUsername.setEnabled(False)
                self.saveBtn.setEnabled(False)

                # 🔥 این خط خیلی مهمه
                if self.main_window:
                    self.main_window.username = self.username


    def save_username(self):
        username = self.txtUsername.text().strip()

        if username == "":
            QMessageBox.warning(self, "خطا", "نام کاربری نمی‌تواند خالی باشد.")
            return

        self.username = username

        # ذخیره در فایل
        with open("username.txt", "w", encoding="utf-8") as f:
            f.write(username)

        # جلوگیری از وارد کردن دوباره
        self.txtUsername.setEnabled(False)
        self.saveBtn.setEnabled(False)

        QMessageBox.information(self, "ذخیره شد", "نام کاربری ذخیره شد.")


    def show_link(self):
        if not self.username:
            QMessageBox.warning(self, "خطا", "ابتدا نام کاربری را ذخیره کنید.")
            return

        # 🔥 مسیر جدید سایت — هماهنگ با کد جدید HTML/JS
        link = f"https://gamenet-web.onrender.com/?user={self.username}"

        QInputDialog.getText(
            self,
            "لینک سایت",
            "لینک مخصوص شما:",
            text=link
        )