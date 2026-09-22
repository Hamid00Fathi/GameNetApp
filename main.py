from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtGui import QIcon
import sys
import os
import requests
from datetime import datetime

from windows.main_window import MainWindow
from database import create_tables
from windows.theme import apply_dark_theme

API_BASE = "https://gamenet-server-mongo-production.up.railway.app"


# ---------------------------------------------------------
# لاگین واقعی (فقط چک یوزرنیم + پسورد)
# ---------------------------------------------------------
def check_login(username, password):
    try:
        r = requests.post(
            f"{API_BASE}/login",
            json={"username": username, "password": password},
            timeout=5
        )

        if r.status_code == 200:
            return True
        return False

    except:
        return False


# ---------------------------------------------------------
# چک اشتراک آنلاین
# ---------------------------------------------------------
def check_subscription(username):
    try:
        r = requests.get(f"{API_BASE}/subscription/{username}", timeout=5)
        data = r.json()

        expire_date = data.get("expireDate")
        active = data.get("active")

        if expire_date is None:
            return "inactive", None, 0

        expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")
        today = datetime.now()
        days_left = (expire_dt - today).days + 1

        if active:
            return "active", expire_date, days_left
        return "inactive", expire_date, days_left

    except:
        return "error", None, None


# ---------------------------------------------------------
# چک لایسنس آفلاین
# ---------------------------------------------------------
def check_license_status(username):
    try:
        r = requests.get(f"{API_BASE}/license/status/{username}", timeout=5)
        data = r.json()

        if not data.get("ok"):
            return False

        if data.get("licenseType") == "offline" and data.get("licenseActive"):
            return True

        return False

    except:
        return True  # آفلاین مود نباید به اینترنت وابسته باشد


# ---------------------------------------------------------
# پنجره انتخاب حالت ورود
# ---------------------------------------------------------
class LoginModeWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("انتخاب حالت ورود")
        self.resize(300, 150)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("لطفاً حالت ورود را انتخاب کنید:"))

        btn_online = QPushButton("ورود با اشتراک (آنلاین)")
        btn_offline = QPushButton("ورود با لایسنس (آفلاین)")

        btn_online.clicked.connect(lambda: self.done(1))
        btn_offline.clicked.connect(lambda: self.done(2))

        layout.addWidget(btn_online)
        layout.addWidget(btn_offline)


