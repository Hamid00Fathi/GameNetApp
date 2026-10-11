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
        self.listw.setMinimumSize(360, 250)
        self.listw.setStyleSheet("""
            QListWidget { background:#101a2a; color:#e8eef8; border:1px solid #344966;
                          border-radius:8px; padding:5px; font-size:12pt; }
            QListWidget::item { padding:12px 10px; border-radius:6px; margin:2px; }
            QListWidget::item:hover { background:#203653; }
            QListWidget::item:selected { background:#2864e8; color:white; border:1px solid #6e9bff; }
        """)
        for r in rates:
            rid, controllers_count, price_per_hour, name = r
            label = f"{name or f'{controllers_count} دسته'} — {price_per_hour:,} تومان / ساعت"
            self.listw.addItem(label)
            self.listw.item(self.listw.count()-1).setData(Qt.ItemDataRole.UserRole, rid)
        self.selection_hint = QLabel("برای انتخاب، روی تعرفه کلیک کنید.")
        self.selection_hint.setStyleSheet("color:#9db8e8; padding:4px; font-size:11pt;")
        v.addWidget(self.listw)
        v.addWidget(self.selection_hint)
        self.listw.currentItemChanged.connect(self._show_selected_rate)
        self.listw.itemDoubleClicked.connect(self._accept_double_click)
        btn = QPushButton("انتخاب تعرفه")
        btn.setMinimumHeight(42)
        btn.clicked.connect(self.on_select)
        v.addWidget(btn)
        if self.listw.count():
            self.listw.setCurrentRow(0)

    def _show_selected_rate(self, current, previous=None):
        if current is None:
            self.selected_rate_id = None
            self.selection_hint.setText("برای انتخاب، روی تعرفه کلیک کنید.")
            return
        self.selected_rate_id = current.data(Qt.ItemDataRole.UserRole)
        self.selection_hint.setText(f"تعرفه انتخاب‌شده: {current.text()}")

    def _accept_double_click(self, item):
        if item is not None:
            self.selected_rate_id = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

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
        from windows.ui_builder import build_ui
        build_ui(self, 'main')

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

        # ستون‌ها همیشه با عرض پنجره هماهنگ می‌شوند و اسکرول افقی لازم نیست.
        header = self.systemTable.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        self.systemTable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # دسترسی مستقیم به کارت‌های آماری ساخته‌شده در ui_builder
        self.metric_revenue = self.findChild(QLabel, "metric_revenue")
        self.metric_sessions = self.findChild(QLabel, "metric_sessions")
        self.metric_customers = self.findChild(QLabel, "metric_customers")

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

        # Any session left running when the previous process ended must become
        # paused on startup, even if the last heartbeat is only a second old.
        # The stored heartbeat is used as the safe billing cutoff.
        self.detect_power_loss()
        self.load_systems()

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
            # A missing/malformed heartbeat must not leave an active session
            # impossible to resume. In that case use the session start as a
            # conservative cutoff, avoiding charges for unknown offline time.
            last_dt = None
            if last_update_time:
                try:
                    last_dt = datetime.strptime(last_update_time, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    last_dt = None

            if last_dt is None:
                cur.execute("""
                    SELECT start_time FROM sessions
                    WHERE system_id=? AND end_time IS NULL
                    ORDER BY id DESC LIMIT 1
                """, (sys_id,))
                fallback_session = cur.fetchone()
                try:
                    last_dt = datetime.strptime(
                        fallback_session[0], "%Y-%m-%d %H:%M:%S"
                    ) if fallback_session and fallback_session[0] else now
                except Exception:
                    last_dt = now

            diff = int((now - last_dt).total_seconds())

            # During application startup, an active=1 session is always treated
            # as interrupted. A recent heartbeat does not mean the application
            # is still running (it may have closed just after writing it).
            if active == 1 or diff > threshold_seconds:
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

    @staticmethod
    def _status_info(active):
        """Return a high-contrast label and color for the system state."""
        try:
            active = int(active)
        except (TypeError, ValueError):
            active = 0
        if active == 1:
            return "فعال", "#16A34A"       # سبز: جلسه در حال اجرا
        if active == 2:
            return "توقف", "#2563EB"      # آبی: جلسه مکث/توقف شده
        return "آزاد", "#DC2626"           # قرمز: جلسه‌ای باز نیست

    def status_item(self, active):
        """Fallback item with a colored background, kept for compatibility."""
        label, color = self._status_info(active)
        item = QTableWidgetItem(label)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor("#FFFFFF"))
        item.setBackground(QColor(color))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setToolTip(f"وضعیت سیستم: {label}")
        return item

    def status_badge(self, active):
        """Compact, cell-bounded status label; never overlaps adjacent cells."""
        label, color = self._status_info(active)
        badge = QLabel(label)
        badge.setObjectName("systemStatusBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # A cell widget must not request a size larger than the status column/row.
        # In particular, no 58x30 minimum, padding, border, or rounded frame.
        badge.setMinimumSize(0, 0)
        badge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        badge.setMargin(0)
        badge.setIndent(0)
        badge.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        badge.setToolTip(f"وضعیت سیستم: {label}")
        badge.setStyleSheet(
            f"""
            QLabel#systemStatusBadge {{
                background-color: {color};
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                margin: 0px;
                padding: 0px;
                font-weight: 800;
            }}
        """
        )
        return badge

    def refresh_dashboard_metrics(self):
        """Refresh dashboard counters from the local database without affecting session logic."""
        conn = None
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM customers")
            customers_count = int((cur.fetchone() or [0])[0] or 0)
            cur.execute("SELECT COUNT(*) FROM sessions WHERE end_time IS NULL")
            active_sessions = int((cur.fetchone() or [0])[0] or 0)
            # Settled sessions ending today are used as today's realized revenue.
            cur.execute("""
                SELECT COALESCE(SUM(COALESCE(cost, 0) + COALESCE(snack_cost, 0) - COALESCE(discount, 0)), 0)
                FROM sessions
                WHERE end_time IS NOT NULL
                  AND date(end_time) = date('now', 'localtime')
            """)
            revenue_today = int((cur.fetchone() or [0])[0] or 0)
            if hasattr(self, "metric_customers"):
                self.metric_customers.setText(f"{customers_count:,}")
            if hasattr(self, "metric_sessions"):
                self.metric_sessions.setText(f"{active_sessions:,}")
            if hasattr(self, "metric_revenue"):
                self.metric_revenue.setText(f"{revenue_today:,} تومان")
        except Exception:
            # Keep the UI usable if a legacy database has an unexpected schema.
            for attr in ("metric_customers", "metric_sessions", "metric_revenue"):
                label = getattr(self, attr, None)
                if label is not None and label.text() == "در حال بارگذاری…":
                    label.setText("—")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

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
                try:
                    self.refresh_dashboard_metrics()
                except Exception:
                    pass

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
            current_ids = set(self.system_row_map.values()) if hasattr(self, "system_row_map") else set()
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

    def update_ui_tick(self):
        """Refresh elapsed time, live cost, and status without rebuilding cell widgets."""
        try:
            systems = get_systems()
            # get_systems returns the same tuple layout used by load_systems.
            for sys in systems:
                sys_id, name, active, start_time, elapsed, cost, customer_id, note, controllers_count, price_per_hour = sys
                row = next((r for r, sid in self.system_row_map.items() if sid == sys_id), None)
                if row is None or row >= self.systemTable.rowCount():
                    continue

                elapsed_item = self.systemTable.item(row, 3)
                if elapsed_item is None:
                    elapsed_item = QTableWidgetItem()
                    elapsed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.systemTable.setItem(row, 3, elapsed_item)
                elapsed_item.setText(str(elapsed or "00:00:00"))

                cost_item = self.systemTable.item(row, 2)
                if cost_item is None:
                    cost_item = QTableWidgetItem()
                    cost_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.systemTable.setItem(row, 2, cost_item)
                try:
                    cost_item.setText(f"{int(cost or 0):,}")
                except (TypeError, ValueError):
                    cost_item.setText(str(cost or 0))

                status_widget = self.systemTable.cellWidget(row, 8)
                status_label, status_color = self._status_info(active)
                if not isinstance(status_widget, QLabel) or status_widget.text() != status_label:
                    self.systemTable.setCellWidget(row, 8, self.status_badge(active))
                else:
                    # Keep the exact same zero-padding style as initial creation;
                    # adding padding/borders here made the badge appear offset.
                    status_widget.setStyleSheet(
                        f"""
                        QLabel#systemStatusBadge {{
                            background-color: {status_color};
                            color: #FFFFFF;
                            border: none;
                            border-radius: 10px;
                            margin: 0px;
                            padding: 0px;
                            font-weight: 800;
                        }}
                    """
                    )
        except Exception:
            # A transient DB issue must not interrupt the one-second UI timer.
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

        # ستون وضعیت ویجت مستقل دارد؛ پس‌زمینهٔ آن را هرگز شفاف نکن.
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
                if widget is not None and c not in skip_columns:
                    try:
                        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                    except Exception:
                        pass
                    widget.setStyleSheet("background: transparent; border: none;")

    def make_icon_button(self, icon_path, icon_size=(28, 28)):
        btn = QPushButton()
        btn.setFlat(True)
        btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        btn.setStyleSheet("QPushButton{border:none;background:transparent;padding:2px;min-height:30px;min-width:34px;border-radius:7px} QPushButton:hover{background:#263a57} QPushButton:pressed{background:#31527d}")
        btn.setIcon(self.get_icon(icon_path))
        btn.setIconSize(QSize(icon_size[0], icon_size[1]))
        return btn

    def update_table_column_widths(self):
        """Keep action/status columns readable while flexible columns use remaining space."""
        try:
            header = self.systemTable.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            for column, width in self._fixed_columns.items():
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
                self.systemTable.setColumnWidth(column, width)
            self.systemTable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except Exception:
            pass

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


            # نام سیستم
            item = QTableWidgetItem(name)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 9, item)


            # وضعیت: سلول غیرقابل انتخاب + نشانگر رنگی که تمام سلول را می‌پوشاند؛
            # در نتیجه نه هایلایت انتخاب و نه hover جدول زیر رنگ وضعیت دیده نمی‌شود.
            status_cell = QTableWidgetItem("")
            status_cell.setFlags(Qt.ItemFlag.NoItemFlags)
            self.systemTable.setItem(row, 8, status_cell)
            self.systemTable.setCellWidget(row, 8, self.status_badge(active))


            # دکمه استارت
            start_btn = self.make_icon_button("icons/start.png", (28,28))
            start_btn.clicked.connect(lambda _, sid=sys_id: self.start_system(sid))
            start_btn.setEnabled(active != 1)
            self.systemTable.setCellWidget(row, 7, start_btn)


            # دکمه استاپ
            stop_btn = self.make_icon_button("icons/stop.png", (30,30))
            stop_btn.clicked.connect(lambda _, sid=sys_id: self.stop_system(sid))
            self.systemTable.setCellWidget(row, 6, stop_btn)


            # دکمه تغییر سیستم
            change_btn = self.make_icon_button("icons/edit.png", (30,30))
            change_btn.clicked.connect(lambda _, sid=sys_id: self.change_system(sid))
            self.systemTable.setCellWidget(row, 5, change_btn)


            # دکمه خوراکی
            snack_btn = self.make_icon_button("icons/snack.png", (30,30))
            snack_btn.clicked.connect(lambda _, sid=sys_id: self.add_snack(sid))
            self.systemTable.setCellWidget(row, 4, snack_btn)


            # زمان سپری‌شده
            item_elapsed = QTableWidgetItem(elapsed)
            item_elapsed.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 3, item_elapsed)


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


            # دکمه تسویه
            checkout_btn = self.make_icon_button("icons/checkout.png", (28,28))
            checkout_btn.clicked.connect(lambda _, sid=sys_id: self.checkout(sid))
            self.systemTable.setCellWidget(row, 0, checkout_btn)


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
                cname = "-"

            item_customer = QTableWidgetItem(cname)
            item_customer.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row, 1, item_customer)


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
                            display_text = "-"

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


            self.system_row_map[row] = sys_id

        self.recolor_rows()
        self.refresh_dashboard_metrics()
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
                SELECT id, start_time, paused_seconds, COALESCE(cost, 0)
                FROM sessions
                WHERE system_id=? AND end_time IS NULL
                ORDER BY id DESC LIMIT 1
            """, (sys_id,))
            session = cur.fetchone()

            if not session:
                conn.close()
                return

            session_id, start_time, paused_seconds, saved_session_cost = session
            pause_at = datetime.now()
            existing_paused = max(0, to_int_safe(paused_seconds, 0))
            saved_session_cost = max(0, to_int_safe(saved_session_cost, 0))

            # محاسبهٔ elapsed به صورت ایمن
            elapsed_seconds = 0
            if start_time:
                try:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elapsed_seconds = int((pause_at - start_dt).total_seconds())
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

            # Persist the full accumulated session cost before pausing. A failure
            # in the calculator must never erase a previously saved amount; that
            # was the cause of the live session cost appearing to restart at zero.
            if start_time:
                accrued_cost = None
                running_segments = []
                try:
                    calc_result = repo.calc_session_cost_and_segments(
                        conn, session_id, sys_id, until_dt=pause_at
                    )
                    accrued_cost, running_segments = calc_result[0], calc_result[1]
                except Exception:
                    # Retry with the equivalent calculator before falling back to
                    # the saved amount; never overwrite an already-saved amount.
                    try:
                        calc_result = database.calc_session_cost_and_segments(
                            conn, session_id, sys_id, until_dt=pause_at
                        )
                        accrued_cost, running_segments = calc_result[0], calc_result[1]
                    except Exception:
                        accrued_cost = None
                        running_segments = []

                if accrued_cost is None:
                    accrued_cost = saved_session_cost
                accrued_cost = max(saved_session_cost, max(0, to_int_safe(accrued_cost, saved_session_cost)))

                # Save each just-finished tariff interval before marking the
                # session paused. These are snapshots for an auditable checkout.
                try:
                    cur.execute("SELECT name FROM systems WHERE id=?", (sys_id,))
                    system_row = cur.fetchone()
                    system_name = system_row[0] if system_row else f"سیستم {sys_id}"
                    repo.persist_cost_segments(conn, session_id, sys_id, system_name, running_segments)
                except Exception:
                    # Pausing and preserving the cumulative amount is more
                    # important than optional display history on an older DB.
                    pass

                cur.execute("""
                    UPDATE sessions
                    SET cost=?, paused_seconds=?, start_time=NULL
                    WHERE id=?
                """, (accrued_cost, total_seconds, session_id))
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
            QMessageBox.warning(self, "خطا در توقف سیستم", f"توقف سیستم انجام نشد و تغییرات ذخیره نشد.\n{e}")
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
                details = " | ".join(f"{label}: {price:,} " for _rid, _count, price, label in targets[target_id]["options"])
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
                accrued_calc = repo.calc_session_cost_and_segments(
                    conn, session_id, old_sys_id, until_dt=accrued_at
                )
                accrued_cost = to_int_safe(accrued_calc[0], 0)
                source_running_segments = accrued_calc[1] or []
            except Exception:
                accrued_cost = to_int_safe(current_saved_cost, 0)
                source_running_segments = []
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
            # Save the just-finished source-machine interval before the session's
            # system_id changes, so checkout can show where that time was spent.
            repo.persist_cost_segments(
                conn, session_id, old_sys_id, source_name, source_running_segments
            )
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
        """Show a structured, auditable invoice and settle the open session once."""
        conn = None
        checkout_at = datetime.now()
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT name, note, COALESCE(cost, 0) FROM systems WHERE id=?", (sys_id,))
            system_row = cur.fetchone()
            if not system_row:
                QMessageBox.warning(self, "خطا", "سیستم موردنظر پیدا نشد.")
                return
            system_name, system_note, transfer_cost = system_row
            system_name = system_name or f"سیستم {sys_id}"
            system_note = system_note or ""
            transfer_cost = max(0, to_int_safe(transfer_cost, 0))

            cur.execute("""
                SELECT id, start_time, COALESCE(paused_seconds, 0), customer_id,
                       COALESCE(cost, 0), COALESCE(controllers_count, 1)
                FROM sessions
                WHERE system_id=? AND end_time IS NULL
                ORDER BY id DESC LIMIT 1
            """, (sys_id,))
            session = cur.fetchone()
            if not session:
                QMessageBox.information(self, "تسویه حساب", "برای این سیستم نشست بازی وجود ندارد.")
                return
            session_id, start_time, paused_seconds, customer_id, saved_cost, _controllers = session
            paused_seconds = max(0, to_int_safe(paused_seconds, 0))
            saved_cost = max(0, to_int_safe(saved_cost, 0))

            running_seconds = 0
            if start_time:
                try:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    running_seconds = max(0, int((checkout_at - start_dt).total_seconds()))
                except (TypeError, ValueError):
                    QMessageBox.warning(
                        self, "زمان نشست نامعتبر است",
                        "زمان شروع این نشست قابل خواندن نیست؛ برای جلوگیری از محاسبه اشتباه، تسویه انجام نشد."
                    )
                    return
            total_seconds = paused_seconds + running_seconds

            # Never fall back to systems.price_per_hour here: that can charge the
            # default tariff instead of the tariff selected for this session.
            try:
                calc = repo.calc_session_cost_and_segments(
                    conn, session_id, sys_id, until_dt=checkout_at
                )
            except Exception:
                try:
                    calc = database.calc_session_cost_and_segments(
                        conn, session_id, sys_id, until_dt=checkout_at
                    )
                except Exception as calc_error:
                    QMessageBox.warning(
                        self, "خطا در محاسبه هزینه",
                        "هزینه نشست با تعرفه ثبت‌شده قابل محاسبه نیست؛ برای جلوگیری از صدور فاکتور اشتباه، تسویه لغو شد.\n\n"
                        f"جزئیات: {calc_error}"
                    )
                    return
            session_time_cost, current_segments, _accum_cost, _accum_details = calc
            session_time_cost = max(0, to_int_safe(session_time_cost, saved_cost))

            # Historical intervals were captured at each stop. Older sessions
            # may have no such rows; those are reconciled below as one explicit
            # cumulative line rather than inventing a tariff breakdown.
            history_segments = []
            try:
                cur.execute("""
                    SELECT system_id, system_name, rate_id, rate_name, rate_price,
                           start_time, end_time, elapsed_seconds, cost
                    FROM session_cost_segments WHERE session_id=? ORDER BY id
                """, (session_id,))
                for row in cur.fetchall():
                    history_segments.append({
                        "system_id": row[0], "system": row[1] or system_name,
                        "rate_id": row[2], "rate": row[3] or "",
                        "rate_price": max(0, to_int_safe(row[4], 0)),
                        "start": row[5] or "", "end": row[6] or "",
                        "seconds": max(0, to_int_safe(row[7], 0)),
                        "cost": max(0, to_int_safe(row[8], 0)),
                    })
            except sqlite3.OperationalError:
                # Defensive compatibility if an old database was not migrated.
                history_segments = []

            display_segments = list(history_segments)
            for seg in current_segments or []:
                try:
                    a, b, rate_id, rate_name, rate_price, seconds, cost = seg
                except (TypeError, ValueError):
                    continue
                seconds = max(0, to_int_safe(seconds, 0))
                if seconds <= 0:
                    continue
                display_segments.append({
                    "system_id": sys_id, "system": system_name,
                    "rate_id": rate_id,
                    "rate": str(rate_name or (f"تعرفه {rate_id}" if rate_id else "تک‌تعرفه‌ای")),
                    "rate_price": max(0, to_int_safe(rate_price, 0)),
                    "start": a.strftime("%Y-%m-%d %H:%M:%S") if hasattr(a, "strftime") else str(a),
                    "end": b.strftime("%Y-%m-%d %H:%M:%S") if hasattr(b, "strftime") else str(b),
                    "seconds": seconds, "cost": max(0, to_int_safe(cost, 0)),
                })

            # A pause/resume cycle is not a separate machine-use line item when
            # the system and tariff are the same. Aggregate repeated intervals
            # by system + tariff while retaining total billed seconds and cost.
            aggregated = {}
            non_interval_rows = []
            for item in display_segments:
                if not item.get("seconds") or not item.get("start") or not item.get("end"):
                    non_interval_rows.append(item)
                    continue
                key = (item.get("system_id"), item.get("rate_id"), item.get("rate"), item.get("rate_price"))
                if key not in aggregated:
                    aggregated[key] = dict(item)
                else:
                    target = aggregated[key]
                    starts = [x for x in (target.get("start", ""), item.get("start", "")) if x]
                    ends = [x for x in (target.get("end", ""), item.get("end", "")) if x]
                    target["start"] = min(starts) if starts else ""
                    target["end"] = max(ends) if ends else ""
                    target["seconds"] = max(0, to_int_safe(target.get("seconds"), 0)) + max(0, to_int_safe(item.get("seconds"), 0))
                    target["cost"] = max(0, to_int_safe(target.get("cost"), 0)) + max(0, to_int_safe(item.get("cost"), 0))
            display_segments = sorted(
                list(aggregated.values()) + non_interval_rows,
                key=lambda item: (item.get("start") or "9999", str(item.get("system") or ""), str(item.get("rate") or ""))
            )

            cur.execute("""
                SELECT COALESCE(ss.name_snapshot, f.name, 'خوراکی حذف‌شده'),
                       COALESCE(ss.price_snapshot, f.price, 0), COALESCE(ss.quantity, 0)
                FROM session_snacks ss
                LEFT JOIN foods f ON f.id=ss.snack_id
                WHERE ss.session_id=? ORDER BY ss.id
            """, (session_id,))
            snacks = cur.fetchall() or []

            customer_text = "مشتری متفرقه"
            if customer_id:
                cur.execute("SELECT name, family, code FROM customers WHERE id=?", (customer_id,))
                customer = cur.fetchone()
                customer_text = (f"{customer[0]} {customer[1]} · کد {customer[2]}" if customer
                                 else "مشتری نامشخص")
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"آماده‌سازی فاکتور انجام نشد:\n{e}")
            return
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        def money(value):
            return f"{to_int_safe(value, 0):,} تومان"

        def duration(seconds):
            seconds = max(0, to_int_safe(seconds, 0))
            hours, rem = divmod(seconds, 3600)
            minutes, secs = divmod(rem, 60)
            if hours:
                return f"{hours} ساعت و {minutes} دقیقه"
            if minutes:
                return f"{minutes} دقیقه و {secs} ثانیه"
            return f"{secs} ثانیه"

        snack_lines = []
        snack_total = 0
        for name, price, quantity in snacks:
            price = max(0, to_int_safe(price, 0))
            quantity = max(0, to_int_safe(quantity, 0))
            line_total = price * quantity
            snack_total += line_total
            snack_lines.append((str(name), quantity, price, line_total))

        # Reconcile visible tariff rows with the authoritative calculator total.
        # This also handles legacy sessions whose previous intervals were not saved.
        detail_total = sum(max(0, to_int_safe(x.get("cost"), 0)) for x in display_segments)
        # The displayed detail rows include both the current machine and any
        # previous machines. Prior-machine amounts are billed in transfer_cost,
        # so reconcile against the combined authoritative total, not only this leg.
        reconciliation = (session_time_cost + transfer_cost) - detail_total
        if reconciliation != 0:
            if reconciliation > 0:
                label = "هزینه قدیمی / انتقالی (جزئیات بازه موجود نیست)"
            else:
                label = "تعدیل داده‌های قدیمی برای تطبیق با مبلغ محاسبه‌شده"
            display_segments.append({
                "system_id": sys_id, "system": system_name, "rate_id": None,
                "rate": label, "rate_price": 0, "start": "", "end": "",
                "seconds": 0, "cost": reconciliation,
            })
        elif not display_segments and session_time_cost:
            display_segments.append({
                "system_id": sys_id, "system": system_name, "rate_id": None,
                "rate": "هزینه تجمیعی ثبت‌شده", "rate_price": 0,
                "start": "", "end": "", "seconds": 0,
                "cost": session_time_cost,
            })

        subtotal = repo.calculate_checkout_totals(
            session_time_cost, transfer_cost, snack_total, 0
        )["subtotal"]

        dlg = QDialog(self)
        dlg.setWindowTitle("تسویه حساب")
        dlg.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        screen = self.screen() if hasattr(self, "screen") else None
        available = screen.availableGeometry() if screen else QRect(0, 0, 1100, 800)
        dialog_width = min(980, max(640, int(available.width() * 0.94)))
        dialog_height = min(780, max(420, int(available.height() * 0.92)))
        dlg.resize(dialog_width, dialog_height)
        dlg.setMinimumSize(min(640, dialog_width), min(420, dialog_height))
        dlg.setMaximumSize(available.size())

        # The invoice body scrolls; the action buttons remain visible at all times.
        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)
        scroll = QScrollArea(dlg)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        heading = QLabel(f"تسویه حساب · {system_name}")
        heading.setStyleSheet("font-size:20px; font-weight:700; color:#e8eef8; padding:4px 2px;")
        root.addWidget(heading)
        customer_label = QLabel(f"{customer_text}    |    مدت استفاده فعال: {duration(total_seconds)}")
        customer_label.setStyleSheet("font-size:13px; color:#aebfd6; padding:2px;")
        root.addWidget(customer_label)

        title_game = QLabel("جزئیات استفاده از سیستم و تعرفه‌ها")
        title_game.setStyleSheet("font-size:14px; font-weight:700; padding-top:5px;")
        root.addWidget(title_game)
        tariff_table = QTableWidget(0, 7)
        tariff_table.setHorizontalHeaderLabels(["سیستم", "تعرفه", "شروع", "پایان", "مدت", "نرخ ساعتی", "هزینه"])
        tariff_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tariff_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tariff_table.setAlternatingRowColors(True)
        tariff_table.verticalHeader().setVisible(False)
        tariff_table.setMinimumHeight(120)
        tariff_table.setMaximumHeight(260)
        tariff_table.setWordWrap(True)
        tariff_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        tariff_table.verticalHeader().setDefaultSectionSize(32)
        tariff_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for item in display_segments:
            row = tariff_table.rowCount()
            tariff_table.insertRow(row)
            start_display = item["start"][-8:-3] if len(item["start"]) >= 16 else (item["start"] or "—")
            end_display = item["end"][-8:-3] if len(item["end"]) >= 16 else (item["end"] or "—")
            values = [
                item["system"] or system_name,
                item["rate"] or ("تک‌تعرفه‌ای" if not item["rate_id"] else f"تعرفه {item['rate_id']}"),
                start_display or "—", end_display or "—",
                duration(item["seconds"]) if item["seconds"] else "—",
                money(item["rate_price"]) + " / ساعت" if item["rate_price"] else "—",
                money(item["cost"]),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                tariff_table.setItem(row, col, cell)
        if tariff_table.rowCount() == 0:
            tariff_table.insertRow(0)
            tariff_table.setItem(0, 0, QTableWidgetItem("بازه‌ای ثبت نشده"))
            tariff_table.setSpan(0, 0, 1, 7)
        root.addWidget(tariff_table)

        title_snacks = QLabel("خوراکی‌های ثبت‌شده")
        title_snacks.setStyleSheet("font-size:14px; font-weight:700; padding-top:2px;")
        root.addWidget(title_snacks)
        snack_table = QTableWidget(0, 4)
        snack_table.setHorizontalHeaderLabels(["خوراکی", "تعداد", "قیمت واحد", "جمع"])
        snack_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        snack_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        snack_table.verticalHeader().setVisible(False)
        snack_table.setMinimumHeight(76)
        snack_table.setMaximumHeight(min(220, 42 + max(1, min(len(snack_lines), 5)) * 34))
        snack_table.setWordWrap(True)
        snack_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        snack_table.verticalHeader().setDefaultSectionSize(32)
        snack_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        snack_table.setColumnWidth(0, 220)
        for name, quantity, price, line_total in snack_lines:
            row = snack_table.rowCount()
            snack_table.insertRow(row)
            for col, value in enumerate([name, quantity, money(price), money(line_total)]):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignRight if col == 0 else Qt.AlignmentFlag.AlignCenter))
                if col == 0:
                    cell.setToolTip(str(name))
                snack_table.setItem(row, col, cell)
        if not snack_lines:
            snack_table.insertRow(0)
            snack_table.setItem(0, 0, QTableWidgetItem("خوراکی‌ای ثبت نشده"))
            snack_table.setSpan(0, 0, 1, 4)
        root.addWidget(snack_table)

        summary = QGridLayout()
        summary.setHorizontalSpacing(18)
        summary.setVerticalSpacing(6)
        summary.addWidget(QLabel("هزینه زمان سیستم:"), 0, 0)
        time_amount = QLabel(money(session_time_cost))
        time_amount.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        summary.addWidget(time_amount, 0, 1)
        summary.addWidget(QLabel("هزینه سیستم‌های قبلی / انتقال:"), 1, 0)
        transfer_amount = QLabel(money(transfer_cost))
        transfer_amount.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        summary.addWidget(transfer_amount, 1, 1)
        summary.addWidget(QLabel("هزینه خوراکی‌ها:"), 2, 0)
        snacks_amount = QLabel(money(snack_total))
        snacks_amount.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        summary.addWidget(snacks_amount, 2, 1)
        summary.addWidget(QLabel("تخفیف (مبلغ ثابت):"), 3, 0)
        discount_input = QLineEdit()
        discount_input.setPlaceholderText("۰")
        discount_input.setMaximumWidth(180)
        summary.addWidget(discount_input, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        summary.addWidget(QLabel("مبلغ نهایی:"), 4, 0)
        grand_total_label = QLabel(money(subtotal))
        grand_total_label.setStyleSheet("font-size:18px; font-weight:800; color:#22c55e; padding:4px 0;")
        grand_total_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        summary.addWidget(grand_total_label, 4, 1)
        root.addLayout(summary)

        if system_note.strip():
            note_label = QLabel(f"یادداشت: {system_note}")
            note_label.setWordWrap(True)
            note_label.setStyleSheet("color:#aebfd6; padding:3px;")
            root.addWidget(note_label)

        rb_instant = rb_add_to_account = rb_custom_amount = None
        custom_input = None
        if customer_id:
            pay_title = QLabel("روش تسویه")
            pay_title.setStyleSheet("font-size:13px; font-weight:700;")
            root.addWidget(pay_title)
            rb_instant = QRadioButton("پرداخت نقدی")
            rb_add_to_account = QRadioButton("ثبت مبلغ در حساب مشتری")
            rb_custom_amount = QRadioButton("ثبت مبلغ دلخواه در حساب مشتری")
            rb_instant.setChecked(True)
            root.addWidget(rb_instant)
            root.addWidget(rb_add_to_account)
            root.addWidget(rb_custom_amount)
            custom_input = QLineEdit()
            custom_input.setPlaceholderText("مبلغ دلخواه حساب مشتری")
            custom_input.setEnabled(False)
            root.addWidget(custom_input)
            rb_custom_amount.toggled.connect(lambda checked: custom_input.setEnabled(checked))

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_cancel = QPushButton("بازگشت")
        btn_ok = QPushButton("ثبت تسویه")
        btn_ok.setDefault(True)
        btn_ok.setMinimumWidth(130)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_ok)
        main_layout.addLayout(buttons)

        def parse_amount(raw):
            value = str(raw or "").strip().replace(",", "").replace("٬", "")
            if not value:
                return 0
            if not value.isdigit():
                raise ValueError("مبلغ باید فقط شامل عدد باشد.")
            return int(value)

        def discount_value(show_error=False):
            try:
                value = parse_amount(discount_input.text())
                if value > subtotal:
                    if show_error:
                        QMessageBox.warning(dlg, "تخفیف نامعتبر", "تخفیف نمی‌تواند از مبلغ کل بیشتر باشد.")
                    return None if show_error else 0
                return value
            except ValueError:
                if show_error:
                    QMessageBox.warning(dlg, "تخفیف نامعتبر", "تخفیف را به‌صورت عدد صحیح وارد کنید.")
                    return None
                return 0

        def refresh_total(_text=None):
            discount_value_now = discount_value(False)
            grand_total_label.setText(money(max(0, subtotal - discount_value_now)))
        discount_input.textChanged.connect(refresh_total)

        result = {"accepted": False}
        def accept_checkout():
            discount_amount = discount_value(True)
            if discount_amount is None:
                return
            if rb_custom_amount and rb_custom_amount.isChecked():
                try:
                    custom_amount = parse_amount(custom_input.text())
                except ValueError:
                    QMessageBox.warning(dlg, "مبلغ نامعتبر", "مبلغ دلخواه را به‌صورت عدد صحیح وارد کنید.")
                    return
                if not custom_input.text().strip():
                    QMessageBox.warning(dlg, "مبلغ نامعتبر", "مبلغ دلخواه نمی‌تواند خالی باشد.")
                    return
            result["accepted"] = True
            result["discount"] = discount_amount
            result["total"] = repo.calculate_checkout_totals(
                session_time_cost, transfer_cost, snack_total, discount_amount
            )["total"]
            result["custom_amount"] = custom_amount if rb_custom_amount and rb_custom_amount.isChecked() else None
            dlg.accept()

        btn_ok.clicked.connect(accept_checkout)
        btn_cancel.clicked.connect(dlg.reject)
        if dlg.exec() != QDialog.DialogCode.Accepted or not result["accepted"]:
            # Deliberately do not stop/restart self.timer: it is the application
            # heartbeat/display timer, not this system's session timer.
            try:
                self.load_systems()
            except Exception:
                pass
            return

        total = result["total"]
        discount_amount = result["discount"]
        conn3 = None
        payment_info = ""
        try:
            conn3 = database.get_connection()
            cur3 = conn3.cursor()
            if customer_id:
                cur3.execute("SELECT balance FROM customers WHERE id=?", (customer_id,))
                balance_row = cur3.fetchone()
                if not balance_row:
                    raise ValueError("مشتری این نشست در دیتابیس پیدا نشد.")
                balance = to_int_safe(balance_row[0], 0)
                if rb_instant and rb_instant.isChecked():
                    payment_info = f"پرداخت نقدی: {money(total)}"
                elif rb_add_to_account and rb_add_to_account.isChecked():
                    new_balance = balance - total
                    cur3.execute("UPDATE customers SET balance=? WHERE id=?", (new_balance, customer_id))
                    payment_info = f"مبلغ ثبت‌شده در حساب مشتری: {money(total)}\nموجودی جدید: {money(new_balance)}"
                elif rb_custom_amount and rb_custom_amount.isChecked():
                    custom_amount = result["custom_amount"]
                    new_balance = balance - custom_amount
                    cur3.execute("UPDATE customers SET balance=? WHERE id=?", (new_balance, customer_id))
                    payment_info = f"مبلغ دلخواه ثبت‌شده: {money(custom_amount)}\nموجودی جدید: {money(new_balance)}"
                else:
                    payment_info = f"مبلغ فاکتور: {money(total)}"
            else:
                payment_info = f"پرداخت نقدی: {money(total)}"

            # Atomic finalization: either payment/account change and session close
            # are both committed, or neither change is persisted.
            final_session_cost = max(0, to_int_safe(session_time_cost, 0)) + transfer_cost
            cur3.execute("""
                UPDATE sessions
                SET end_time=?, paused_seconds=?, cost=?, snack_cost=?, discount=?
                WHERE id=? AND end_time IS NULL
            """, (checkout_at.strftime("%Y-%m-%d %H:%M:%S"), total_seconds,
                  final_session_cost, snack_total, discount_amount, session_id))
            if cur3.rowcount != 1:
                raise RuntimeError("این نشست قبلاً تسویه شده یا وضعیت آن تغییر کرده است؛ صفحه را تازه‌سازی کنید.")
            cur3.execute("UPDATE systems SET active=0, customer_id=NULL, note='', cost=0 WHERE id=?", (sys_id,))
            conn3.commit()
        except Exception as e:
            if conn3 is not None:
                try:
                    conn3.rollback()
                except Exception:
                    pass
            QMessageBox.warning(self, "خطا در ثبت تسویه", f"تسویه ذخیره نشد و تغییرات مالی برگشت داده شد.\n{e}")
            return
        finally:
            if conn3 is not None:
                try:
                    conn3.close()
                except Exception:
                    pass

        msg = QMessageBox(self)
        msg.setWindowTitle("تسویه با موفقیت ثبت شد")
        msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setText(f"{payment_info}\nتخفیف: {money(discount_amount)}\nجمع نهایی فاکتور: {money(total)}")
        msg.exec()
        try:
            self.load_systems()
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

    def closeEvent(self, event):
        """Persist active intervals and pause open sessions before a normal exit."""
        try:
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = database.get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE systems SET last_update_time=? WHERE active=1",
                    (now_text,),
                )
                conn.commit()
            finally:
                conn.close()

            # -1 makes the current active sessions eligible for recovery even
            # when the heartbeat is fresh; the cutoff was just updated to now.
            self.detect_power_loss(threshold_seconds=-1)
        except Exception:
            # Do not trap the user in the app if recovery fails; the startup
            # recovery path will retry on the next launch.
            pass
        try:
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
        except Exception:
            pass
        event.accept()

