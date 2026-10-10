from PyQt6 import uic
from PyQt6.QtWidgets import *
from PyQt6.QtGui import QIcon , QColor , QPixmap, QCursor
from PyQt6.QtCore import *
from database import get_systems , get_connection
import database
from windows.add_system import AddSystemWindow
from windows.add_snack_to_system import AddSnackToSystem
from windows.charge_customer import ChargeCustomerWindow
from windows.customer_list import CustomerListWindow
from windows.new_customer import NewCustomerWindow
from windows.snack_list import SnackListWindow
from windows.system_list import System_List
from windows.select_username import SelectUsernameWindow
from datetime import datetime , timedelta
import sqlite3 , requests
import re
import sys , os
import certifi
from datetime import datetime
import system_repository as repo



def to_int_safe(v, default=0):
    try:
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return int(v)
        return int(str(v).replace(",", "").strip() or default)
    except Exception:
        return default

def to_float_safe(v, default=0.0):
    try:
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return float(v)
        return float(str(v).replace(",", "").strip() or default)
    except Exception:
        return default

class RateSelectDialog(QDialog):
    def __init__(self, rates, parent=None):
        super().__init__(parent)
        self.setWindowTitle("انتخاب تعرفه")
        self.selected_rate_id = None
        v = QVBoxLayout(self)
        self.listw = QListWidget()
        for r in rates:
            rid, controllers_count, price_per_hour, name = r
            label = f"{name or f'{controllers_count} دسته'} — {price_per_hour:,}"
            self.listw.addItem(label)
            self.listw.item(self.listw.count()-1).setData(Qt.ItemDataRole.UserRole, rid)
        v.addWidget(self.listw)
        btn = QPushButton("انتخاب")
        btn.clicked.connect(self.on_select)
        v.addWidget(btn)

    def on_select(self):
        it = self.listw.currentItem()
        if not it:
            QMessageBox.warning(self, "هشدار", "لطفاً یک تعرفه انتخاب کنید.")
            return
        self.selected_rate_id = it.data(Qt.ItemDataRole.UserRole)
        self.accept()


class StartTimeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("زمان شروع سیستم")
        self.choice = None
        self.scheduled_time_str = None

        v = QVBoxLayout(self)
        v.addWidget(QLabel("همین حالا شروع کن یا زمان شروع را به صورت ساعت:دقیقه وارد کن."))

        self.immediate_btn = QPushButton("شروع فوری")
        self.schedule_btn = QPushButton("ثبت زمان")
        self.time_edit = QTimeEdit(QTime.currentTime())
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setKeyboardTracking(False)
        self.time_edit.setFocus()

        v.addWidget(self.immediate_btn)
        v.addWidget(self.schedule_btn)
        v.addWidget(QLabel("زمان شروع (HH:MM)"))
        v.addWidget(self.time_edit)

        self.immediate_btn.clicked.connect(self.on_immediate)
        self.schedule_btn.clicked.connect(self.on_schedule)

    def showEvent(self, event):
        # هر بار که دیالوگ باز می‌شود، حداکثر زمان را برابر زمان فعلی قرار بده
        now_qt = QTime.currentTime()
        self.time_edit.setMaximumTime(now_qt)
        # اگر مقدار فعلی time_edit بزرگ‌تر از now شده باشد، آن را به now تنظیم کن
        if self.time_edit.time() > now_qt:
            self.time_edit.setTime(now_qt)
        super().showEvent(event)

    def on_immediate(self):
        self.choice = 'immediate'
        self.accept()

    def on_schedule(self):
        qt = self.time_edit.time()
        hh = qt.hour()
        mm = qt.minute()
        # اعتبارسنجی نهایی: اگر کاربر به هر طریقی زمان آینده انتخاب کرد، هشدار بده
        from datetime import datetime
        now = datetime.now()
        chosen_dt = datetime(now.year, now.month, now.day, hh, mm, 0)
        if chosen_dt > now:
            QMessageBox.warning(self, "زمان نامعتبر", "نمی‌توانید زمان آینده انتخاب کنید. لطفاً زمان مساوی یا قبل از حال را انتخاب کنید.")
            return
        self.choice = 'schedule'
        self.scheduled_time_str = f"{hh:02d}:{mm:02d}"
        self.accept()



class SenderThread(QThread):
    # emits (success: bool, response_text: str)
    finished = pyqtSignal(bool, str)

    def __init__(self, url, data):
        super().__init__()
        self.url = url
        self.data = data

    def run(self):
        import requests
        try:
            r = requests.post(self.url, json=self.data, timeout=5, verify=certifi.where())
            ok = (200 <= r.status_code < 300)
            self.finished.emit(ok, r.text)
        except Exception as e:
            self.finished.emit(False, str(e))