# ---------------------------------------------------------
# پنجره ورود آنلاین
# ---------------------------------------------------------
class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ورود آنلاین")
        self.resize(300, 150)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("نام کاربری:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)

        layout.addWidget(QLabel("رمز ورود:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        btn = QPushButton("ورود")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_data(self):
        return self.username_input.text().strip(), self.password_input.text().strip()


# ---------------------------------------------------------
# پنجره ورود آفلاین
# ---------------------------------------------------------
class LicenseWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ورود با لایسنس (آفلاین)")
        self.resize(300, 200)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("نام کاربری:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)

        layout.addWidget(QLabel("رمز ورود:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        layout.addWidget(QLabel("کلید لایسنس:"))
        self.license_input = QLineEdit()
        layout.addWidget(self.license_input)

        btn = QPushButton("فعال‌سازی")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_data(self):
        return (
            self.username_input.text().strip(),
            self.password_input.text().strip(),
            self.license_input.text().strip()
        )


# ---------------------------------------------------------
# اجرای اصلی برنامه
# ---------------------------------------------------------

create_tables()
app = QApplication(sys.argv)
app.setStyleSheet(apply_dark_theme())
app.setWindowIcon(QIcon("icon.ico"))

window = None
username = None
password = None


# ---------------------------------------------------------
# ۱) ورود اتوماتیک آفلاین
# ---------------------------------------------------------
if os.path.exists("license.key") and os.path.exists("credentials.txt"):
    with open("credentials.txt", "r") as f:
        lines = f.read().splitlines()
        for line in lines:
            if line.startswith("username="):
                username = line.split("=")[1].strip()
            if line.startswith("password="):
                password = line.split("=")[1].strip()

    if username and password and check_license_status(username):
        window = MainWindow(mode="offline", username=username)
        window.gamenet_password = password
        window.lblSubscriptionInfo.setText("حالت آفلاین فعال است")
        window.show()
        sys.exit(app.exec())


# ---------------------------------------------------------
# ۲) ورود اتوماتیک آنلاین
# ---------------------------------------------------------
if window is None and os.path.exists("credentials.txt"):
    with open("credentials.txt", "r") as f:
        lines = f.read().splitlines()
        for line in lines:
            if line.startswith("username="):
                username = line.split("=")[1].strip()
            if line.startswith("password="):
                password = line.split("=")[1].strip()

    if username and password and check_login(username, password):
        status, expire_date, days_left = check_subscription(username)

        if status == "active":
            window = MainWindow(mode="online", username=username)
            window.gamenet_password = password
            window.lblSubscriptionInfo.setText(f"مانده اشتراک: {days_left} روز | پایان: {expire_date}")
            window.show()
            sys.exit(app.exec())


# ---------------------------------------------------------
# ۳) انتخاب حالت ورود
# ---------------------------------------------------------
mode_window = LoginModeWindow()
choice = mode_window.exec()

if choice != 1 and choice != 2:
    sys.exit()


# ---------------------------------------------------------
# حالت آنلاین
# ---------------------------------------------------------
if choice == 1:
    login = LoginWindow()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit()

    username, password = login.get_data()

    if not check_login(username, password):
        QMessageBox.critical(None, "خطا", "نام کاربری یا رمز ورود اشتباه است.")
        sys.exit()

    status, expire_date, days_left = check_subscription(username)

    if status == "error":
        QMessageBox.critical(None, "خطا", "اتصال اینترنت برقرار نیست.")
        sys.exit()

    if status != "active":
        QMessageBox.critical(None, "خطا", "اشتراک فعال نیست.")
        sys.exit()

    with open("credentials.txt", "w") as f:
        f.write(f"username={username}\n")
        f.write(f"password={password}\n")

    window = MainWindow(mode="online", username=username)
    window.gamenet_password = password
    window.lblSubscriptionInfo.setText(f"مانده اشتراک: {days_left} روز | پایان: {expire_date}")
    window.show()
    sys.exit(app.exec())


# ---------------------------------------------------------
# حالت آفلاین
# ---------------------------------------------------------
if choice == 2:
    lic_win = LicenseWindow()
    if lic_win.exec() != QDialog.DialogCode.Accepted:
        sys.exit()

    username, password, license_key = lic_win.get_data()

    # اگر credentials.txt وجود دارد → باید یوزرنیم و پسورد یکی باشد
    if os.path.exists("credentials.txt"):
        saved_user = None
        saved_pass = None

        with open("credentials.txt", "r") as f:
            lines = f.read().splitlines()
            for line in lines:
                if line.startswith("username="):
                    saved_user = line.split("=")[1].strip()
                if line.startswith("password="):
                    saved_pass = line.split("=")[1].strip()

        if username != saved_user or password != saved_pass:
            QMessageBox.critical(None, "خطا", "نام کاربری یا رمز ورود اشتباه است.")
            sys.exit()

    # چک لایسنس از سرور
    try:
        r = requests.post(
            f"{API_BASE}/license/verify",
            json={"username": username, "key": license_key},
            timeout=5
        )
        data = r.json()

        if not data.get("valid"):
            QMessageBox.critical(None, "خطا", "لایسنس معتبر نیست.")
            sys.exit()

        with open("license.key", "w") as f:
            f.write(license_key)

        with open("credentials.txt", "w") as f:
            f.write(f"username={username}\n")
            f.write(f"password={password}\n")

        window = MainWindow(mode="offline", username=username)
        window.gamenet_password = password
        window.lblSubscriptionInfo.setText("حالت آفلاین فعال است")
        window.show()
        sys.exit(app.exec())

    except:
        if os.path.exists("license.key") and os.path.exists("credentials.txt"):
            window = MainWindow(mode="offline", username=username)
            window.gamenet_password = password
            window.lblSubscriptionInfo.setText("حالت آفلاین فعال است (بدون اینترنت)")
            window.show()
            sys.exit(app.exec())

        QMessageBox.critical(None, "خطا", "اتصال اینترنت برقرار نیست و فایل لایسنس موجود نیست.")
        sys.exit()