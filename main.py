from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
import requests
import sys
import os
from datetime import datetime
import jdatetime
from windows.main_window import MainWindow
from database import create_tables
from windows.theme import apply_dark_theme
from PyQt6.QtGui import QIcon


API_BASE = "https://gamenet-server-mongo-production.up.railway.app"

mode = "online"
password = ""



# ---------------------------------------------------------
# چک لایسنس آفلاین
# ---------------------------------------------------------
def check_license_status(username):
    try:
        url = f"{API_BASE}/license/status/{username}"
        r = requests.get(url, timeout=5)
        data = r.json()

        if not data.get("ok"):
            return False

        if data.get("licenseType") == "offline" and data.get("licenseActive"):
            return True

        return False

    except:
        return True   # اگر اینترنت قطع باشد ولی فایل لایسنس هست → اجازه بده آفلاین اجرا شود


# ---------------------------------------------------------
# چک اشتراک آنلاین
# ---------------------------------------------------------
def check_subscription(username):
    try:
        url = f"{API_BASE}/subscription/{username}"
        r = requests.get(url, timeout=5)
        data = r.json()

        expire_date = data.get("expireDate")
        active = data.get("active")

        if expire_date is None:
            return "inactive", None, 0

        expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")

        # تاریخ امروز
        today = datetime.now()

        delta = expire_dt - today
        days_left = delta.days + 1

        if active:
            return "active", expire_date, days_left
        else:
            return "inactive", expire_date, days_left

    except:
        return "error", None, None

def check_login(username, password):
    try:
        url = f"{API_BASE}/login"
        r = requests.post(url, json={"username": username, "password": password}, timeout=5)
        data = r.json()
        return data.get("ok", False)
    except:
        return False
    
# ---------------------------------------------------------
# پنجره انتخاب حالت ورود
# ---------------------------------------------------------
class LoginModeWindow(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("انتخاب حالت ورود")
        self.resize(300, 150)

        layout = QVBoxLayout(self)

        lbl = QLabel("لطفاً حالت ورود را انتخاب کنید:")
        layout.addWidget(lbl)

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
# پنجره ورود لایسنس
# ---------------------------------------------------------
class LicenseWindow(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ورود با لایسنس")
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
username = None
password = ""
mode = "online"

# 1) اگر فایل لایسنس وجود داشت → مستقیم آفلاین
# 🔥 اولویت: اگر license.key وجود دارد → اول آفلاین مود
if os.path.exists("license.key"):
    mode = "offline"
    username = None
    password = ""

    # خواندن credentials اگر وجود داشت
    if os.path.exists("credentials.txt"):
        with open("credentials.txt", "r") as f:
            for line in f.read().splitlines():
                if line.startswith("username="):
                    username = line.split("=", 1)[1].strip()
                if line.startswith("password="):
                    password = line.split("=", 1)[1].strip()

    # 🔥 چک خراب بودن credentials
    if not username or not password:
        username = None
        password = None

    # 🔥 چک پسورد + چک لایسنس
    if username and password and check_login(username, password) and check_license_status(username):
        window = MainWindow(mode="offline", username=username)
        window.gamenet_password = password
        window.lblSubscriptionInfo.setText("حالت آفلاین فعال است")
        window.show()
        sys.exit(app.exec())

# 2) اگر credentials.txt وجود دارد → تلاش برای ورود آنلاین بدون سوال
if os.path.exists("credentials.txt"):
    with open("credentials.txt", "r") as f:
        for line in f.read().splitlines():
            if line.startswith("username="):
                username = line.split("=", 1)[1].strip()
            if line.startswith("password="):
                password = line.split("=", 1)[1].strip()

    # اگر فایل خراب بود (یوزرنیم یا پسورد خالی بود)
    if not username or not password:
        username = None
        password = None

    # حالا اگر فایل سالم بود، چک لاگین انجام بده
    if username:
        if not check_login(username, password):
            QMessageBox.critical(None, "خطا", "نام کاربری یا رمز اشتباه است")

            # فایل خراب را حذف کن
            try:
                os.remove("credentials.txt")
            except:
                pass

            sys.exit()

# ۳) اگر نه credentials معتبر بود، نه لایسنس → پنجره انتخاب حالت
mode_window = LoginModeWindow()
choice = mode_window.exec()

# ---------------------------------------------------------
# حالت آنلاین
# ---------------------------------------------------------
if choice == 1:
    login = LoginWindow()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit()

    username, password = login.get_data()

    status, expire_date, days_left = check_subscription(username)

    if not check_login(username, password):
        QMessageBox.critical(None, "خطا", "نام کاربری یا رمز اشتباه است")

    if status != "active":
        QMessageBox.critical(None, "خطا", "اشتراک فعال نیست.")
        sys.exit()

    # ذخیره credentials
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

    # 🔥 چک پسورد آفلاین با credentials.txt
    if os.path.exists("credentials.txt"):
        saved_user = None
        saved_pass = None

        with open("credentials.txt", "r") as f:
            for line in f.read().splitlines():
                if line.startswith("username="):
                    saved_user = line.split("=", 1)[1].strip()
                if line.startswith("password="):
                    saved_pass = line.split("=", 1)[1].strip()

        if password != saved_pass:
            QMessageBox.critical(None, "خطا", "رمز ورود اشتباه است.")
            sys.exit()

    # تلاش برای چک لایسنس از سرور
    try:
        r = requests.post(f"{API_BASE}/license/verify", json={"username": username, "key": license_key}, timeout=5)
        data = r.json()

        if not data.get("valid"):
            QMessageBox.critical(None, "خطا", "لایسنس معتبر نیست.")
            sys.exit()

        # ذخیره فایل لایسنس
        with open("license.key", "w") as f:
            f.write(license_key)

        # ذخیره credentials
        with open("credentials.txt", "w") as f:
            f.write(f"username={username}\n")
            f.write(f"password={password}\n")

        window = MainWindow(mode="offline", username=username)
        window.gamenet_password = password
        window.lblSubscriptionInfo.setText("حالت آفلاین فعال است")
        window.show()
        sys.exit(app.exec())

    except:
        # اگر اینترنت قطع بود → فقط فایل لایسنس را چک کن
        if os.path.exists("license.key"):
            with open("credentials.txt", "w") as f:
                f.write(f"username={username}\n")
                f.write(f"password={password}\n")

            window = MainWindow(mode="offline", username=username)
            window.gamenet_password = password
            window.lblSubscriptionInfo.setText("حالت آفلاین فعال است (بدون اینترنت)")
            window.show()
            sys.exit(app.exec())
        else:
            QMessageBox.critical(None, "خطا", "اتصال اینترنت برقرار نیست و فایل لایسنس موجود نیست.")
            sys.exit()