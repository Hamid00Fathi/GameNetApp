from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow , QLabel , QTableWidgetItem , QPushButton , QMessageBox , QDialog , QVBoxLayout , QComboBox , QLineEdit , QRadioButton , QCompleter , QTextEdit
from PyQt6.QtGui import QIcon , QColor
from PyQt6.QtCore import QTimer , Qt , QSize , QThread , pyqtSignal
from database import get_systems
from windows.remove_system import RemoveSystemWindow
from windows.add_system import AddSystemWindow
from windows.add_snack_to_system import AddSnackToSystem
from windows.charge_customer import ChargeCustomerWindow
from windows.customer_list import CustomerListWindow
from windows.delete_snack import DeleteSnackWindow
from windows.new_customer import NewCustomerWindow
from windows.new_snack import NewSnackWindow
from windows.snack_list import SnackListWindow
from windows.system_list import System_List
from windows.select_username import SelectUsernameWindow
import sqlite3
from datetime import datetime



class SenderThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, url, data):
        super().__init__()
        self.url = url
        self.data = data

    def run(self):
        import requests
        try:
            r = requests.post(self.url, json=self.data, timeout=5)
            self.finished.emit(r.text)
        except Exception as e:
            self.finished.emit(f"خطا: {e}")

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        uic.loadUi("ui/main_window.ui", self)

        self.detect_power_loss()

        self.btnAddSystem.triggered.connect(self.open_add_system)
        self.btnRemoveSystem.triggered.connect(self.open_remove_system)
        self.btnAddCustomer.triggered.connect(self.open_add_customer)
        self.btnChargeCustomer.triggered.connect(self.open_chgarge_customer)
        self.btnCustomerList.triggered.connect(self.open_customer_list)
        self.btnDeleteSnack.triggered.connect(self.open_delete_snack)
        self.btnSnackList.triggered.connect(self.open_snack_list)
        self.btnNewSnack.triggered.connect(self.open_new_snack)
        self.btnSystemList.triggered.connect(self.open_system_list)
        self.btnUsername.triggered.connect(self.open_user_name)

        self.timer = QTimer()
        self.timer.timeout.connect(self.load_systems)
        self.timer.start(1000)


        self.username = None

        # تلاش برای خواندن یوزرنیم از فایل
        try:
            with open("username.txt", "r", encoding="utf-8") as f:
                self.username = f.read().strip()
        except:
            pass

        # اگر یوزرنیم وجود داشت → تایمر ارسال را همینجا روشن کن
        if self.username:
            self.start_sender_timer()



        self.load_systems()


    def send_update(self):
        if not hasattr(self, "username"):
            return

        data = self.build_status_json()
        url = f"https://gamenet-server.onrender.com/update/{self.username}"

        self.thread = SenderThread(url, data)
        self.thread.finished.connect(lambda r: print("نتیجه ارسال:", r))
        self.thread.start()

    def build_status_json(self):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("""
            SELECT id, name, active, note, customer_id, price_per_hour
            FROM systems
        """)
        rows = cur.fetchall()

        data = {}

        for sys_id, name, active, note, customer_id, price_per_hour in rows:

            # مشتری
            if customer_id:
                cur.execute("SELECT name, family, code, balance FROM customers WHERE id=?", (customer_id,))
                c = cur.fetchone()
                if c:
                    customer_info = {
                        "name": f"{c[0]} {c[1]}",
                        "code": c[2],
                        "balance": c[3]
                    }
                else:
                    customer_info = {"name": "متفرقه", "code": "", "balance": 0}
            else:
                customer_info = {"name": "متفرقه", "code": "", "balance": 0}

            # سشن فعال
            cur.execute("""
                SELECT id, start_time, paused_seconds
                FROM sessions
                WHERE system_id=? AND end_time IS NULL
            """, (sys_id,))
            session = cur.fetchone()

            if session:
                session_id, start_time, paused_seconds = session

                if start_time:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elapsed_seconds = paused_seconds + (datetime.now() - start_dt).seconds
                else:
                    elapsed_seconds = paused_seconds

                h = elapsed_seconds // 3600
                m = (elapsed_seconds % 3600) // 60
                s = elapsed_seconds % 60
                elapsed = f"{h:02}:{m:02}:{s:02}"

                # هزینه زمان
                time_cost = int(elapsed_seconds * (price_per_hour / 3600))

            else:
                elapsed = "00:00:00"
                elapsed_seconds = 0
                time_cost = 0
                session_id = None

            # خوراکی‌ها
            snacks = []
            snacks_total = 0

            if session_id:
                cur.execute("""
                    SELECT snacks.name, snacks.price, session_snacks.quantity
                    FROM session_snacks
                    JOIN snacks ON snacks.id = session_snacks.snack_id
                    WHERE session_snacks.session_id=?
                """, (session_id,))
                for n, p, q in cur.fetchall():
                    snacks.append({"name": n, "price": p, "qty": q})
                    snacks_total += p * q

            # هزینه نهایی
            final_total = time_cost + snacks_total

            data[f"system{sys_id}"] = {
                "name": name,
                "active": active,
                "elapsed": elapsed,
                "time_cost": time_cost,
                "snacks": snacks,
                "snacks_total": snacks_total,
                "final_total": final_total,
                "note": note,
                "customer": customer_info,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        conn.close()
        return data

    def detect_power_loss(self):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("SELECT id, active, last_update_time FROM systems WHERE active IN (1, 2)")
        systems = cur.fetchall()

        now = datetime.now()

        for sys_id, active, last_update in systems:
            if not last_update:
                continue

            last_dt = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
            diff = (now - last_dt).seconds

            # اگر بیش از 5 ثانیه گذشته یعنی برنامه ناگهانی بسته شده
            if diff > 5:

                # گرفتن سشن فعال
                cur.execute("""
                    SELECT id, start_time, paused_seconds
                    FROM sessions
                    WHERE system_id=? AND end_time IS NULL
                """, (sys_id,))
                session = cur.fetchone()

                if session:
                    session_id, start_time, paused_seconds = session

                    # محاسبه زمان سپری‌شده تا لحظهٔ قطع برق
                    if start_time:
                        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                        elapsed_seconds = (last_dt - start_dt).seconds
                    else:
                        elapsed_seconds = 0

                    total_seconds = paused_seconds + elapsed_seconds

                    # ❗ فقط Pause می‌کنیم، سشن را نمی‌بندیم
                    cur.execute("""
                        UPDATE sessions
                        SET paused_seconds=?, start_time=NULL
                        WHERE id=?
                    """, (total_seconds, session_id))

                # ❗ سیستم را Pause می‌کنیم، نه آزاد
                cur.execute("UPDATE systems SET active=2 WHERE id=?", (sys_id,))

        conn.commit()
        conn.close()

    def status_item(self , active):
        item = QTableWidgetItem("")
        if active == 0:
            item.setBackground(QColor("#51E22D"))
        elif active == 1:
            item.setBackground(QColor("#FF3030"))
        else:
            item.setBackground(QColor("#2A7AE4"))

        return item


    def load_systems(self):

        # 1) آپدیت هر ثانیه
        with sqlite3.connect("gamenet.db") as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE systems
                SET last_update_time=?
                WHERE active IN (1, 2)
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))

        # 2) گرفتن سیستم‌ها
        systems = get_systems()
        self.systemTable.setRowCount(len(systems))
        systems.sort(key=lambda s: s[1])

        # 3) نمایش جدول
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()



        for row, sys in enumerate(systems):
            sys_id, name, active, start_time, elapsed, cost , custoer_id , note = sys

            # یادداشت
            note_btn = QPushButton()
            note_btn.setIcon(QIcon("icons/note.png"))
            note_btn.setIconSize(QSize(25, 25))
            note_btn.setStyleSheet("border: none;")
            note_btn.clicked.connect(lambda _, sid=sys_id: self.note_system(sid))
            self.systemTable.setCellWidget(row, 10, note_btn)
            self.systemTable.setColumnWidth(10, 80)

            # اگر سیستم فعال است → دکمه نوت فعال باشد
            if active in (1 ,2):
                note_btn.setEnabled(True)
            else:
                note_btn.setEnabled(False)

            # نام سیستم
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 9, item)
            self.systemTable.setColumnWidth(9, 200)

            # وضعیت
            self.systemTable.setItem(row, 8, self.status_item(active))
            self.systemTable.setColumnWidth(8, 60)

            # دکمه استارت
            start_btn = QPushButton()
            start_btn.setIcon(QIcon("icons/start.png"))
            start_btn.setIconSize(QSize(25, 25))
            start_btn.setStyleSheet("border: none;")
            start_btn.clicked.connect(lambda _, sid=sys_id: self.start_system(sid))

            # اگر سیستم فعال است → دکمه استارت غیرفعال
            if active == 1:
                start_btn.setEnabled(False)
            else:
                start_btn.setEnabled(True)


            self.systemTable.setCellWidget(row, 7, start_btn)
            self.systemTable.setColumnWidth(7, 110)

            # دکمه استاپ
            stop_btn = QPushButton()
            stop_btn.setIcon(QIcon("icons/stop.png"))
            stop_btn.setIconSize(QSize(28, 28))
            stop_btn.setStyleSheet("border: none;")
            stop_btn.clicked.connect(lambda _, sid=sys_id: self.stop_system(sid))
            self.systemTable.setCellWidget(row, 6, stop_btn)
            self.systemTable.setColumnWidth(6, 110)

            # دکمه تغییر سیستم
            change_btn = QPushButton()
            change_btn.setIcon(QIcon("icons/edit.png"))
            change_btn.setIconSize(QSize(28, 28))
            change_btn.setStyleSheet("border: none;")
            change_btn.clicked.connect(lambda _, sid=sys_id: self.change_system(sid))
            self.systemTable.setCellWidget(row, 5, change_btn)
            self.systemTable.setColumnWidth(5, 110)

            # دکمه خوراکی
            snack_btn = QPushButton()
            snack_btn.setIcon(QIcon("icons/snack.png"))
            snack_btn.setIconSize(QSize(28, 28))
            snack_btn.setStyleSheet("border: none;")
            snack_btn.clicked.connect(lambda _, sid=sys_id: self.add_snack(sid))
            self.systemTable.setCellWidget(row, 4, snack_btn)
            self.systemTable.setColumnWidth(4, 110)

            # زمان سپری‌شده
            item_elapsed = QTableWidgetItem(elapsed)
            item_elapsed.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 3, item_elapsed)
            self.systemTable.setColumnWidth(3, 100)

            # هزینه
            item_cost = QTableWidgetItem(f"{cost:,}")
            item_cost.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 2, item_cost)
            self.systemTable.setColumnWidth(2, 150)

            # دکمه تسویه
            checkout_btn = QPushButton()
            checkout_btn.setIcon(QIcon("icons/checkout.png"))
            checkout_btn.setIconSize(QSize(25, 25))
            checkout_btn.setStyleSheet("border: none;")
            checkout_btn.clicked.connect(lambda _, sid=sys_id: self.checkout(sid))
            self.systemTable.setCellWidget(row, 0, checkout_btn)
            self.systemTable.setColumnWidth(0, 90)

            # گرفتن نام مشتری
            cur.execute("""
                SELECT customers.name, customers.family, customers.code
                FROM systems
                LEFT JOIN customers ON customers.id = systems.customer_id
                WHERE systems.id=?
            """, (sys_id,))
            customer = cur.fetchone()

            if customer and customer[0] is not None:
                cname = f"{customer[0]} {customer[1]} - {customer[2]}"
            else:
                cname = "متفرقه"

            item_customer = QTableWidgetItem(cname)
            item_customer.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 1, item_customer)
            self.systemTable.setColumnWidth(1, 200)


        conn.close()



    def note_system(self, sys_id):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        # گرفتن نوت قبلی
        cur.execute("SELECT note FROM systems WHERE id=?", (sys_id,))
        row = cur.fetchone()
        old_note = row[0] if row else ""

        # ساخت پنجره نوت
        dlg = QDialog(self)
        dlg.setWindowTitle("یادداشت سیستم")
        dlg.resize(350, 200)

        layout = QVBoxLayout(dlg)

        label = QLabel("یادداشت سیستم:")
        layout.addWidget(label)

        text = QTextEdit()
        text.setText(old_note)
        layout.addWidget(text)

        btn_save = QPushButton("ذخیره")
        btn_save.clicked.connect(dlg.accept)
        layout.addWidget(btn_save)

        # اگر کاربر ذخیره نکرد
        if dlg.exec() != QDialog.DialogCode.Accepted:
            conn.close()
            return

        new_note = text.toPlainText()

        # ذخیره نوت جدید
        cur.execute("UPDATE systems SET note=? WHERE id=?", (new_note, sys_id))
        conn.commit()
        conn.close()

        # رفرش جدول
        self.load_systems()

    def start_system(self, sys_id):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()
        
        # اگر سیستم Pause شده باشد → ادامه همان مشتری
        cur.execute("SELECT active, customer_id FROM systems WHERE id=?", (sys_id,))
        active, customer_id = cur.fetchone()

        if active == 2:
            # ادامه سشن قبلی
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur.execute("""
                SELECT id, paused_seconds
                FROM sessions
                WHERE system_id=? AND end_time IS NULL
            """, (sys_id,))
            session_id, paused_seconds = cur.fetchone()

            # Resume
            cur.execute("""
                UPDATE sessions
                SET start_time=?, paused_seconds=?
                WHERE id=?
            """, (now_str, paused_seconds, session_id))

            # فعال کردن سیستم
            cur.execute("UPDATE systems SET active=1 WHERE id=?", (sys_id,))
            conn.commit()
            conn.close()

            self.load_systems()
            return


        # چک کردن اینکه سیستم آزاد است یا نه
        cur.execute("SELECT active FROM systems WHERE id=?", (sys_id,))
        active = cur.fetchone()[0]
        if active == 1:
            QMessageBox.warning(self, "خطا", "این سیستم هم‌اکنون فعال است.")
            conn.close()
            return

        # انتخاب حالت: مشتری یا متفرقه
        mode_dlg = QDialog(self)
        mode_dlg.setWindowTitle("انتخاب نوع کاربر")
        v = QVBoxLayout(mode_dlg)

        rb_customer = QRadioButton("حساب کاربری (مشتری)")
        rb_guest = QRadioButton("متفرقه")
        rb_guest.setChecked(True)

        v.addWidget(rb_customer)
        v.addWidget(rb_guest)

        btn_mode = QPushButton("ادامه")
        btn_mode.clicked.connect(mode_dlg.accept)
        v.addWidget(btn_mode)

        if mode_dlg.exec() != QDialog.DialogCode.Accepted:
            conn.close()
            return

        mode = "customer" if rb_customer.isChecked() else "guest"
        customer_id = None

        if mode == "customer":
            # انتخاب مشتری
            cdlg = QDialog(self)
            cdlg.setWindowTitle("انتخاب مشتری")
            clayout = QVBoxLayout(cdlg)

            search = QLineEdit()
            search.setPlaceholderText("جستجو مشتری...")
            clayout.addWidget(search)

            ccombo = QComboBox()
            clayout.addWidget(ccombo)

            cur.execute("SELECT id, name, family, code FROM customers")
            customers = cur.fetchall()

            if not customers:
                QMessageBox.warning(self, "خطا", "هیچ مشتری ثبت نشده است.")
                conn.close()
                return

            names = [f"{name} {family} - {code}" for cid, name, family, code in customers]
            completer = QCompleter(names)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            search.setCompleter(completer)

            def update_list():
                text = search.text().strip()
                ccombo.clear()
                for cid, name, family, code in customers:
                    full = f"{name} {family} - {code}"
                    if text == "" or text in full:
                        ccombo.addItem(full, cid)

            search.textChanged.connect(update_list)
            update_list()

            cbtn = QPushButton("انتخاب")
            cbtn.clicked.connect(cdlg.accept)
            clayout.addWidget(cbtn)

            if cdlg.exec() != QDialog.DialogCode.Accepted:
                conn.close()
                return

            customer_id = ccombo.currentData()

            # جلوگیری از باز شدن چند سیستم با یک مشتری
            cur.execute("""
                SELECT COUNT(*) FROM sessions
                WHERE customer_id=? AND end_time IS NULL
            """, (customer_id,))
            active_sessions = cur.fetchone()[0]

            if active_sessions > 0:
                QMessageBox.warning(self, "خطا", "این مشتری هم‌اکنون در یک سیستم دیگر فعال است.")
                conn.close()
                return

            # ثبت مشتری روی سیستم
            cur.execute("UPDATE systems SET customer_id=? WHERE id=?", (customer_id, sys_id))

        else:
            # متفرقه → customer_id خالی
            cur.execute("UPDATE systems SET customer_id=NULL WHERE id=?", (sys_id,))

        # ساخت سشن جدید
        start_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO sessions (system_id, customer_id, start_time, paused_seconds)
            VALUES (?, ?, ?, 0)
        """, (sys_id, customer_id, start_str))

        cur.execute("UPDATE systems SET active=1 WHERE id=?", (sys_id,))
        conn.commit()
        conn.close()

        self.load_systems()



    def stop_system(self, sys_id):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("""
            SELECT id, start_time, paused_seconds
            FROM sessions
            WHERE system_id=? AND end_time IS NULL
        """, (sys_id,))
        session = cur.fetchone()

        if not session:
            conn.close()
            return

        session_id, start_time, paused_seconds = session

        if start_time:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            elapsed_seconds = (datetime.now() - start_dt).seconds
        else:
            elapsed_seconds = 0

        total_seconds = paused_seconds + elapsed_seconds

        cur.execute("""
            UPDATE sessions
            SET paused_seconds=?, start_time=NULL
            WHERE id=?
        """, (total_seconds, session_id))

        cur.execute("UPDATE systems SET active=2 WHERE id=?", (sys_id,))

        conn.commit()
        conn.close()
        self.load_systems()


    def transfer_session(self, old_sys_id, new_sys_id):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("""
            SELECT id, start_time, paused_seconds, customer_id
            FROM sessions
            WHERE system_id=? AND end_time IS NULL
        """, (old_sys_id,))
        session = cur.fetchone()

        if not session:
            conn.close()
            return

        session_id, start_time, paused_seconds, customer_id = session

        if start_time:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            elapsed_seconds = (datetime.now() - start_dt).seconds
        else:
            elapsed_seconds = 0

        total_seconds = paused_seconds + elapsed_seconds

        # بستن سشن قبلی
        cur.execute("""
            UPDATE sessions
            SET end_time=?, paused_seconds=?
            WHERE id=?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_seconds, session_id))

        cur.execute("UPDATE systems SET active=0 WHERE id=?", (old_sys_id,))

        # ساخت سشن جدید روی سیستم جدید
        cur.execute("""
            INSERT INTO sessions (system_id, customer_id, start_time, paused_seconds)
            VALUES (?, ?, NULL, ?)
        """, (new_sys_id, customer_id, total_seconds))

        cur.execute("UPDATE systems SET active=1 WHERE id=?", (new_sys_id,))

        self.load_systems()

        conn.commit()
        conn.close()
        self.load_systems()

    def change_system(self, old_sys_id):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        # گرفتن سیستم‌های آزاد
        cur.execute("SELECT id, name, price_per_hour FROM systems WHERE id!=? AND active = 0", (old_sys_id,))
        systems = cur.fetchall()

        if not systems:
            QMessageBox.warning(self, "خطا", "هیچ سیستم آزادی برای انتقال وجود ندارد.")
            conn.close()
            return

        # توقف سیستم قبلی قبل از انتخاب سیستم جدید
        self.stop_system(old_sys_id)

        # گرفتن نوت سیستم قبلی
        cur.execute("SELECT note FROM systems WHERE id=?", (old_sys_id,))
        old_note = cur.fetchone()[0]

        # گرفتن هزینه سیستم قبلی
        cur.execute("SELECT cost FROM systems WHERE id=?", (old_sys_id,))
        old_cost = cur.fetchone()[0]

        # انتخاب سیستم جدید
        dlg = QDialog(self)
        dlg.resize(200, 100)
        dlg.setWindowTitle("انتقال سیستم")
        layout = QVBoxLayout(dlg)

        combo = QComboBox()
        for sid, name, price in systems:
            combo.addItem(f"{name} - {price:,} تومان/ساعت", sid)
        layout.addWidget(combo)

        btn = QPushButton("انتقال")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)

        # اگر کاربر لغو کرد → سیستم قبلی دوباره اجرا شود
        if dlg.exec() != QDialog.DialogCode.Accepted:
            conn.close()
            self.start_system(old_sys_id)
            return

        new_sys_id = combo.currentData()

        # گرفتن قیمت سیستم قبلی
        cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (old_sys_id,))
        old_price = cur.fetchone()[0]

        # گرفتن قیمت سیستم جدید
        cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (new_sys_id,))
        new_price = cur.fetchone()[0]

        # گرفتن سشن فعال سیستم قبلی
        cur.execute("""
            SELECT id, start_time, paused_seconds, customer_id
            FROM sessions
            WHERE system_id=? AND end_time IS NULL
        """, (old_sys_id,))
        session = cur.fetchone()

        if not session:
            QMessageBox.warning(self, "خطا", "این سیستم هیچ سشن فعالی ندارد.")
            conn.close()
            self.start_system(old_sys_id)
            return

        session_id, start_time, paused_seconds, customer_id = session

        # محاسبه زمان سپری‌شده
        if start_time:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            elapsed_seconds = (datetime.now() - start_dt).seconds
        else:
            elapsed_seconds = 0

        total_seconds = paused_seconds + elapsed_seconds

        # هشدار قیمت متفاوت
        if old_price != new_price:
            msg = QMessageBox(self)
            msg.setWindowTitle("تغییر سیستم با قیمت متفاوت")
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(
                f"قیمت سیستم فعلی: {old_price:,} تومان/ساعت<br>"
                f"قیمت سیستم جدید: {new_price:,} تومان/ساعت<br><br>"
                f"آیا مطمئن هستید؟<br>"
                f"⛔ زمان سیستم جدید از صفر شروع می‌شود<br>"
                f"⛔ هزینهٔ سیستم قبلی به سیستم جدید اضافه می‌شود"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if msg.exec() != QMessageBox.StandardButton.Yes:
                conn.close()
                self.start_system(old_sys_id)
                return

        # توقف سشن قبلی
        cur.execute("""
            UPDATE sessions
            SET paused_seconds=?, start_time=NULL
            WHERE id=?
        """, (total_seconds, session_id))

        # آزاد کردن سیستم قبلی + پاک کردن نوت + پاک کردن هزینه
        cur.execute("UPDATE systems SET active=0, customer_id=NULL, note='', cost=0 WHERE id=?", (old_sys_id,))

        # اگر قیمت‌ها متفاوت بودند → زمان سیستم جدید از صفر شروع شود
        if old_price != new_price:

            previous_cost = int((total_seconds / 60) * (old_price / 60))

            # اضافه کردن هزینه قبلی + هزینه ذخیره‌شده قبلی
            cur.execute("""
                UPDATE systems
                SET cost = cost + ?
                WHERE id=?
            """, (previous_cost + old_cost, new_sys_id))

            cur.execute("""
                UPDATE sessions
                SET system_id=?, paused_seconds=0, start_time=?
                WHERE id=?
            """, (new_sys_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session_id))
        else:
            cur.execute("""
                UPDATE sessions
                SET system_id=?, start_time=?
                WHERE id=?
            """, (new_sys_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session_id))

        # فعال کردن سیستم جدید + انتقال نوت
        cur.execute("UPDATE systems SET active=1, customer_id=?, note=? WHERE id=?", (customer_id, old_note, new_sys_id))

        conn.commit()
        conn.close()

        self.load_systems()

    def add_snack(self, sys_id):
        self.snack_window = AddSnackToSystem(sys_id)
        self.snack_window.show()

    def checkout(self, sys_id):
        self.timer.stop()

        try:
            with sqlite3.connect("gamenet.db") as conn:
                cur = conn.cursor()

                cur.execute("SELECT note FROM systems WHERE id=?", (sys_id,))
                row = cur.fetchone()
                note = row[0] if row else ""

                # گرفتن سشن فعال
                cur.execute("""
                    SELECT id, start_time, paused_seconds, customer_id
                    FROM sessions
                    WHERE system_id=? AND end_time IS NULL
                """, (sys_id,))
                session = cur.fetchone()

                if not session:
                    QMessageBox.information(self, "تسویه", "هیچ سشن فعالی برای این سیستم نیست.")
                    conn.close()
                    return

                session_id, start_time, paused_seconds, customer_id = session

                # محاسبه زمان جاری
                if start_time:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elapsed_seconds = (datetime.now() - start_dt).seconds
                else:
                    elapsed_seconds = 0

                total_seconds = paused_seconds + elapsed_seconds

                # گرفتن قیمت سیستم + هزینه قبلی + نوت
                cur.execute("SELECT price_per_hour, cost FROM systems WHERE id=?", (sys_id,))
                price_per_hour, transfer_cost = cur.fetchone()

                # توقف واقعی سشن (Pause) و تغییر وضعیت سیستم به توقف
                cur.execute("""
                    UPDATE sessions
                    SET paused_seconds=?, start_time=NULL
                    WHERE id=?
                """, (total_seconds, session_id))

                cur.execute("UPDATE systems SET active=2 WHERE id=?", (sys_id,))
                conn.commit()

                # آپدیت فوری UI تا زمان و قیمت متوقف شوند
                self.load_systems()

                # گرفتن قیمت سیستم
                cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (sys_id,))
                price_per_hour = cur.fetchone()[0]
                game_cost = int((total_seconds / 60) * (price_per_hour / 60))

                # لیست خوراکی‌ها
                cur.execute("""
                    SELECT snacks.name, snacks.price, session_snacks.quantity
                    FROM session_snacks
                    JOIN snacks ON snacks.id = session_snacks.snack_id
                    WHERE session_snacks.session_id=?
                """, (session_id,))
                snacks_list = cur.fetchall()

                snack_cost = sum(price * qty for _, price, qty in snacks_list)


                # مشخص کردن نوع مشتری
                if customer_id:
                    cur.execute("""
                        SELECT name, family, code
                        FROM customers
                        WHERE id=?
                    """, (customer_id,))
                    customer = cur.fetchone()
                    if customer:
                        customer_text = f"مشتری: {customer[0]} {customer[1]} - {customer[2]}"
                    else:
                        customer_text = "مشتری: نامشخص"
                else:
                    customer_text = "مشتری: متفرقه"

                # ساخت پنجره تسویه
                dlg = QDialog(self)
                dlg.setWindowTitle("تسویه حساب")
                layout = QVBoxLayout(dlg)

                text = customer_text + "\n\nخوراکی‌ها:\n"
                for name, price, qty in snacks_list:
                    text += f"{name} × {qty} = {price * qty:,}\n"

                text += f"\nهزینه بازی: {game_cost:,}\n"
                if transfer_cost > 0:
                    text += f"هزینهٔ سیستم قبلی: {transfer_cost:,} تومان\n"

                text += f"هزینه خوراکی‌ها: {snack_cost:,}\n"
                text += f"جمع کل: {game_cost + snack_cost + transfer_cost:,}\n"
                if note.strip() != "":
                    text += f"\nیادداشت سیستم:\n{note}"


                label = QLabel(text)



                layout.addWidget(label)

                # -----------------------------
                # گزینه‌های پرداخت فقط برای حساب کاربری
                # -----------------------------
                if customer_id:
                    rb_instant = QRadioButton("پرداخت لحظه‌ای")
                    rb_add_to_account = QRadioButton("افزودن به حساب مشتری")
                    rb_custom_amount = QRadioButton("مبلغ دلخواه")

                    rb_instant.setChecked(True)

                    layout.addWidget(rb_instant)
                    layout.addWidget(rb_add_to_account)
                    layout.addWidget(rb_custom_amount)

                    custom_input = QLineEdit()
                    custom_input.setPlaceholderText("مبلغ دلخواه...")
                    custom_input.setEnabled(False)
                    layout.addWidget(custom_input)

                    rb_custom_amount.toggled.connect(lambda checked: custom_input.setEnabled(checked))


                discount = QLineEdit()
                discount.setPlaceholderText("تخفیف (اختیاری)")
                layout.addWidget(discount)

                btn_ok = QPushButton("تسویه")
                btn_cancel = QPushButton("لغو")

                btn_ok.clicked.connect(lambda: dlg.done(1))
                btn_cancel.clicked.connect(lambda: dlg.done(0))

                layout.addWidget(btn_ok)
                layout.addWidget(btn_cancel)

                result = dlg.exec()

                # اگر کاربر لغو کرد → ادامه سشن
                if result != 1:
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # ادامه دادن سشن
                    cur.execute("""
                        UPDATE sessions
                        SET start_time=?, paused_seconds=?
                        WHERE id=?
                    """, (now_str, total_seconds, session_id))

                    # فعال کردن سیستم دوباره
                    cur.execute("UPDATE systems SET active=1 WHERE id=?", (sys_id,))

                    conn.commit()
                    # conn.close()

                    self.load_systems()
                    return

                # -----------------------------
                # اعمال نوع پرداخت
                # -----------------------------
                total = game_cost + snack_cost + transfer_cost

                payment_info = ""

                if customer_id:
                    cur.execute("SELECT balance FROM customers WHERE id=?", (customer_id,))
                    balance = cur.fetchone()[0]

                    # پرداخت لحظه‌ای
                    if rb_instant.isChecked():
                        payment_info = f"پرداخت نقدی: {total:,} تومان"

                    # افزودن به حساب
                    elif rb_add_to_account.isChecked():
                        new_balance = balance - total
                        cur.execute("""
                            UPDATE customers
                            SET balance=?
                            WHERE id=?
                        """, (new_balance, customer_id))

                        # رنگی کردن موجودی جدید
                        if new_balance < 0:
                            balance_text = f"<span style='color:red;'>{new_balance:,}</span>"
                        else:
                            balance_text = f"{new_balance:,}"

                        payment_info = (
                            f"کسر از حساب مشتری: {total:,} تومان<br>"
                            f"موجودی جدید مشتری: {balance_text} تومان"
                        )

                    # مبلغ دلخواه
                    elif rb_custom_amount.isChecked():
                        custom_amount = int(custom_input.text())
                        new_balance = balance - custom_amount

                        cur.execute("""
                            UPDATE customers
                            SET balance=?
                            WHERE id=?
                        """, (new_balance, customer_id))

                        # رنگی کردن موجودی جدید
                        if new_balance < 0:
                            balance_text = f"<span style='color:red;'>{new_balance:,}</span>"
                        else:
                            balance_text = f"{new_balance:,}"

                        payment_info = (
                            f"کسر مبلغ دلخواه: {custom_amount:,} تومان<br>"
                            f"موجودی جدید مشتری: {balance_text} تومان"
                        )


                else:
                    # متفرقه
                    payment_info = f"پرداخت نقدی: {total:,} تومان"
                    # گرفتن نوت سیستم
                    cur.execute("SELECT note FROM systems WHERE id=?", (sys_id,))
                    row = cur.fetchone()
                    note = row[0] if row else ""


                # نمایش در پنجره
                msg = QMessageBox(self)
                msg.setWindowTitle("نتیجه پرداخت")
                msg.setTextFormat(Qt.TextFormat.RichText)   # ← اجازه استفاده از HTML
                msg.setText(payment_info)
                msg.exec()

                # بستن کامل سشن و آزاد کردن سیستم
                cur.execute("""
                    UPDATE sessions
                    SET end_time=?, paused_seconds=?
                    WHERE id=?
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_seconds, session_id))

                cur.execute("UPDATE systems SET active=0, customer_id=NULL WHERE id=?", (sys_id,))

                # پاک کردن نوت بعد از تسویه
                cur.execute("UPDATE systems SET cost=0 , note='' WHERE id=?", (sys_id,))
                
                conn.commit()

                # conn.close()

                self.load_systems()

        except Exception as e:
            QMessageBox.warning(self, "خطا" , f"مشکل در تسویه حساب:\n{e}")

        finally:
            self.timer.start(1000)

            self.load_systems()

    def open_add_system(self):
        self.addSystem = AddSystemWindow()
        self.addSystem.show()

    def open_remove_system(self):
        self.removeSystem = RemoveSystemWindow()
        self.removeSystem.show()


    def open_add_customer(self):
            self.addcustomer = NewCustomerWindow()
            self.addcustomer.show()

    def open_chgarge_customer(self):
            self.chargecustomer = ChargeCustomerWindow()
            self.chargecustomer.show()

    def open_customer_list(self):
            self.customerlist = CustomerListWindow()
            self.customerlist.show()

    def open_new_snack(self):
            self.newsnack = NewSnackWindow()
            self.newsnack.show()

    def open_delete_snack(self):
            self.deletesnack = DeleteSnackWindow()
            self.deletesnack.show()

    def open_snack_list(self):
            self.snacklist = SnackListWindow()
            self.snacklist.show()

    def open_system_list(self):
           self.systemlist = System_List()
           self.systemlist.show()


    def start_sender_timer(self):
        self.sender_timer = QTimer()
        self.sender_timer.timeout.connect(self.send_update)
        self.sender_timer.start(5000)

    def open_user_name(self):
        dlg = SelectUsernameWindow()
        dlg.main_window = self
        dlg.load_saved_username()
        dlg.exec()



