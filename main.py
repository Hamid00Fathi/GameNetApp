from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtGui import QIcon
import sys
import os
import requests
from datetime import datetime
from windows.main_window import MainWindow
from database import create_tables
from windows.theme import apply_dark_theme
import certifi


APP_DIR = os.path.dirname(os.path.abspath(__file__))
API_BASE = "https://gamenet-server-mongo-production.up.railway.app"

# فایل‌های نسبی برنامه (دیتابیس، آیکن و فایل‌های ورود) همیشه از پوشهٔ برنامه خوانده شوند.
os.chdir(APP_DIR)


# ---------------------------------------------------------
# لاگین واقعی (فقط چک یوزرنیم + پسورد)
# ---------------------------------------------------------
def check_login(username, password):
    try:
        r = requests.post(
            f"{API_BASE}/login",
            json={"username": username, "password": password},
            timeout=5,
            verify=certifi.where()
        )

        # اگر سرور JSON برگرداند و ok=True باشد
        try:
            data = r.json()
            if data.get("ok") is True:
                return True
        except:
            pass

        # اگر سرور پاسخ داده ولی لاگین اشتباه است
        QMessageBox.critical(None, "خطا", 
            "نام کاربری یا رمز ورود اشتباه است!")
        return False

    except requests.exceptions.SSLError:
        QMessageBox.critical(None, "خطای SSL",
            "ارتباط امن با سرور برقرار نشد!")
        return False

    except requests.exceptions.ConnectionError:
        QMessageBox.critical(None, "خطای اتصال",
            "درخواست به سرور ارسال نشد!")
        return False

    except requests.exceptions.Timeout:
        QMessageBox.critical(None, "تایم‌اوت",
            "سرور در زمان مناسب پاسخ نداد!")
        return False

    except Exception as e:
        QMessageBox.critical(None, "خطای ناشناخته",
            f"خطای غیرمنتظره رخ داد:\n{e}")
        return False

# ---------------------------------------------------------
# چک اشتراک آنلاین
# ---------------------------------------------------------
def check_subscription(username):
    try:
        r = requests.get(
            f"{API_BASE}/subscription/{username}",
            timeout=5,
            verify=certifi.where()
        )

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

    except requests.exceptions.SSLError:
        QMessageBox.critical(None, "خطای SSL", "ارتباط امن برقرار نشد.")
        return "error", None, None

    except Exception:
        QMessageBox.critical(None, "خطا", "مشکل در دریافت اطلاعات اشتراک.")
        return "error", None, None


# ---------------------------------------------------------
# چک لایسنس آفلاین
# ---------------------------------------------------------
def check_license_status(username):
    try:
        r = requests.get(
            f"{API_BASE}/license/status/{username}",
            timeout=5,
            verify=certifi.where()
        )

        data = r.json()

        if not data.get("ok"):
            return False

        if data.get("licenseType") == "offline" and data.get("licenseActive"):
            return True

        return False

    except:
        return True  # حالت آفلاین باید بدون اینترنت کار کند


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

    # چک واقعی لایسنس
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
            timeout=5,
            verify=certifi.where()
        )
        r.raise_for_status()
        data = r.json()

        if not check_login(username, password):
            QMessageBox.critical(None, "خطا", "نام کاربری یا رمز ورود اشتباه است.")
            sys.exit()        

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

    except requests.RequestException:
        # استفادهٔ آفلاین فقط در صورت وجود فایل‌های قبلی و تطبیق با حساب ذخیره‌شده مجاز است.
        if os.path.isfile("license.key") and os.path.isfile("credentials.txt"):
            try:
                with open("license.key", "r", encoding="utf-8") as f:
                    saved_license = f.read().strip()
                with open("credentials.txt", "r", encoding="utf-8") as f:
                    saved_credentials = dict(
                        line.split("=", 1) for line in f.read().splitlines() if "=" in line
                    )
                if (saved_license and saved_credentials.get("username") == username
                        and saved_credentials.get("password") == password):
                    window = MainWindow(mode="offline", username=username)
                    window.gamenet_password = password
                    window.lblSubscriptionInfo.setText("حالت آفلاین فعال است (بدون اینترنت)")
                    window.show()
                    sys.exit(app.exec())
            except (OSError, ValueError):
                pass

        QMessageBox.critical(None, "خطا", "اتصال اینترنت برقرار نیست و لایسنس ذخیره‌شدهٔ معتبر در دسترس نیست.")
        sys.exit()
    except (ValueError, KeyError) as e:
        QMessageBox.critical(None, "خطا", f"پاسخ سرور لایسنس قابل پردازش نیست: {e}")
        sys.exit()