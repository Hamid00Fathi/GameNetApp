from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout,QLabel, QLineEdit, QPushButton
import datetime
from windows.main_window import MainWindow
from database import create_tables
import requests
import sys
import os
from datetime import datetime
import jdatetime


def get_today_gregorian():
    # تاریخ میلادی سیستم
    g_now = datetime.now()

    # تاریخ شمسی سیستم
    j_now = jdatetime.datetime.now()

    # اگر سال شمسی با میلادی فرق داشت → سیستم شمسی است
    if j_now.year != g_now.year:
        # سیستم شمسی است → تاریخ شمسی را به میلادی تبدیل کن
        return j_now.togregorian()
    else:
        # سیستم میلادی است → همان میلادی را برگردان
        return g_now
    
# ---------------------------------------------------------
# چک اشتراک از سرور (سازگار با API فعلی)
# ---------------------------------------------------------
def check_subscription(username):
    try:
        url = f"https://gamenet-server-mongo.onrender.com/subscription/{username}"
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

        # تاریخ پایان اشتراک (میلادی)
        expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")

        # تاریخ امروز (تشخیص شمسی/میلادی → تبدیل به میلادی)
        today = get_today_gregorian()

        # اختلاف روز
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
        super().__init()
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

# ---------------------------------------------------------
# اگر credentials.txt وجود نداشت → پنجره ورود
# ---------------------------------------------------------
if not username or not password:
    login = LoginWindow()

    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit()

    username, password = login.get_data()

    if not username or not password:
        QMessageBox.critical(None, "خطا", "نام کاربری یا رمز ورود وارد نشده است.")
        sys.exit()

    # چک اشتراک
    status , expire_date , days_left = check_subscription(username)

    if status == "inactive":
        QMessageBox.critical(None, "خطا", "اشتراک شما فعال نیست یا ثبت نشده است.")
        sys.exit()

    if status == "error":
        QMessageBox.critical(None, "خطا", "اتصال به سرور ممکن نیست.")
        sys.exit()

    save_credentials(username, password)

else:
    # ---------------------------------------------------------
    # اگر credentials.txt وجود داشت → چک اشتراک
    # ---------------------------------------------------------
    status , expire_date , days_left = check_subscription(username)

    if status == "inactive":
        QMessageBox.critical(None, "خطا", "اشتراک شما فعال نیست یا ثبت نشده است.")
        sys.exit()

    if status == "error":
        QMessageBox.critical(None, "خطا", "اتصال به سرور ممکن نیست.")
        sys.exit()


# ---------------------------------------------------------
# اجرای نرم‌افزار اصلی
# ---------------------------------------------------------
try:
    window = MainWindow()
except Exception as e:
    QMessageBox.critical(None, "خطا در اجرای MainWindow", str(e))
    sys.exit()

window.show()

window.lblSubscriptionInfo.setText(f"مانده اشتراک: {days_left} روز | پایان: {expire_date}")

sys.exit(app.exec())