class SubscriptionChecker(QThread):
    result = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, username):
        super().__init__()
        self.username = username

    def run(self):
        try:
            url = f"https://gamenet-server-mongo-production.up.railway.app/subscription/{self.username}"
            res = requests.get(url, timeout=6, verify=certifi.where())
            data = res.json()
            self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):

    def __init__(self, mode="online", username=None):
        super().__init__()

        # ------------------------------
        # Load UI
        # ------------------------------
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(__file__))

        uic.loadUi(os.path.join(base_path, "ui", "main_window.ui"), self)

        self.last_update_counter = 0
        try:
            with sqlite3.connect(database.DB_PATH, timeout=10) as _conn:
                _conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass

        self.icon_cache = {}
        self.preload_icons()

        # در init کلاس MainWindow مقداردهی اولیه (یک‌بار)
        self._running_sessions_map = {}
        self._scheduled_timer = None
        self._ui_timer = None
        self._scheduled_timer = None

        # نسبت ستون‌های متناسب (فقط ستون‌هایی که می‌خواهی کش بیایند)
        # کلید: شماره ستون؛ مقدار: وزن نسبی (هر عدد مثبت)
        self._col_ratios = {
            1: 18,   # customer
            2: 12,   # cost
            3: 8,    # elapsed
            9: 16,   # name
            11: 10   # controllers/rate
        }
        # ستون‌های با عرض ثابت (ستون: fixed_width_px)
        self._fixed_columns = {
            0: 90,   # checkout
            4: 110,  # snack
            5: 110,  # change
            6: 80,   # stop
            7: 80,   # start
            8: 60,   # status
            10: 80   # note (اگر دکمه است)
        }

        # تنظیم header تا setColumnWidth اثر کند
        header = self.systemTable.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setStretchLastSection(False)

        self._row_to_session = {}

        self.systemTable.setMouseTracking(False)
        self.systemTable.cellClicked.connect(self.on_system_table_cell_clicked)

        # ------------------------------
        # Mode & Username
        # ------------------------------
        self.mode = mode              # online / offline
        self.username = username
        self.send_data_online = (mode == "online")

        # ------------------------------
        # Statusbar Labels
        # ------------------------------
        self.lblSubscriptionInfo = QLabel("اشتراک: ---")
        self.lblSubscriptionInfo.setStyleSheet("font-size: 15px; color: #444; padding: 5px;")

        self.lblLastUpdate = QLabel("آخرین آپدیت: ---")
        self.lblLastUpdate.setStyleSheet("font-size: 15px; color: #444; padding: 5px;")

        self.statusbar.addPermanentWidget(self.lblSubscriptionInfo)
        self.statusbar.addPermanentWidget(self.lblLastUpdate)

        # ------------------------------
        # Menu Actions
        # ------------------------------
        self.actionOnlineLogin.triggered.connect(self.switch_to_online)
        self.actionOfflineLogin.triggered.connect(self.switch_to_offline)
        self.actionRenewSubscription.triggered.connect(self.renew_subscription)
        self.actionLogout.triggered.connect(self.logout)

        # ------------------------------
        # Buttons
        # ------------------------------
        self.btnAddSystem.triggered.connect(self.open_add_system)
        self.btnAddCustomer.triggered.connect(self.open_add_customer)
        self.btnChargeCustomer.triggered.connect(self.open_chgarge_customer)
        self.btnCustomerList.triggered.connect(self.open_customer_list)
        self.btnSnackList.triggered.connect(self.open_snack_list)
        self.btnSystemList.triggered.connect(self.open_system_list)
        self.btnUsername.triggered.connect(self.open_user_name)

        self._running_sessions_map = {}
        self.start_scheduled_timer()

        # ------------------------------
        # Initial Load
        # ------------------------------
        self.load_systems()

        self.detect_power_loss()

        # ------------------------------
        # Timers
        # ------------------------------
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tick)
        self.timer.start(1000)

        self.subscription_timer = QTimer()
        self.subscription_timer.timeout.connect(self.start_subscription_check)

        # ------------------------------
        # Mode Handling
        # ------------------------------
        if self.mode == "online":
            self.subscription_timer.start(3600 * 3000)  # هر 3 ساعت
            self.start_subscription_check()
            self.start_sender_timer()
        else:
            self.disable_online_features()


    def disable_online_features(self):
        self.send_data_online = False

        try:
            self.subscription_timer.stop()
        except:
            pass

        try:
            self.sender_timer.stop()
        except:
            pass

        self.lblSubscriptionInfo.setText("حالت آفلاین فعال است")


    def switch_to_online(self):
        QMessageBox.information(self, "تمدید اشتراک", "صفحه تغییر اشتراک بعداً اضافه می‌شود.")

    def switch_to_offline(self):
        QMessageBox.information(self, "تمدید اشتراک", "صفحه تغییر اشتراک بعداً اضافه می‌شود.")

    def renew_subscription(self):
        QMessageBox.information(self, "تمدید اشتراک", "صفحه تمدید اشتراک بعداً اضافه می‌شود.")

    def logout(self):
        if os.path.exists("credentials.txt"):
            os.remove("credentials.txt")
        if os.path.exists("license.key"):
            os.remove("license.key")

        QMessageBox.information(self, "خروج", "خروج انجام شد.")
        QCoreApplication.quit()


    def start_sender_timer(self):
        if self.mode == "offline":
            return

        self.sender_timer = QTimer()
        self.sender_timer.timeout.connect(self.send_update)
        self.sender_timer.start(5000)


    def lock_software(self):
        try:
            QMessageBox.critical(
                self,
                "اشتراک منقضی شده",
                "اشتراک شما منقضی شده است.\nنرم‌افزار بسته می‌شود."
            )

            QApplication.quit()

        except Exception as e:
            pass

    def handle_subscription_error(self, err):
        # تشخیص خطای SSL
        if "SSL" in err or "ssl" in err:
            QMessageBox.critical(self, "خطای SSL",
                "ارتباط امن با سرور برقرار نشد!")
            return

        # تشخیص بلاک شدن توسط فایروال
        if "Connection" in err or "Failed to establish" in err:
            QMessageBox.critical(self, "خطای اتصال",
                "درخواست چک اشتراک ارسال نشد!")
            return

        # تشخیص Timeout
        if "timed out" in err or "timeout" in err:
            QMessageBox.critical(self, "تایم‌اوت",
                "سرور در زمان مناسب پاسخ نداد!")
            return

        # خطای ناشناخته
        QMessageBox.critical(self, "خطای اشتراک",
            f"خطای غیرمنتظره در چک اشتراک:\n{err}")


    def handle_subscription_result(self, data):
        active = data.get("active", False)

        # گرفتن تاریخ
        expire = data.get("expireDate") or data.get("expire_date")

        # گرفتن روز مانده از API اگر وجود داشته باشد
        api_days = data.get("daysLeft") or data.get("days_left")

        # اگر API روز مانده را نداد → خودمان حساب می‌کنیم
        if api_days is None and expire:
            try:
                expire_dt = datetime.strptime(expire, "%Y-%m-%d")
                today = datetime.now()

                delta = expire_dt - today
                days_left = delta.days + 1

                if days_left < 0:
                    days_left = 0
            except:
                days_left = "نامشخص"
        else:
            days_left = api_days or "نامشخص"

        # نمایش در استاتوس بار
        if active:
            self.lblSubscriptionInfo.setText(
                f"مانده: {days_left} روز | پایان: {expire}"
            )
        else:
            self.lblSubscriptionInfo.setText("اشتراک منقضی شده")
            self.subscription_expired = True
            self.lock_software()

    def start_subscription_check(self):
        # حالت آفلاین → هیچ چکی انجام نشود
        if self.mode == "offline":
            return

        # اگر یوزرنیم نداریم → چک نکن
        if not self.username:
            return

        # شروع چک اشتراک با Thread
        self.sub_checker = SubscriptionChecker(self.username)
        self.sub_checker.result.connect(self.handle_subscription_result)
        self.sub_checker.error.connect(self.handle_subscription_error)
        self.sub_checker.start()


    def send_update(self):
        if self.mode == "offline":
            return

        if not self.username or not getattr(self, "gamenet_password", None):
            return

        systems_json = self.build_status_json()

        payload = {
            "password": self.gamenet_password,
            "systems": systems_json,
            "lastUpdate": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        url = f"https://gamenet-server-mongo-production.up.railway.app/status/{self.username}"

        # شروع thread و اتصال به handler
        self.thread = SenderThread(url, payload)
        self.thread.finished.connect(self._on_send_finished)
        self.thread.start()

    def _on_send_finished(self, success: bool, response_text: str):
        if success:
            last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.lblLastUpdate.setText(f"آخرین آپدیت: {last_update}")
        else:
            if "SSL" in response_text:
                self.statusbar.showMessage("خطای SSL در ارسال وضعیت", 5000)
            elif "Connection" in response_text or "Failed to establish" in response_text:
                self.statusbar.showMessage("اتصال به سرور برقرار نشد (فایروال؟)", 5000)
            elif "timeout" in response_text:
                self.statusbar.showMessage("تایم‌اوت در ارسال وضعیت", 5000)
            else:
                self.statusbar.showMessage("ارسال وضعیت ناموفق بود", 5000)

    def build_status_json(self):
        try:
            conn = database.get_connection()
        except Exception:
            conn = sqlite3.connect(database.DB_PATH, timeout=10)
        cur = conn.cursor()

        cur.execute("""
            SELECT id, name, active, note, customer_id, price_per_hour, cost
            FROM systems
        """)
        rows = cur.fetchall()

        data = {}

        for sys_id, name, active, note, customer_id, price_per_hour, transfer_cost in rows:

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
                    # ساعت سیستم ممکن است عقب/جلو تنظیم شده باشد؛ زمان منفی قابل نمایش نیست.
                    running_seconds = max(0, int((datetime.now() - start_dt).total_seconds()))
                    elapsed_seconds = max(0, int(paused_seconds or 0)) + running_seconds
                else:
                    elapsed_seconds = max(0, int(paused_seconds or 0))

                h = elapsed_seconds // 3600
                m = (elapsed_seconds % 3600) // 60
                s = elapsed_seconds % 60
                elapsed = f"{h:02}:{m:02}:{s:02}"

                try:
                    # controllers_count از سشن بخوان
                    cur.execute("SELECT controllers_count FROM sessions WHERE system_id=? AND end_time IS NULL LIMIT 1", (sys_id,))
                    rc = cur.fetchone()
                    controllers_count = rc[0] if rc and rc[0] is not None else 1

                    # اگر repository تو تابع get_price_per_hour دارد از آن استفاده کن
                    try:
                        from system_repository import get_price_per_hour, calc_session_cost_and_segments
                        price_per_hour_real = get_price_per_hour(conn, sys_id, controllers_count)
                        # برای دقت بیشتر می‌توانیم از calc_session_cost_and_segments استفاده کنیم:
                        total_cost, segments, accum_cost, accum_details = calc_session_cost_and_segments(
                            conn, session_id, sys_id, until_dt=datetime.now()
                        )
                        # total_cost شامل هزینه‌های تجمعی/انتقالی و بازه‌های فعلی است؛
                        # جمع کردن فقط segments باعث حذف هزینه‌های قبلی از گزارش آنلاین می‌شد.
                        time_cost = max(0, int(total_cost or 0))
                    except Exception:
                        # fallback ساده
                        time_cost = int(elapsed_seconds * (price_per_hour / 3600))
                except Exception:
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
                try:
                    # اطمینان از وجود جداول لازم
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('session_snacks','foods')")
                    existing = {r[0] for r in cur.fetchall()}
                    if 'session_snacks' not in existing or 'foods' not in existing:
                        raise sqlite3.OperationalError("required tables missing")

                    # کوئری مستقیم و ساده بر اساس schema جدید
                    cur.execute("""
                        SELECT COALESCE(ss.name_snapshot, f.name, 'خوراکی حذف‌شده') AS name,
                               COALESCE(ss.price_snapshot, f.price, 0) AS price, ss.quantity AS qty
                        FROM session_snacks ss
                        LEFT JOIN foods f ON f.id = ss.snack_id
                        WHERE ss.session_id = ?
                    """, (session_id,))

                    rows = cur.fetchall()
                    for name, price, qty in rows:
                        # تبدیل امن قیمت و تعداد به عدد صحیح
                        try:
                            if price is None:
                                price_val = 0
                            elif isinstance(price, (int, float)):
                                price_val = int(price)
                            else:
                                price_val = int(str(price).replace(",", "").strip() or 0)
                        except Exception:
                            price_val = 0

                        try:
                            qty_val = int(qty or 0)
                        except Exception:
                            qty_val = 0

                        subtotal = price_val * qty_val
                        snacks.append({"name": name, "price": price_val, "qty": qty_val, "subtotal": subtotal})
                        snacks_total += subtotal

                except sqlite3.OperationalError as e:
                    # جدول وجود ندارد یا schema تغییر کرده؛ لاگ کن و ادامه بده
                    snacks = []
                    snacks_total = 0
                except Exception as e:
                    # سایر خطاها را لاگ کن ولی برنامه کرش نکند
                    snacks = []
                    snacks_total = 0

            final_total = time_cost + snacks_total + transfer_cost

            # ⭐ اضافه کردن هزینه سیستم قبلی ⭐
            data[name] = {
                "name": name,
                "active": active,
                "elapsed": elapsed,
                "time_cost": time_cost,
                "snacks": snacks,
                "snacks_total": snacks_total,
                "transfer_cost": transfer_cost,   # ← این خط جدید
                "final_total": final_total,
                "note": note,
                "customer": customer_info,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        conn.close()
        return data

    def detect_power_loss(self, threshold_seconds=5):
        try:
            conn = database.get_connection()
        except Exception:
            conn = sqlite3.connect(database.DB_PATH, timeout=10)
        cur = conn.cursor()

        cur.execute("SELECT id, active, last_update_time FROM systems WHERE active IN (1, 2)")
        systems = cur.fetchall()

        now = datetime.now()
        power_loss_detected = False

        for sys_id, active, last_update_time in systems:
            if not last_update_time:
                # اگر last_update_time موجود نیست، نادیده بگیر
                continue

            # پارس ایمن last_update_time
            try:
                last_dt = datetime.strptime(last_update_time, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue

            diff = int((now - last_dt).total_seconds())

            if diff > threshold_seconds:
                power_loss_detected = True

                # گرفتن سشن فعال (آخرین سشن فعال)
                cur.execute("""
                    SELECT id, start_time, paused_seconds
                    FROM sessions
                    WHERE system_id=? AND end_time IS NULL
                    ORDER BY id DESC LIMIT 1
                """, (sys_id,))
                session = cur.fetchone()

                if session:
                    session_id = session[0]
                    try:
                        # Save both elapsed time and accrued money before clearing
                        # start_time. Otherwise resume keeps the timer but starts
                        # billing at zero after a power loss/app restart.
                        repo.recover_interrupted_session(conn, session_id, sys_id, last_dt)
                    except Exception:
                        # Keep this system active in the database if recovery fails;
                        # a later startup can retry rather than losing the cost.
                        conn.rollback()
                        continue

                # Mark as paused only after session recovery succeeds.
                cur.execute("UPDATE systems SET active=2 WHERE id=?", (sys_id,))

        try:
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return power_loss_detected

    def status_item(self , active):
        item = QTableWidgetItem("")
        if active == 0:
            item.setBackground(QColor("#ff2b40"))
        elif active == 1:
            item.setBackground(QColor("#00b953"))
        else:
            item.setBackground(QColor("#0084ff"))

        return item

    def safe_sort_key(self , name):
        # بخش حروفی
        alpha = re.sub(r'\d+', '', name).strip().lower()

        # بخش عددی
        nums = re.findall(r'\d+', name)
        num = int(nums[0]) if nums else 0

        return (alpha, num)

    def update_tick(self):
        try:
            # 1) هر 5 ثانیه یک‌بار last_update_time را بنویس
            self.last_update_counter += 1
            if self.last_update_counter >= 5:
                try:
                    with sqlite3.connect(database.DB_PATH, timeout=10) as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE systems SET last_update_time=? WHERE active IN (1, 2)",
                            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
                        )
                        conn.commit()
                except Exception as e:
                    pass
                finally:
                    self.last_update_counter = 0

            # 2) خواندن کلی systems (یک SELECT ساده)
            try:
                conn = sqlite3.connect(database.DB_PATH, timeout=10)
                cur = conn.cursor()
                cur.execute("SELECT id FROM systems")
                db_ids = {r[0] for r in cur.fetchall()}
                conn.close()
            except Exception as e:
                db_ids = set()

            # 3) اگر تعداد یا شناسه‌ها تغییر کرده بود -> full reload
            current_ids = set(self.system_row_map.keys()) if hasattr(self, "system_row_map") else set()
            if db_ids != current_ids:
                # structural change: اضافه/حذف سیستم
                try:
                    self.load_systems()
                except Exception as e:
                    pass
            else:

                try:
                    if hasattr(self, "update_ui_tick"):
                        self.update_ui_tick()
                except Exception as e:
                    pass

        except Exception as e:
            pass

    def get_icon(self, path):
        if path in self.icon_cache:
            return self.icon_cache[path]
        pix = QPixmap(path)
        icon = QIcon(pix)
        self.icon_cache[path] = icon
        return icon

    def preload_icons(self):
        icons = [
            "icons/start.png",
            "icons/stop.png",
            "icons/checkout.png",
            "icons/snack.png",
            "icons/edit.png",
            "icons/note.png"
        ]
        for p in icons:
            try:
                self.get_icon(p)
            except Exception:
                pass

    def recolor_rows(self, color1="#1a1a1a", color2="#0d1114"):
        rows = self.systemTable.rowCount()
        cols = self.systemTable.columnCount()

        skip_columns = {8}

        for r in range(rows):
            row_color = color1 if (r % 2 == 0) else color2
            qcolor = QColor(row_color)
            for c in range(cols):
                if c in skip_columns:
                    continue

                # ست کردن یا ساخت QTableWidgetItem
                item = self.systemTable.item(r, c)
                if item is None:
                    item = QTableWidgetItem("")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.systemTable.setItem(r, c, item)
                item.setBackground(qcolor)

                # اگر cellWidget وجود دارد، پس‌زمینهٔ آن را هم ست کن
                widget = self.systemTable.cellWidget(r, c)
                if widget is not None:
                    try:
                        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                    except Exception:
                        pass
                    widget.setStyleSheet(f"background-color: {row_color}; border: none;")

    def make_icon_button(self, icon_path, icon_size=(28, 28)):
        btn = QPushButton()
        btn.setFlat(True)
        btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        btn.setStyleSheet("border: none; background-color: transparent;")
        btn.setIcon(self.get_icon(icon_path))
        btn.setIconSize(QSize(icon_size[0], icon_size[1]))
        return btn

    def update_table_column_widths(self):
        # عرض قابل استفاده viewport جدول
        avail_w = self.systemTable.viewport().width()
        if avail_w <= 0:
            return

        # جمع عرض ثابت‌ها
        total_fixed = sum(self._fixed_columns.get(c, 0) for c in range(self.systemTable.columnCount()))
        # فضای قابل تقسیم برای ستون‌های متناسب
        flexible_space = max(0, avail_w - total_fixed)

        # جمع نسبت‌ها فقط برای ستون‌هایی که در جدول وجود دارند
        ratios = {c: r for c, r in self._col_ratios.items() if c < self.systemTable.columnCount()}
        total_ratio = sum(ratios.values()) or 1

        # محاسبه عرض برای هر ستون
        for col in range(self.systemTable.columnCount()):
            if col in self._fixed_columns:
                w = self._fixed_columns[col]
            elif col in ratios:
                w = int((ratios[col] / total_ratio) * flexible_space)
                # حداقل عرض اختیاری
                min_w = 60
                if w < min_w:
                    w = min_w
            else:
                # ستون‌هایی که نه ثابت‌اند و نه در ratios تعریف شده‌اند
                # آنها را به صورت کوچک نگه می‌داریم یا سهمی از flexible_space می‌دهیم
                w = 80

            # اعمال عرض فقط اگر ستون وجود داشته باشد
            if col < self.systemTable.columnCount():
                self.systemTable.setColumnWidth(col, w)

    def on_system_table_cell_clicked(self, row, col):
        try:
            RATE_COL = 11   # شماره ستون تعرفه را با جدول خودت تطبیق بده
            if col != RATE_COL:
                return

            sys_id = getattr(self, "system_row_map", {}).get(row)
            if not sys_id:
                QMessageBox.information(self, "خطا", "شناسه سیستم پیدا نشد برای این ردیف.")
                return

            # استفاده از اتصال مرکزی (تغییر بده اگر نام تابع تو فرق دارد)
            try:
                conn = database.get_connection()
            except Exception:
                conn = sqlite3.connect(database.DB_PATH, timeout=10)

            try:
                cur = conn.cursor()
                cur.execute("SELECT id, controllers_count, price_per_hour, name FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC", (sys_id,))
                rates = cur.fetchall()

                if not rates:
                    QMessageBox.information(self, "بدون تعرفه", "برای این سیستم هیچ تعرفه‌ای تعریف نشده است.")
                    return

                dlg = RateSelectDialog(rates, self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return

                new_rate_id = dlg.selected_rate_id
                if not new_rate_id:
                    QMessageBox.warning(self, "هشدار", "تعرفه‌ای انتخاب نشده یا شناسه نامعتبر است.")
                    return

                # پاس دادن همان conn به repository
                try:
                    repo.change_rate_mid_session(conn, sys_id, new_rate_id)
                    try:
                        conn.commit()
                    except Exception:
                        pass
                except Exception as e:
                    QMessageBox.warning(self, "خطا", f"خطا در تغییر تعرفه: {e}")
                    return

                try:
                    self.load_systems()
                except Exception as e:
                    pass

                QMessageBox.information(self, "تعرفه تغییر کرد", "تعرفه با موفقیت تغییر کرد.")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"خطای داخلی: {e}")

    def open_rate_selector_and_apply(self, sys_id):
        try:
            conn = database.get_connection()
        except Exception:
            conn = sqlite3.connect(database.DB_PATH, timeout=10)

        try:
            cur = conn.cursor()
            cur.execute("SELECT id, controllers_count, price_per_hour, name FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC", (sys_id,))
            rates = cur.fetchall()

            if not rates:
                QMessageBox.information(self, "تعرفه", "برای این سیستم تعرفه‌ای تعریف نشده است.")
                return

            dlg = RateSelectDialog(rates, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                selected_rate_id = dlg.selected_rate_id
                if not selected_rate_id:
                    QMessageBox.warning(self, "هشدار", "تعرفه‌ای انتخاب نشده.")
                    return

                try:
                    repo.change_rate_mid_session(conn, sys_id, selected_rate_id)
                    try:
                        conn.commit()
                    except Exception:
                        pass
                except Exception as e:
                    QMessageBox.warning(self, "خطا", f"خطا در تغییر تعرفه: {e}")
                    return

                try:
                    self.load_systems()
                except Exception:
                    pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def load_systems(self):
        systems = get_systems()
        systems.sort(key=lambda s: self.safe_sort_key(s[1]))
        self.systemTable.setRowCount(len(systems))

        self.system_row_map = {}

        for row, sys in enumerate(systems):
            sys_id, name, active, start_time, elapsed, cost, customer_id, note, controllers_count, price_per_hour = sys
            # یادداشت
            note_btn = self.make_icon_button("icons/note.png", (28,28))
            note_btn.clicked.connect(lambda _, sid=sys_id: self.note_system(sid))
            note_btn.setEnabled(active in (1, 2))
            self.systemTable.setCellWidget(row, 10, note_btn)
            self.systemTable.setColumnWidth(10, 80)

            # نام سیستم
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 9, item)
            self.systemTable.setColumnWidth(9, 200)

            # وضعیت
            self.systemTable.setItem(row, 8, self.status_item(active))
            self.systemTable.setColumnWidth(8, 60)

            # دکمه استارت
            start_btn = self.make_icon_button("icons/start.png", (28,28))
            start_btn.clicked.connect(lambda _, sid=sys_id: self.start_system(sid))
            start_btn.setEnabled(active != 1)
            self.systemTable.setCellWidget(row, 7, start_btn)
            self.systemTable.setColumnWidth(7, 80)

            # دکمه استاپ
            stop_btn = self.make_icon_button("icons/stop.png", (30,30))
            stop_btn.clicked.connect(lambda _, sid=sys_id: self.stop_system(sid))
            self.systemTable.setCellWidget(row, 6, stop_btn)
            self.systemTable.setColumnWidth(6, 80)

            # دکمه تغییر سیستم
            change_btn = self.make_icon_button("icons/edit.png", (30,30))
            change_btn.clicked.connect(lambda _, sid=sys_id: self.change_system(sid))
            self.systemTable.setCellWidget(row, 5, change_btn)
            self.systemTable.setColumnWidth(5, 110)

            # دکمه خوراکی
            snack_btn = self.make_icon_button("icons/snack.png", (30,30))
            snack_btn.clicked.connect(lambda _, sid=sys_id: self.add_snack(sid))
            self.systemTable.setCellWidget(row, 4, snack_btn)
            self.systemTable.setColumnWidth(4, 110)

            # زمان سپری‌شده
            item_elapsed = QTableWidgetItem(elapsed)
            item_elapsed.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 3, item_elapsed)
            self.systemTable.setColumnWidth(3, 100)

            # هزینه (فرمت ایمن بدون نیاز به متد format_price)
            try:
                cost_text = f"{int(cost):,}"
            except Exception:
                try:
                    cost_text = f"{int(float(cost)):,}"
                except Exception:
                    cost_text = str(cost or 0)
            item_cost = QTableWidgetItem(cost_text)
            item_cost.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 2, item_cost)
            self.systemTable.setColumnWidth(2, 150)

            # دکمه تسویه
            checkout_btn = self.make_icon_button("icons/checkout.png", (28,28))
            checkout_btn.clicked.connect(lambda _, sid=sys_id: self.checkout(sid))
            self.systemTable.setCellWidget(row, 0, checkout_btn)
            self.systemTable.setColumnWidth(0, 90)

            # گرفتن نام مشتری
            try:
                conn = database.get_connection()
            except Exception:
                conn = sqlite3.connect(database.DB_PATH, timeout=10)
            cur = conn.cursor()
            cur.execute("""
                SELECT customers.name, customers.family, customers.code
                FROM systems
                LEFT JOIN customers ON customers.id = systems.customer_id
                WHERE systems.id=?
            """, (sys_id,))
            customer = cur.fetchone()
            conn.close()

            if customer and customer[0] is not None:
                cname = f"{customer[0]} {customer[1]} - {customer[2]}"
            else:
                cname = "متفرقه"

            item_customer = QTableWidgetItem(cname)
            item_customer.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 1, item_customer)
            self.systemTable.setColumnWidth(1, 200)

            # ----- نمایش نام تعرفه یا متن "بدون تعرفه" در ستون 11 -----
            try:
                cc = int(controllers_count) if controllers_count is not None else 1
            except Exception:
                cc = 1

            # ----- نمایش نام تعرفه یا متن "بدون تعرفه" در ستون 11 -----
            display_text = "بدون تعرفه"
            tooltip_lines = []

            try:
                # اتصال امن به DB
                conn2 = get_connection()
                cur2 = conn2.cursor()

                # 1) تلاش برای یافتن سشن فعال و نام تعرفهٔ اعمال‌شده برای آن سشن
                cur2.execute("SELECT id FROM sessions WHERE system_id=? AND end_time IS NULL ORDER BY id DESC LIMIT 1", (sys_id,))
                srow = cur2.fetchone()
                current_rate_name = None
                if srow:
                    sid = srow[0]
                    cur2.execute("SELECT new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC LIMIT 1", (sid,))
                    rr = cur2.fetchone()
                    if rr and rr[0]:
                        cur2.execute("SELECT name FROM ps_rates WHERE id=? LIMIT 1", (rr[0],))
                        rn = cur2.fetchone()
                        if rn and rn[0]:
                            current_rate_name = rn[0]

                # 2) اگر نام تعرفهٔ سشن پیدا شد، آن را نمایش بده
                if current_rate_name:
                    display_text = str(current_rate_name)
                else:
                    # fallback: نمایش اولین تعرفهٔ سیستم یا "بدون تعرفه"
                    cur2.execute(
                        "SELECT controllers_count, price_per_hour, name FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC",
                        (sys_id,)
                    )
                    rates = cur2.fetchall()
                    if rates:
                        first = rates[0]
                        first_name = first[2] if len(first) > 2 else None
                        if first_name and str(first_name).strip() != "":
                            display_text = str(first_name)
                        else:
                            display_text = "بدون تعرفه"

                        # ساخت tooltip از همهٔ تعرفه‌ها
                        for r in rates:
                            r_cnt = r[0]
                            r_name = r[2] if len(r) > 2 else None
                            if r_name and str(r_name).strip() != "":
                                tooltip_lines.append(f"{r_name}")
                            else:
                                tooltip_lines.append(f"{r_cnt} دسته")
                    else:
                        display_text = "بدون تعرفه"

            except Exception:
                # در صورت خطا، نمایش پیش‌فرض باقی می‌ماند
                display_text = "بدون تعرفه"
                tooltip_lines = []
            finally:
                try:
                    conn2.close()
                except Exception:
                    pass

            item_controllers = QTableWidgetItem(display_text)
            item_controllers.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if tooltip_lines:
                item_controllers.setToolTip("\n".join(tooltip_lines))

            self.systemTable.setItem(row, 11, item_controllers)
            self.systemTable.setColumnWidth(11, 200)

            self.system_row_map[row] = sys_id

        self.recolor_rows()
        self.update_table_column_widths()

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
        finally:
            # به‌محض اینکه جدول اندازه جدید دارد، عرض‌ها را بروزرسانی کن
            try:
                self.update_table_column_widths()
            except Exception:
                pass

    def note_system(self, sys_id):
        try:
            conn = database.get_connection()
        except Exception:
            conn = sqlite3.connect(database.DB_PATH, timeout=10)
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


    # متدهای کمکی تایمر UI (اضافه کن به کلاس اصلی)
    def _ensure_ui_timer_running(self):
        if getattr(self, "_ui_timer", None) is not None:
            return
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(1000)
        self._ui_timer.timeout.connect(self._ui_timer_tick)
        self._ui_timer.start()

    def _ui_timer_tick(self):
        if not getattr(self, "_running_sessions_map", None):
            return
        now = datetime.now()
        for session_id, start_dt in list(self._running_sessions_map.items()):
            elapsed = int((now - start_dt).total_seconds())
            if elapsed < 0:
                elapsed = 0
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            timestr = f"{h:02d}:{m:02d}:{s:02d}"
            try:
                self.update_system_timer_display(session_id, timestr)
            except Exception:
                pass

    # تایمر بررسی زمان‌بندی (بدون تغییر DB)
    def start_scheduled_timer(self, interval_seconds=5):
        if getattr(self, "_scheduled_timer", None) is not None:
            return
        self._scheduled_timer = QTimer(self)
        self._scheduled_timer.setInterval(max(1000, int(interval_seconds * 1000)))
        self._scheduled_timer.timeout.connect(self.check_scheduled_sessions)
        self._scheduled_timer.start()

    def check_scheduled_sessions(self):
        try:
            conn = database.get_connection()
        except Exception:
            conn = sqlite3.connect(database.DB_PATH, timeout=10)
        cur = conn.cursor()
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                SELECT s.id, s.system_id, s.start_time
                FROM sessions s
                LEFT JOIN systems sy ON sy.id = s.system_id
                WHERE s.start_time IS NOT NULL
                AND s.end_time IS NULL
                AND datetime(s.start_time) <= datetime(?)
                AND (sy.active IS NULL OR sy.active != 1)
            """, (now_str,))
            rows = cur.fetchall()
            for session_id, system_id, start_time in rows:
                try:
                    cur.execute("UPDATE systems SET active=1, last_update_time=? WHERE id=?", (now_str, system_id))
                    conn.commit()
                    if not hasattr(self, "_running_sessions_map"):
                        self._running_sessions_map = {}
                    try:
                        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        start_dt = datetime.now()
                    self._running_sessions_map[session_id] = start_dt
                    self._ensure_ui_timer_running()
                except Exception as e:
                    conn.rollback()
        finally:
            conn.close()

    def show_rate_picker_for_session(self, conn, session_id, sys_id, controllers_count=1, effective_from: str = None):
        cur = conn.cursor()
        try:
            # خواندن همه تعرفه‌های مرتبط با سیستم
            cur.execute("SELECT id, controllers_count, price_per_hour, name FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC", (sys_id,))
            rates = cur.fetchall()
        except Exception:
            rates = []

        # سیستم تک‌نرخی از systems.price_per_hour استفاده می‌کند؛
        # صفر یعنی «تعرفهٔ ps_rates ندارد اما نرخ پایه معتبر است» و نباید با لغو دیالوگ اشتباه شود.
        if not rates:
            try:
                cur.execute("SELECT price_per_hour FROM systems WHERE id=? LIMIT 1", (sys_id,))
                r = cur.fetchone()
                if r and r[0] is not None:
                    return 0
            except Exception:
                pass
            QMessageBox.information(self, "تعرفه", "برای این سیستم نرخ معتبری تعریف نشده است.")
            return None

        # اگر فقط یک تعرفه وجود دارد، آن را به عنوان پیش‌فرض انتخاب کن بدون نمایش دیالوگ
        if len(rates) == 1:
            chosen_rate_id = rates[0][0]
            now_for_change = effective_from if effective_from else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                cur.execute("SELECT new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC LIMIT 1", (session_id,))
                rcur = cur.fetchone()
                old_rate_id = rcur[0] if rcur else None
                cur.execute(
                    "INSERT INTO session_rate_changes (session_id, old_rate_id, new_rate_id, changed_at, source_system_id, source_note) VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, old_rate_id, chosen_rate_id, now_for_change, None, "پیش‌فرض تک تعرفه")
                )
                conn.commit()
                return chosen_rate_id
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return None

        # چند تعرفه وجود دارد؛ نمایش دیالوگ انتخاب
        dlg = QDialog(self)
        dlg.setWindowTitle("انتخاب تعرفه")
        dlg.resize(200,100)
        layout = QVBoxLayout(dlg)
        combo = QComboBox()
        for r in rates:
            rid = r[0]
            rname = r[3] if len(r) > 3 and r[3] else f"{r[1]} دسته - {int(r[2]) if r[2] else 0} تومان/ساعت"
            combo.addItem(rname, rid)
        layout.addWidget(combo)
        btn_ok = QPushButton("انتخاب"); btn_cancel = QPushButton("لغو")
        h = QHBoxLayout(); h.addWidget(btn_ok); h.addWidget(btn_cancel); layout.addLayout(h)
        btn_ok.clicked.connect(dlg.accept); btn_cancel.clicked.connect(dlg.reject)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        chosen_rate_id = combo.currentData()
        now_for_change = effective_from if effective_from else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cur.execute("SELECT new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC LIMIT 1", (session_id,))
            rcur = cur.fetchone()
            old_rate_id = rcur[0] if rcur else None
            cur.execute(
                "INSERT INTO session_rate_changes (session_id, old_rate_id, new_rate_id, changed_at, source_system_id, source_note) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, old_rate_id, chosen_rate_id, now_for_change, None, "انتخاب قبل از استارت")
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return None

        return chosen_rate_id


    # بازنویسی تابع start_system (جایگزین تابع فعلی کن)
    def start_system(self, sys_id):
        try:
            conn = database.get_connection()
        except Exception:
            conn = sqlite3.connect(database.DB_PATH, timeout=10)

        try:
            cur = conn.cursor()

            # بررسی وجود سیستم و وضعیت
            cur.execute("SELECT active, customer_id, price_per_hour FROM systems WHERE id=?", (sys_id,))
            row = cur.fetchone()
            if not row:
                QMessageBox.warning(self, "خطا", "سیستم پیدا نشد.")
                try:
                    conn.close()
                except Exception:
                    pass
                return
            active, previous_customer_id, system_price = row

            # اگر سیستم paused است: resume با حفظ paused_seconds
            if active == 2:
                now = datetime.now()
                cur.execute("SELECT id, paused_seconds FROM sessions WHERE system_id=? AND end_time IS NULL ORDER BY id DESC LIMIT 1", (sys_id,))
                s = cur.fetchone()
                if s:
                    session_id = s[0]
                    paused_seconds = to_int_safe(s[1], 0)

                    # اگر برای این سشن هنوز rate ثبت نشده، ثبت پیش‌فرض با changed_at = new_start_str
                    try:
                        cur.execute("SELECT new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC LIMIT 1", (session_id,))
                        rr = cur.fetchone()
                        if not rr or not rr[0]:
                            cur2 = conn.cursor()
                            cur2.execute("SELECT id FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC LIMIT 1", (sys_id,))
                            r0 = cur2.fetchone()
                            new_start = now
                            new_start_str = new_start.strftime("%Y-%m-%d %H:%M:%S")
                            if r0 and r0[0]:
                                cur.execute(
                                    "INSERT INTO session_rate_changes (session_id, old_rate_id, new_rate_id, changed_at, source_note) VALUES (?, ?, ?, ?, ?)",
                                    (session_id, None, r0[0], new_start_str, "پیش‌فرض در resume")
                                )
                            # سیستم تک‌تعرفه‌ای از systems.price_per_hour استفاده می‌کند؛
                            # new_rate_id در این جدول اجباری است، پس برای این حالت رکوردی درج نمی‌کنیم.
                            conn.commit()
                    except Exception:
                        try:
                            conn.rollback()
                        except Exception:
                            pass

                    # تنظیم start_time طوری که زمان قبلی حفظ شود
                    # Accrued cost is already stored in sessions.cost; resume billing
                    # from now to avoid charging the paused interval twice. Keep the
                    # accumulated elapsed seconds for the UI timer.
                    new_start = now
                    new_start_str = new_start.strftime("%Y-%m-%d %H:%M:%S")

                    try:
                        cur.execute("UPDATE sessions SET start_time=?, paused_seconds=? WHERE id=?", (new_start_str, paused_seconds, session_id))
                        cur.execute("UPDATE systems SET active=1, last_update_time=? WHERE id=?", (new_start_str, sys_id))
                        conn.commit()
                    except Exception:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass
                        QMessageBox.warning(self, "خطا", "خطا در ادامهٔ سشن هنگام resume.")
                        return
                    if not hasattr(self, "_running_sessions_map"):
                        self._running_sessions_map = {}
                    self._running_sessions_map[session_id] = new_start
                    self._ensure_ui_timer_running()
                    self.load_systems()
                    return

            # اگر سیستم از قبل فعال است، اخطار بده
            cur.execute("SELECT active FROM systems WHERE id=?", (sys_id,))
            active_row = cur.fetchone()
            if not active_row:
                QMessageBox.warning(self, "خطا", "سیستم پیدا نشد.")
                try:
                    conn.close()
                except Exception:
                    pass
                return
            if active_row[0] == 1:
                QMessageBox.warning(self, "خطا", "این سیستم هم‌اکنون فعال است.")
                try:
                    conn.close()
                except Exception:
                    pass
                return

            # دفاع در عمق: وضعیت active ممکن است به‌علت بسته‌شدن ناگهانی برنامه
            # با وضعیت سشن‌ها ناسازگار شده باشد. برای سیستم آزاد، سشن باز جدید نساز.
            cur.execute(
                "SELECT id FROM sessions WHERE system_id=? AND end_time IS NULL ORDER BY id DESC LIMIT 1",
                (sys_id,),
            )
            dangling_session = cur.fetchone()
            if dangling_session:
                QMessageBox.warning(
                    self,
                    "سشن قبلی باز است",
                    "برای این سیستم یک سشن پایان‌نیافته وجود دارد. ابتدا وضعیت آن را بازیابی یا تعیین تکلیف کنید.",
                )
                try:
                    conn.close()
                except Exception:
                    pass
                return

            # انتخاب نوع کاربر (customer یا guest)
            mode_dlg = QDialog(self)
            mode_dlg.setWindowTitle("انتخاب نوع کاربر")
            v = QVBoxLayout(mode_dlg)
            rb_customer = QRadioButton("حساب کاربری (مشتری)")
            rb_guest = QRadioButton("متفرقه")
            rb_guest.setChecked(True)
            v.addWidget(rb_customer); v.addWidget(rb_guest)
            btn_mode = QPushButton("ادامه"); btn_mode.clicked.connect(mode_dlg.accept)
            v.addWidget(btn_mode)
            if mode_dlg.exec() != QDialog.DialogCode.Accepted:
                try:
                    conn.close()
                except Exception:
                    pass
                return

            mode = "customer" if rb_customer.isChecked() else "guest"
            customer_id = None
            controllers_count = 1

            if mode == "customer":
                # انتخاب مشتری (همان پیاده‌سازی قبلی)
                cdlg = QDialog(self)
                cdlg.setWindowTitle("انتخاب مشتری")
                clayout = QVBoxLayout(cdlg)
                search = QLineEdit(); search.setPlaceholderText("جستجو مشتری...")
                clayout.addWidget(search)
                ccombo = QComboBox(); clayout.addWidget(ccombo)
                cur.execute("SELECT id, name, family, code FROM customers")
                customers = cur.fetchall()
                if not customers:
                    QMessageBox.warning(self, "خطا", "هیچ مشتری ثبت نشده است.")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return
                names = [f"{name} {family} - {code}" for cid, name, family, code in customers]
                completer = QCompleter(names); completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                search.setCompleter(completer)
                def update_list():
                    text = search.text().strip()
                    ccombo.clear()
                    for cid, name, family, code in customers:
                        full = f"{name} {family} - {code}"
                        if text == "" or text in full:
                            ccombo.addItem(full, cid)
                search.textChanged.connect(update_list); update_list()
                cbtn = QPushButton("انتخاب"); cbtn.clicked.connect(cdlg.accept); clayout.addWidget(cbtn)
                if cdlg.exec() != QDialog.DialogCode.Accepted:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return
                customer_id = ccombo.currentData()
                cur.execute("SELECT COUNT(*) FROM sessions WHERE customer_id=? AND end_time IS NULL", (customer_id,))
                active_sessions = cur.fetchone()[0]
                if active_sessions > 0:
                    QMessageBox.warning(self, "خطا", "این مشتری هم‌اکنون در یک سیستم دیگر فعال است.")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return
                cur.execute("UPDATE systems SET customer_id=? WHERE id=?", (customer_id, sys_id))
                conn.commit()
            else:
                cur.execute("UPDATE systems SET customer_id=NULL WHERE id=?", (sys_id,))
                conn.commit()
                # ساخت سشن جدید (start_time را فعلاً None می‌گذاریم)
            cur.execute("INSERT INTO sessions (system_id, customer_id, start_time, paused_seconds) VALUES (?, ?, ?, 0)",
                        (sys_id, customer_id, None))
            session_id = cur.lastrowid
            conn.commit()

            # --- ثبت تعرفه پیش‌فرض یا نمایش دیالوگ انتخاب تعرفه ---
            # استفاده از متد کمکی اگر وجود دارد، در غیر این صورت رفتار fallback انجام می‌شود.
            chosen_rate = None
            try:
                # اگر متد show_rate_picker_for_session در کلاس وجود دارد از آن استفاده کن
                if hasattr(self, "show_rate_picker_for_session"):
                    chosen_rate = self.show_rate_picker_for_session(conn, session_id, sys_id, controllers_count=controllers_count, effective_from=None)
                else:
                    # fallback ساده: اگر فقط یک ps_rate هست، آن را ثبت کن؛ اگر هیچ ps_rate نیست، ثبت fallback با new_rate_id=NULL
                    cur.execute("SELECT id FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC", (sys_id,))
                    rates = cur.fetchall()
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if not rates:
                        # تک‌تعرفه‌ای: نرخ از systems.price_per_hour محاسبه می‌شود و رکورد NULL مجاز نیست.
                        chosen_rate = 0
                    elif len(rates) == 1:
                        cur.execute("INSERT INTO session_rate_changes (session_id, old_rate_id, new_rate_id, changed_at, source_note) VALUES (?, ?, ?, ?, ?)",
                                    (session_id, None, rates[0][0], now_str, "پیش‌فرض تک تعرفه"))
                        conn.commit()
                        chosen_rate = rates[0][0]
                    else:
                        # اگر چند تعرفه هست، بهتر است دیالوگ انتخاب را نمایش دهی؛ اما برای سازگاری اینجا fallback = None
                        chosen_rate = None
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                chosen_rate = None

            # اگر کاربر لغو کرده و chosen_rate is None => حذف سشن و بازگشت
            if chosen_rate is None:
                try:
                    cur.execute("DELETE FROM session_rate_changes WHERE session_id=?", (session_id,))
                    cur.execute("DELETE FROM session_snacks WHERE session_id=?", (session_id,))
                    cur.execute("DELETE FROM sessions WHERE id=?", (session_id,))
                    conn.commit()
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                try:
                    conn.close()
                except Exception:
                    pass
                self.load_systems()
                return

            # بستن کانکشن فعلی و ادامه برای انتخاب زمان شروع
            try:
                conn.close()
            except Exception:
                pass

            # نمایش دیالوگ زمان (StartTimeDialog)
            dlg = StartTimeDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                # لغو پنجرهٔ زمان باید شروع نیمه‌کاره را کاملاً پاک کند؛ در غیر این صورت
                # سشن باز با start_time=NULL باقی می‌ماند و شروع بعدی همین سیستم را مسدود می‌کند.
                try:
                    conn2 = database.get_connection()
                except Exception:
                    conn2 = sqlite3.connect(database.DB_PATH, timeout=10)
                try:
                    cur2 = conn2.cursor()
                    cur2.execute("DELETE FROM session_rate_changes WHERE session_id=?", (session_id,))
                    cur2.execute("DELETE FROM session_snacks WHERE session_id=?", (session_id,))
                    cur2.execute("DELETE FROM sessions WHERE id=? AND end_time IS NULL", (session_id,))
                    # اگر کاربر در همین تلاش مشتری را به سیستم وصل کرده بود، در لغو استارت اتصال را هم پاک کن.
                    cur2.execute("UPDATE systems SET customer_id=?, active=0 WHERE id=? AND active=0", (previous_customer_id, sys_id))
                    conn2.commit()
                except Exception:
                    try:
                        conn2.rollback()
                    except Exception:
                        pass
                finally:
                    try:
                        conn2.close()
                    except Exception:
                        pass
                self.load_systems()
                return
            # دوباره اتصال برای نوشتن start_time نهایی و همگام‌سازی changed_at در صورت زمان گذشته
            try:
                conn = database.get_connection()
            except Exception:
                conn = sqlite3.connect(database.DB_PATH, timeout=10)
            cur = conn.cursor()

            try:
                now = datetime.now()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")

                if dlg.choice == 'immediate':
                    # اگر هنوز rate برای این session ثبت نشده (نادر)، ثبت fallback با changed_at = now_str
                    try:
                        cur.execute("SELECT new_rate_id FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC LIMIT 1", (session_id,))
                        rr = cur.fetchone()
                        if not rr or not rr[0]:
                            cur2 = conn.cursor()
                            cur2.execute("SELECT id FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC LIMIT 1", (sys_id,))
                            r0 = cur2.fetchone()
                            if r0 and r0[0]:
                                cur.execute("INSERT INTO session_rate_changes (session_id, old_rate_id, new_rate_id, changed_at, source_note) VALUES (?, ?, ?, ?, ?)",
                                            (session_id, None, r0[0], now_str, "پیش‌فرض در immediate"))
                            # در حالت تک‌تعرفه‌ای، نرخ پایه در systems.price_per_hour نگهداری می‌شود.
                            conn.commit()
                    except Exception:
                        try:
                            conn.rollback()
                        except Exception:
                            pass

                    # ثبت start_time و فعال‌سازی سیستم
                    cur.execute("UPDATE sessions SET start_time=?, paused_seconds=0 WHERE id=?", (now_str, session_id))
                    cur.execute("UPDATE systems SET active=1, last_update_time=? WHERE id=?", (now_str, sys_id))
                    conn.commit()
                    if not hasattr(self, "_running_sessions_map"):
                        self._running_sessions_map = {}
                    self._running_sessions_map[session_id] = now
                    self._ensure_ui_timer_running()

                elif dlg.choice == 'schedule':
                    hh, mm = map(int, dlg.scheduled_time_str.split(":"))
                    now = datetime.now()
                    chosen_dt = datetime(now.year, now.month, now.day, hh, mm, 0)
                    chosen_str = chosen_dt.strftime("%Y-%m-%d %H:%M:%S")

                    if chosen_dt > now:
                        # زمان در آینده: فقط زمان‌بندی کن
                        cur.execute("UPDATE sessions SET start_time=? WHERE id=?", (chosen_str, session_id))
                        conn.commit()
                        try:
                            self.start_scheduled_timer()
                        except Exception:
                            pass
                        QMessageBox.information(self, "زمان‌بندی شد", f"سیستم برای شروع در {chosen_str} زمان‌بندی شد.")
                    else:
                        # زمان در گذشته یا حال: باید changed_at برای rate برابر chosen_str ثبت شود
                        try:
                            # اگر رکوردی وجود ندارد یا changed_at بعد از chosen_str است، درج یک ردیف با changed_at = chosen_str
                            cur.execute("SELECT new_rate_id, changed_at FROM session_rate_changes WHERE session_id=? ORDER BY datetime(changed_at) DESC LIMIT 1", (session_id,))
                            rr = cur.fetchone()
                            if not rr or not rr[0]:
                                # هیچ تعرفه‌ای برای سشن ثبت نشده؛ تعرفهٔ پیش‌فرض را مستقیماً از زمان شروع ثبت کن.
                                cur2 = conn.cursor()
                                cur2.execute("SELECT id FROM ps_rates WHERE system_id=? ORDER BY controllers_count ASC LIMIT 1", (sys_id,))
                                r0 = cur2.fetchone()
                                if r0 and r0[0]:
                                    cur.execute("INSERT INTO session_rate_changes (session_id, old_rate_id, new_rate_id, changed_at, source_note) VALUES (?, ?, ?, ?, ?)",
                                                (session_id, None, r0[0], chosen_str, "پیش‌فرض در schedule گذشته"))
                                # در حالت تک‌تعرفه‌ای، نرخ پایه در systems.price_per_hour نگهداری می‌شود.
                                conn.commit()
                            else:
                                # تعرفهٔ انتخاب‌شده قبلاً هنگام شروع سشن ثبت شده است.
                                # همان رکورد اولیه را به زمان شروع گذشته منتقل می‌کنیم تا نرخ قدیمی
                                # به‌صورت بازهٔ اضافی بین chosen_str و زمان فعلی محاسبه نشود.
                                last_changed = rr[1]
                                if last_changed and last_changed > chosen_str:
                                    cur.execute("""
                                        UPDATE session_rate_changes
                                        SET changed_at=?
                                        WHERE id=(
                                            SELECT id FROM session_rate_changes
                                            WHERE session_id=?
                                            ORDER BY datetime(changed_at) ASC, id ASC
                                            LIMIT 1
                                        )
                                    """, (chosen_str, session_id))
                                    conn.commit()
                        except Exception:
                            try:
                                conn.rollback()
                            except Exception:
                                pass

                        # سپس فعال‌سازی با start_time = chosen_str
                        cur.execute("UPDATE sessions SET start_time=?, paused_seconds=0 WHERE id=?", (chosen_str, session_id))
                        cur.execute("UPDATE systems SET active=1, last_update_time=? WHERE id=?", (now_str, sys_id))
                        conn.commit()
                        if not hasattr(self, "_running_sessions_map"):
                            self._running_sessions_map = {}
                        self._running_sessions_map[session_id] = chosen_dt
                        self._ensure_ui_timer_running()
                        minutes = int((now - chosen_dt).total_seconds() // 60)
                        QMessageBox.information(self, "شروع بازگشتی",
                                                f"سیستم از {chosen_str} شروع شد. حدود {minutes} دقیقه محاسبه می‌شود.")
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                QMessageBox.warning(self, "خطا", f"خطا در ثبت شروع سشن: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            # رفرش UI
            self.load_systems()

        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            QMessageBox.warning(self, "خطا", f"خطای غیرمنتظره: {e}")
            try:
                conn.close()
            except Exception:
                pass


    def stop_system(self, sys_id):
        try:
            conn = database.get_connection()
        except Exception:
            conn = sqlite3.connect(database.DB_PATH, timeout=10)

        try:
            cur = conn.cursor()

            # گرفتن آخرین سشن فعال برای این سیستم
            cur.execute("""
                SELECT id, start_time, paused_seconds
                FROM sessions
                WHERE system_id=? AND end_time IS NULL
                ORDER BY id DESC LIMIT 1
            """, (sys_id,))
            session = cur.fetchone()

            if not session:
                conn.close()
                return

            session_id, start_time, paused_seconds = session
            existing_paused = to_int_safe(paused_seconds, 0)

            # محاسبهٔ elapsed به صورت ایمن
            elapsed_seconds = 0
            if start_time:
                try:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elapsed_seconds = int((datetime.now() - start_dt).total_seconds())
                    if elapsed_seconds < 0:
                        elapsed_seconds = 0
                except Exception as e:
                    elapsed_seconds = 0
            else:
                # اگر start_time وجود ندارد، فرض می‌کنیم سشن قبلاً paused بوده
                elapsed_seconds = 0

            # مقدار پیشنهادی جدید paused
            try:
                total_seconds = int(existing_paused) + int(elapsed_seconds)
            except Exception:
                total_seconds = existing_paused

            # Save the complete accrued cost before clearing start_time. This
            # prevents a paused multi-rate session from being recalculated using
            # the (often zero) legacy base price. Keep the old best-effort value
            # for sessions that were already paused.
            if start_time:
                try:
                    accrued_cost = repo.calc_session_cost_and_segments(
                        conn, session_id, sys_id, until_dt=datetime.now()
                    )[0]
                except Exception:
                    accrued_cost = 0
                cur.execute("""
                    UPDATE sessions
                    SET cost=?, paused_seconds=?, start_time=NULL
                    WHERE id=?
                """, (max(0, int(accrued_cost)), total_seconds, session_id))
            elif total_seconds > existing_paused:
                cur.execute("UPDATE sessions SET paused_seconds=? WHERE id=?", (total_seconds, session_id))

            # تغییر وضعیت سیستم به paused (2)
            cur.execute("UPDATE systems SET active=2 WHERE id=?", (sys_id,))

            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

        try:
            self.load_systems()
        except Exception:
            pass



    def change_system(self, old_sys_id):
        """Move an active session to another machine without losing or duplicating cost."""
        conn = None
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, name, price_per_hour, cost, note, customer_id, active FROM systems WHERE id=?", (old_sys_id,))
            source = cur.fetchone()
            if not source:
                QMessageBox.warning(self, "خطا", "سیستم مبدأ پیدا نشد.")
                return
            _, source_name, source_base_price, source_transfer_cost, source_note, source_customer_id, source_active = source
            if source_active != 1:
                QMessageBox.warning(self, "انتقال سیستم", "برای انتقال، سیستم باید در حال اجرا باشد.")
                return

            cur.execute("""SELECT id, start_time, paused_seconds, customer_id, controllers_count, cost
                           FROM sessions WHERE system_id=? AND end_time IS NULL
                           ORDER BY id DESC LIMIT 1""", (old_sys_id,))
            session = cur.fetchone()
            if not session:
                QMessageBox.warning(self, "خطا", "برای این سیستم سشن فعالی پیدا نشد.")
                return
            session_id, start_time, paused_seconds, customer_id, old_controllers, saved_session_cost = session
            paused_seconds = to_int_safe(paused_seconds, 0)

            # Resolve the actual active source tariff from immutable history snapshots.
            cur.execute("""SELECT new_rate_id, new_rate_price, new_rate_name
                           FROM session_rate_changes
                           WHERE session_id=? AND datetime(changed_at)<=datetime('now','localtime')
                           ORDER BY datetime(changed_at) DESC, id DESC LIMIT 1""", (session_id,))
            last_rate = cur.fetchone()
            old_rate_id = last_rate[0] if last_rate else None
            old_rate_price = to_float_safe(last_rate[1], 0.0) if last_rate and last_rate[1] is not None else None
            old_rate_name = last_rate[2] if last_rate and last_rate[2] else None
            if old_rate_id is not None:
                cur.execute("SELECT price_per_hour, name, controllers_count FROM ps_rates WHERE id=? AND system_id=?", (old_rate_id, old_sys_id))
                old_rate_row = cur.fetchone()
                if old_rate_row:
                    if old_rate_price is None:
                        old_rate_price = to_float_safe(old_rate_row[0], 0.0)
                    if old_rate_name is None:
                        old_rate_name = old_rate_row[1]
                    old_controllers = to_int_safe(old_rate_row[2], old_controllers or 1)
            if old_rate_price is None:
                old_rate_price = to_float_safe(source_base_price, 0.0)
            if not old_rate_name:
                old_rate_name = "تعرفه ثابت" if old_rate_id is None else f"تعرفه {old_controllers or 1} دسته"

            # Collect only currently free systems and their actual rate options.
            cur.execute("SELECT id, name, price_per_hour FROM systems WHERE id!=? AND active=0 ORDER BY name", (old_sys_id,))
            target_rows = cur.fetchall()
            if not target_rows:
                QMessageBox.warning(self, "انتقال سیستم", "هیچ سیستم آزادی برای انتقال وجود ندارد.")
                return

            targets = {}
            for target_id, target_name, target_base in target_rows:
                cur.execute("""SELECT id, controllers_count, price_per_hour, name
                               FROM ps_rates WHERE system_id=? ORDER BY controllers_count, id""", (target_id,))
                rates = cur.fetchall()
                if rates:
                    options = [(rid, to_int_safe(count, 1), to_int_safe(price, 0), (name or f"{count} دسته"))
                               for rid, count, price, name in rates]
                else:
                    options = [(None, 1, to_int_safe(target_base, 0), "تعرفه ثابت")]
                targets[target_id] = {"name": target_name, "options": options}

            dlg = QDialog(self)
            dlg.setWindowTitle("انتقال سیستم")
            dlg.setMinimumWidth(460)
            layout = QVBoxLayout(dlg)
            layout.addWidget(QLabel(f"سیستم مبدأ: <b>{source_name}</b>"))
            layout.addWidget(QLabel(f"تعرفه فعلی: {old_rate_name} — {int(old_rate_price):,} تومان/ساعت"))
            system_combo = QComboBox()
            for target_id, _name, _price in target_rows:
                details = " | ".join(f"{label}: {price:,} تومان/ساعت" for _rid, _count, price, label in targets[target_id]["options"])
                system_combo.addItem(f"{targets[target_id]['name']} ({details})", target_id)
            layout.addWidget(QLabel("سیستم مقصد"))
            layout.addWidget(system_combo)
            layout.addWidget(QLabel("تعرفهٔ مقصد (از لحظهٔ انتقال)"))
            rate_combo = QComboBox()
            layout.addWidget(rate_combo)
            summary = QLabel("هزینهٔ ثبت‌شدهٔ قبلی منتقل می‌شود و دوباره محاسبه نخواهد شد. مدت کل جلسه حفظ می‌شود.")
            summary.setWordWrap(True)
            layout.addWidget(summary)

            def populate_rates(_index=0):
                rate_combo.clear()
                target_id = system_combo.currentData()
                options = targets.get(target_id, {}).get("options", [])
                selected_index = 0
                for i, (rate_id, count, price, label) in enumerate(options):
                    rate_combo.addItem(f"{label} — {price:,} تومان/ساعت", (rate_id, count, price, label))
                    if count == to_int_safe(old_controllers, 1):
                        selected_index = i
                if options:
                    rate_combo.setCurrentIndex(selected_index)
            system_combo.currentIndexChanged.connect(populate_rates)
            populate_rates()

            buttons = QHBoxLayout()
            transfer_btn = QPushButton("تأیید و انتقال")
            cancel_btn = QPushButton("انصراف")
            transfer_btn.clicked.connect(dlg.accept)
            cancel_btn.clicked.connect(dlg.reject)
            buttons.addWidget(transfer_btn)
            buttons.addWidget(cancel_btn)
            layout.addLayout(buttons)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            new_sys_id = system_combo.currentData()
            selected_rate = rate_combo.currentData()
            if new_sys_id is None or selected_rate is None:
                QMessageBox.warning(self, "انتقال سیستم", "لطفاً سیستم مقصد و تعرفه را انتخاب کنید.")
                return
            new_rate_id, new_controllers, new_rate_price, new_rate_name = selected_rate
            new_rate_name = str(new_rate_name or ("تعرفه ثابت" if new_rate_id is None else f"تعرفه {new_controllers} دسته"))

            accrued_at = datetime.now().replace(microsecond=0)
            now_str = accrued_at.strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("SELECT start_time, paused_seconds, cost FROM sessions WHERE id=?", (session_id,))
            current_session = cur.fetchone()
            if not current_session:
                QMessageBox.warning(self, "انتقال سیستم", "سشن قبل از انتقال تغییر کرده است؛ دوباره تلاش کنید.")
                return
            current_start, current_paused, current_saved_cost = current_session
            total_seconds = to_int_safe(current_paused, 0)
            if current_start:
                try:
                    total_seconds += max(0, int((accrued_at - datetime.strptime(current_start, "%Y-%m-%d %H:%M:%S")).total_seconds()))
                except Exception:
                    pass
            try:
                accrued_cost = to_int_safe(repo.calc_session_cost_and_segments(conn, session_id, old_sys_id, until_dt=accrued_at)[0], 0)
            except Exception:
                accrued_cost = to_int_safe(current_saved_cost, 0)
            transfer_amount = max(0, to_int_safe(source_transfer_cost, 0)) + max(0, accrued_cost)

            confirm = QMessageBox(self)
            confirm.setWindowTitle("تأیید انتقال")
            confirm.setText(
                f"انتقال از {source_name} به {targets[new_sys_id]['name']}\n\n"
                f"تعرفه قبلی: {int(old_rate_price):,} تومان/ساعت\n"
                f"تعرفه جدید: {int(new_rate_price):,} تومان/ساعت\n"
                f"هزینهٔ قابل انتقال: {transfer_amount:,} تومان\n\n"
                "زمان کل جلسه حفظ می‌شود؛ هزینهٔ قبلی فقط یک بار در تسویه منظور خواهد شد."
            )
            confirm.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            confirm.setDefaultButton(QMessageBox.StandardButton.No)
            if confirm.exec() != QMessageBox.StandardButton.Yes:
                return

            # Atomic transfer and availability re-check.
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("SELECT active FROM systems WHERE id=?", (new_sys_id,))
            target_state = cur.fetchone()
            if not target_state or target_state[0] != 0:
                raise RuntimeError("سیستم مقصد دیگر آزاد نیست. فهرست را تازه‌سازی و دوباره تلاش کنید.")
            cur.execute("SELECT id FROM sessions WHERE system_id=? AND end_time IS NULL AND id!=? LIMIT 1", (new_sys_id, session_id))
            if cur.fetchone():
                raise RuntimeError("برای سیستم مقصد یک سشن پایان‌نیافته وجود دارد.")

            cur.execute("""INSERT INTO session_rate_changes
                (session_id, old_rate_id, new_rate_id, changed_at, source_system_id, source_note,
                 old_rate_price, old_rate_name, new_rate_price, new_rate_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, old_rate_id, new_rate_id, now_str, old_sys_id,
                 f"انتقال از {source_name} به {targets[new_sys_id]['name']}",
                 int(old_rate_price), old_rate_name, int(new_rate_price), new_rate_name))

            # The previous leg is represented once in systems.cost. A new billing
            # leg starts now; paused_seconds preserves the whole session duration.
            cur.execute("""UPDATE sessions SET system_id=?, start_time=?, paused_seconds=?,
                           controllers_count=?, cost=0, customer_id=? WHERE id=?""",
                        (new_sys_id, now_str, total_seconds, int(new_controllers), customer_id, session_id))
            cur.execute("UPDATE systems SET active=0, customer_id=NULL, note='', cost=0 WHERE id=?", (old_sys_id,))
            cur.execute("""UPDATE systems SET active=1, customer_id=?, note=?, cost=?, last_update_time=?
                           WHERE id=?""", (customer_id, source_note or "", transfer_amount, now_str, new_sys_id))
            conn.commit()

            try:
                if not hasattr(self, "_running_sessions_map"):
                    self._running_sessions_map = {}
                self._running_sessions_map[session_id] = accrued_at
                self._ensure_ui_timer_running()
            except Exception:
                pass
            try:
                self.send_update()
            except Exception:
                pass
            QMessageBox.information(self, "انتقال موفق", "سیستم با تعرفهٔ انتخاب‌شده منتقل شد و هزینهٔ قبلی فقط یک‌بار محاسبه می‌شود.")
        except Exception as e:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            QMessageBox.warning(self, "خطا در انتقال سیستم", str(e))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            try:
                self.load_systems()
            except Exception:
                pass

    def add_snack(self, sys_id):
        self.snack_window = AddSnackToSystem(sys_id)
        self.snack_window.show()

    def checkout(self, sys_id):
        try:
            self.timer.stop()
        except Exception:
            pass

        # 1) محاسبات اولیه با اتصال و سپس بستن اتصال
        try:
            try:
                conn = database.get_connection()
            except Exception:
                conn = sqlite3.connect(database.DB_PATH, timeout=10)
            cur = conn.cursor()

            # گرفتن نوت سیستم
            cur.execute("SELECT note FROM systems WHERE id=?", (sys_id,))
            row = cur.fetchone()
            system_note = row[0] if row and row[0] is not None else ""

            # گرفتن سشن فعال
            cur.execute("""
                SELECT id, start_time, paused_seconds, customer_id
                FROM sessions
                WHERE system_id=? AND end_time IS NULL
                ORDER BY id DESC LIMIT 1
            """, (sys_id,))
            session = cur.fetchone()
            if not session:
                conn.close()
                QMessageBox.information(self, "تسویه", "هیچ سشن فعالی برای این سیستم نیست.")
                try:
                    self.timer.start(1000)
                except Exception:
                    pass
                return

            session_id, start_time, paused_seconds, customer_id = session
            paused_seconds = to_int_safe(paused_seconds, 0)

            # محاسبه elapsed بدون نوشتن در DB
            if start_time:
                try:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elapsed_seconds = int((datetime.now() - start_dt).total_seconds())
                    if elapsed_seconds < 0:
                        elapsed_seconds = 0
                except Exception:
                    elapsed_seconds = paused_seconds
            else:
                elapsed_seconds = paused_seconds

            total_seconds = to_int_safe(paused_seconds, 0) + to_int_safe(elapsed_seconds, 0)

            # قیمت پایه و هزینه ذخیره شده (transfer_cost)
            cur.execute("SELECT price_per_hour, cost FROM systems WHERE id=?", (sys_id,))
            row = cur.fetchone()
            if row:
                price_per_hour, transfer_cost = row[0], row[1]
            else:
                price_per_hour, transfer_cost = 0, 0

            # محاسبه هزینه و قطعات با تابع repository
            try:
                total_with_accum, segments, accum_cost, accum_details = repo.calc_session_cost_and_segments(
                    conn, session_id, sys_id, until_dt=datetime.now()
                )
            except Exception as e:
                total_with_accum = to_int_safe(total_seconds * (to_int_safe(price_per_hour) / 3600.0))
                segments = []
                accum_cost = 0
                accum_details = []

            # خواندن خوراکی‌ها
            try:
                cur.execute("""
                    SELECT COALESCE(ss.name_snapshot, f.name, 'خوراکی حذف‌شده'),
                           COALESCE(ss.price_snapshot, f.price, 0), ss.quantity
                    FROM session_snacks ss
                    LEFT JOIN foods f ON f.id = ss.snack_id
                    WHERE ss.session_id = ?
                """, (session_id,))
                snacks_list = cur.fetchall() or []
            except sqlite3.OperationalError:
                snacks_list = []

            # بستن اتصال قبل از نمایش دیالوگ
            try:
                conn.close()
            except Exception:
                pass

        except Exception as e:
            try:
                conn.close()
            except Exception:
                pass
            QMessageBox.warning(self, "خطا", f"خطا در آماده‌سازی تسویه: {e}")
            try:
                self.timer.start(1000)
            except Exception:
                pass
            return

        # 2) ساخت متن فاکتور و نمایش دیالوگ بدون اتصال باز
        snack_cost = 0
        for s_name, s_price, s_qty in snacks_list:
            try:
                price_val = int(s_price) if isinstance(s_price, (int, float)) else int(str(s_price).replace(",", "").strip() or 0)
            except Exception:
                price_val = 0
            try:
                qty_val = int(s_qty or 0)
            except Exception:
                qty_val = 0
            snack_cost += price_val * qty_val

        customer_text = "مشتری: متفرقه"
        if customer_id:
            try:
                conn2 = database.get_connection()
            except Exception:
                conn2 = sqlite3.connect(database.DB_PATH, timeout=10)
            try:
                cur2 = conn2.cursor()
                cur2.execute("SELECT name, family, code FROM customers WHERE id=?", (customer_id,))
                customer = cur2.fetchone()
                if customer:
                    customer_text = f"مشتری: {customer[0]} {customer[1]} - {customer[2]}"
                else:
                    customer_text = "مشتری: نامشخص"
            except Exception:
                customer_text = "مشتری: نامشخص"
            finally:
                try:
                    conn2.close()
                except Exception:
                    pass

        # ایمن‌سازی مقادیر خروجی calc
        total_with_accum = to_int_safe(total_with_accum, 0)
        accum_cost = to_int_safe(accum_cost, 0)
        base_time_cost = total_with_accum - accum_cost
        if base_time_cost < 0:
            base_time_cost = 0
        transfer_cost = to_int_safe(transfer_cost, 0)
        snack_cost = to_int_safe(snack_cost, 0)
        price_per_hour = to_int_safe(price_per_hour, 0)
        total_seconds = to_int_safe(total_seconds, 0)

        text = customer_text + "\n\nخوراکی‌ها:\n"
        if snacks_list:
            for s_name, s_price, s_qty in snacks_list:
                try:
                    line_cost = int(s_price) * int(s_qty)
                except Exception:
                    line_cost = 0
                text += f"{s_name} × {s_qty} = {line_cost:,}\n"
        else:
            text += "هیچ\n"

        text += "\nجزئیات هزینه بازی:\n"

        # هزینهٔ تجمعی قبلی
        if accum_details:
            for item in accum_details:
                note = item.get("note", "هزینهٔ قبلی")
                amt = to_int_safe(item.get("amount", 0))
                text += f"هزینهٔ قبلی: {amt:,} تومان — {note}\n"
        elif accum_cost > 0:
            text += f"هزینهٔ قبلی: {accum_cost:,} تومان\n"

        # هزینهٔ زمان جاری (بدون هزینهٔ قبلی)
        text += f"هزینه زمان جاری (بدون هزینهٔ قبلی): {base_time_cost:,} تومان\n"

        # نمایش قطعات اگر وجود دارد
        if segments:
            for seg in segments:
                try:
                    a, b, rate_id, rate_name, rate_val, secs, cost_seg = seg
                except Exception:
                    try:
                        a, b, rate_val, secs, cost_seg = seg
                        rate_id = None
                        rate_name = None
                    except Exception:
                        continue
                try:
                    time_label = f"{a.strftime('%H:%M')} → {b.strftime('%H:%M')}"
                except Exception:
                    time_label = f"{str(a)} → {str(b)}"
                try:
                    rate_label = rate_name if rate_name else (f"{int(rate_val):,}" if rate_val else "بدون نرخ")
                except Exception:
                    rate_label = "بدون نرخ"
                minutes = to_int_safe(secs) // 60
                text += f"{time_label} | {minutes} دقیقه | {rate_label} | هزینه {to_int_safe(cost_seg):,}\n"
        else:
            text += f"مدت کل: {total_seconds//60} دقیقه | نرخ: {price_per_hour:,} | هزینه: {base_time_cost:,}\n"

        # نمایش هزینهٔ انتقال (اگر وجود دارد)
        if transfer_cost > 0:
            text += f"\nهزینهٔ انتقال از سیستم قبلی: {transfer_cost:,} تومان\n"

        # جمع‌بندی نهایی
        grand_total = base_time_cost + accum_cost + transfer_cost + snack_cost
        text += f"هزینه خوراکی‌ها: {snack_cost:,}\n"
        text += f"جمع کل: {grand_total:,}\n"

        if system_note and system_note.strip() != "":
            text += f"\nیادداشت سیستم:\n{system_note}\n"
            # نمایش دیالوگ تسویه
        dlg = QDialog(self)
        dlg.setWindowTitle("تسویه حساب")
        layout = QVBoxLayout(dlg)
        label = QLabel(text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)

        rb_instant = rb_add_to_account = rb_custom_amount = None
        custom_input = None
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

        if result != 1:
            try:
                self.load_systems()
            except Exception:
                pass
            try:
                self.timer.start(1000)
            except Exception:
                pass
            return

        # 3) اعمال تغییرات دائمی با اتصال جدید
        try:
            try:
                conn3 = database.get_connection()
            except Exception:
                conn3 = sqlite3.connect(database.DB_PATH, timeout=10)
            cur3 = conn3.cursor()

            total = grand_total
            payment_info = ""
            if customer_id:
                cur3.execute("SELECT balance FROM customers WHERE id=?", (customer_id,))
                balance_row = cur3.fetchone()
                balance = to_int_safe(balance_row[0]) if balance_row else 0

                if rb_instant and rb_instant.isChecked():
                    payment_info = f"پرداخت نقدی: {total:,} تومان"
                elif rb_add_to_account and rb_add_to_account.isChecked():
                    new_balance = balance - total
                    cur3.execute("UPDATE customers SET balance=? WHERE id=?", (new_balance, customer_id))
                    balance_text = f"<span style='color:red;'>{new_balance:,}</span>" if new_balance < 0 else f"{new_balance:,}"
                    payment_info = f"کسر از حساب مشتری: {total:,} تومان\nموجودی جدید مشتری: {balance_text} تومان"
                elif rb_custom_amount and rb_custom_amount.isChecked():
                    try:
                        custom_amount = int(custom_input.text())
                    except Exception:
                        custom_amount = 0
                    new_balance = balance - custom_amount
                    cur3.execute("UPDATE customers SET balance=? WHERE id=?", (new_balance, customer_id))
                    balance_text = f"<span style='color:red;'>{new_balance:,}</span>" if new_balance < 0 else f"{new_balance:,}"
                    payment_info = f"کسر مبلغ دلخواه: {custom_amount:,} تومان\nموجودی جدید مشتری: {balance_text} تومان"
            else:
                payment_info = f"پرداخت نقدی: {total:,} تومان"

            msg = QMessageBox(self)
            msg.setWindowTitle("نتیجه پرداخت")
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(payment_info)
            msg.exec()

            # بستن کامل سشن و آزاد کردن سیستم (تغییرات دائمی)
            cur3.execute("UPDATE sessions SET end_time=?, paused_seconds=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total_seconds, session_id))
            cur3.execute("UPDATE systems SET active=0, customer_id=NULL, note='' WHERE id=?", (sys_id,))
            cur3.execute("UPDATE systems SET cost=0 WHERE id=?", (sys_id,))
            conn3.commit()
        except Exception as e:
            try:
                conn3.rollback()
            except Exception:
                pass
            QMessageBox.warning(self, "خطا", f"خطا در ثبت تسویه: {e}")
        finally:
            try:
                conn3.close()
            except Exception:
                pass

        try:
            self.load_systems()
        except Exception:
            pass

        try:
            self.timer.start(1000)
        except Exception:
            pass


    def open_add_system(self):
        self.addSystem = AddSystemWindow()
        self.addSystem.show()
        self.load_systems()


    def open_add_customer(self):
            self.addcustomer = NewCustomerWindow()
            self.addcustomer.show()
            self.load_systems()

    def open_chgarge_customer(self):
            self.chargecustomer = ChargeCustomerWindow()
            self.chargecustomer.show()
            self.load_systems()

    def open_customer_list(self):
            self.customerlist = CustomerListWindow()
            self.customerlist.show()
            self.load_systems()

    def open_snack_list(self):
            self.snacklist = SnackListWindow()
            self.snacklist.show()
            self.load_systems()

    def open_system_list(self):
           self.systemlist = System_List()
           self.systemlist.show()
           self.load_systems()

    def start_sender_timer(self):
        self.sender_timer = QTimer()
        self.sender_timer.timeout.connect(self.send_update)
        self.sender_timer.start(5000)

    def open_user_name(self):
        self.selectusername = SelectUsernameWindow()
        self.selectusername.show()



