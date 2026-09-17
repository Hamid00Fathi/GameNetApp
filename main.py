from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
import datetime
from windows.main_window import MainWindow
from database import create_tables
import requests
import sys
import os
from datetime import datetime
import jdatetime

API_BASE = "https://gamenet-server-mongo-production.up.railway.app"


def get_today_gregorian():
    g_now = datetime.now()
    j_now = jdatetime.datetime.now()

    if j_now.year != g_now.year:
        return j_now.togregorian()
    else:
        return g_now


# ---------------------------------------------------------
# چک اشتراک از سرور (آنلاین مود)
# ---------------------------------------------------------
def check_subscription(username):
    try:
        url = f"{API_BASE}/subscription/{username}"
        r = requests.get(url, timeout=5)

        try:
            data = r.json()
        except:
            return "error", None, None

        if not isinstance(data, dict):
            return "error", None, None

        expire_date = data.get("expireDate")
        active = data.get("active")

        if expire_date is None:
            return "inactive", None, 0

        expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")
        today = get_today_gregorian()
        delta = expire_dt - today
        days_left = delta.days + 1

        if active is False:
            return "inactive", expire_date, days_left

        if active is True:
            return "active", expire_date, days_left

        return "error", None, None

    except Exception as e:
        print("خطا در چک اشتراک:", e)
        return "error", None, None


# ---------------------------------------------------------
# چک وضعیت لایسنس از سرور (برای آفلاین مود)
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

    except Exception as e:
        print("خطا در چک لایسنس:", e)
        # اگر اینترنت قطع باشد ولی فایل لایسنس هست → اجازه بده آفلاین اجرا شود
        return True


# ---------------------------------------------------------
# خواندن credentials.txt
# ---------------------------------------------------------
def read_credentials():
    if not os.path.exists("credentials.txt"):
        return None, None

    username = None
    password = None

    try:
        with open("credentials.txt", "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
            for line in lines:
                if line.startswith("username="):
                    username = line.split("=", 1)[1].strip()
                elif line.startswith("password="):
                    password = line.split("=", 1)[1].strip()
    except:
        pass

    return username, password


# ---------------------------------------------------------
# ذخیره credentials.txt
# ---------------------------------------------------------
def save_credentials(username, password):
    with open("credentials.txt", "w", encoding="utf-8") as f:
        f.write(f"username={username}\n")
        f.write(f"password={password}\n")


# ---------------------------------------------------------
# پنجره ورود برای اولین اجرا
# ---------------------------------------------------------
class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ورود به نرم‌افزار گیم‌نت")
        self.resize(300, 150)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("نام کاربری گیم‌نت:"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)

        layout.addWidget(QLabel("رمز ورود گیم‌نت:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        btn = QPushButton("ورود")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_data(self):
        return (
            self.username_input.text().strip(),
            self.password_input.text().strip()
        )


# ---------------------------------------------------------
# اجرای اصلی برنامه
# ---------------------------------------------------------

create_tables()
app = QApplication(sys.argv)

username, password = read_credentials()

mode = None
expire_date = None
days_left = None

# ---------------------------------------------------------
# اگر فایل لایسنس وجود داشته باشد → اول لایسنس را چک کن
# ---------------------------------------------------------
if os.path.exists("license.key") and username:
    if check_license_status(username):
        mode = "offline"
    else:
        QMessageBox.critical(None, "خطا", "لایسنس معتبر نیست. لطفاً دوباره آنلاین شوید یا لایسنس را اصلاح کنید.")
        sys.exit()

# ---------------------------------------------------------
# اگر فایل لایسنس نبود → مثل قبل اشتراک را چک کن (آنلاین مود)
# ---------------------------------------------------------
if mode is None:
    # اگر credentials.txt وجود نداشت → پنجره ورود
    if not username or not password:
        login = LoginWindow()

        if login.exec() != QDialog.DialogCode.Accepted:
            sys.exit()

        username, password = login.get_data()

        if not username or not password:
            QMessageBox.critical(None, "خطا", "نام کاربری یا رمز ورود وارد نشده است.")
            sys.exit()

        status, expire_date, days_left = check_subscription(username)

        if status == "inactive":
            QMessageBox.critical(None, "خطا", "اشتراک شما فعال نیست یا ثبت نشده است.")
            sys.exit()

        if status == "error":
            QMessageBox.critical(None, "خطا", "اتصال به سرور ممکن نیست.")
            sys.exit()

        save_credentials(username, password)
        mode = "online"

    else:
        # credentials.txt وجود دارد → چک اشتراک
        status, expire_date, days_left = check_subscription(username)

        if status == "inactive":
            QMessageBox.critical(None, "خطا", "اشتراک شما فعال نیست یا ثبت نشده است.")
            sys.exit()

        if status == "error":
            QMessageBox.critical(None, "خطا", "اتصال به سرور ممکن نیست.")
            sys.exit()

        mode = "online"


# ---------------------------------------------------------
# اجرای نرم‌افزار اصلی
# ---------------------------------------------------------
try:
    # اگر خواستی بعداً می‌تونی mode و username را به MainWindow پاس بدی
    window = MainWindow(mode=mode, username=username)
except Exception as e:
    QMessageBox.critical(None, "خطا در اجرای MainWindow", str(e))
    sys.exit()

window.show()

# فقط اگر در حالت آنلاین هستیم، اطلاعات اشتراک را روی لیبل بزن
if mode == "online" and expire_date is not None and days_left is not None:
    window.lblSubscriptionInfo.setText(f"مانده اشتراک: {days_left} روز | پایان: {expire_date}")
else:
    window.lblSubscriptionInfo.setText("حالت آفلاین فعال است")

exit_code = app.exec()
sys.exit(exit_code)