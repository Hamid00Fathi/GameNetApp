from PyQt6.QtWidgets import (
    QWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QInputDialog,
    QMessageBox, QComboBox, QLabel, QDialog, QVBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QSizePolicy, QHeaderView
)
from system_repository import (
    get_all_systems, get_system_by_id, update_system, add_system,
    system_name_exists, remove_system
)
from PyQt6.QtCore import Qt
import re
import sqlite3
import database
import os, sys

DB_PATH = database.DB_PATH


class System_List(QWidget):
    def __init__(self):
        super().__init__()

        from windows.ui_builder import build_ui
        build_ui(self, 'system_list')

        # اتصال دکمه افزودن (اگر در UI وجود دارد)
        if hasattr(self, "addButton"):
            self.addButton.clicked.connect(self.add_systems)

        # اتصال سوییچ حالت
        if self.modeCombo:
            self.modeCombo.currentIndexChanged.connect(self.load_systems)

        # تنظیم اندازه جدول ساخته‌شده با PyQt6
        self.systemTable.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        header = self.systemTable.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.systemTable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # وضعیت اولیه دکمه‌های پایین و اتصال سیگنال انتخاب جدول
        try:
            # اگر دکمه‌ها در UI وجود دارند، غیرفعال‌شان کن تا وقتی ردیفی انتخاب نشده فعال نشوند
            if hasattr(self, "editButton"):
                self.editButton.setEnabled(False)
            if hasattr(self, "deleteButton"):
                self.deleteButton.setEnabled(False)
        except Exception:
            pass

        # نگهداری شناسهٔ انتخاب‌شده
        self._selected_system_id = None

        # وقتی انتخاب جدول تغییر کند، handler اجرا شود
        # (اطمینان: systemTable از .ui بارگذاری شده و موجود است)
        try:
            self.systemTable.itemSelectionChanged.connect(self.on_system_selection_changed)
        except Exception:
            pass

        # وصل کردن دکمه‌های پایین به handlerها
        try:
            if hasattr(self, "editButton"):
                self.editButton.clicked.connect(self.on_bottom_edit_clicked)
            if hasattr(self, "deleteButton"):
                self.deleteButton.clicked.connect(self.on_bottom_delete_clicked)
        except Exception:
            pass

        # بارگذاری اولیه
        self.load_systems()

    def format_price(self, price):
        try:
            return f"{int(price):,}"
        except Exception:
            try:
                return f"{int(float(price)):,}"
            except Exception:
                return str(price or 0)

    def add_systems(self):
        name, ok1 = QInputDialog.getText(self, "افزودن سیستم", "نام سیستم را وارد کنید:")
        if not ok1 or name.strip() == "":
            return

        if system_name_exists(name):
            QMessageBox.warning(self, "خطا!", "این سیستم قبلا ذخیره شده است")
            return

        price_str, ok2 = QInputDialog.getText(self, "افزودن سیستم", "قیمت هر ساعت را وارد کنید", text="50000")
        if not ok2:
            return

        if price_str == "0":
            QMessageBox.warning(self, "خطا!", "قیمت سیستم نباید 0 باشد")
            return

        try:
            price = int(price_str.replace(",", ""))
            add_system(name, price)
        except Exception:
            QMessageBox.warning(self, "خطا", "لطفا مبلغ معتبر وارد کنید")
            return

        self.load_systems()

    def safe_sort_key(self, name):
        alpha = re.sub(r'\d+', '', name).strip().lower()
        nums = re.findall(r'\d+', name)
        num = int(nums[0]) if nums else 0
        return (alpha, num)

    # ---------- توابع کمکی ps_rates ----------
    def _count_rates_for_system(self, system_id):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM ps_rates WHERE system_id=?", (system_id,))
        r = cur.fetchone()
        conn.close()
        return r[0] if r else 0

    def _ps_rates_has_name_column(self):
        if getattr(self, "_ps_rates_name_column_checked", False):
            return getattr(self, "_ps_rates_has_name", False)

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA table_info(ps_rates)")
            cols = cur.fetchall()
            has_name = any(c[1] == "name" for c in cols)
        except Exception:
            has_name = False
        finally:
            conn.close()

        self._ps_rates_name_column_checked = True
        self._ps_rates_has_name = has_name
        return has_name

    def _has_rates(self, system_id):
        return self._count_rates_for_system(system_id) > 0

    def _get_rates_for_system(self, system_id):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            # بررسی وجود ستون name (یکبار کش می‌شود)
            cur.execute("PRAGMA table_info(ps_rates)")
            cols = cur.fetchall()
            has_name = any(c[1] == "name" for c in cols)
            if has_name:
                cur.execute("SELECT id, controllers_count, price_per_hour, name FROM ps_rates WHERE system_id=? ORDER BY controllers_count", (system_id,))
                rows = cur.fetchall()
            else:
                cur.execute("SELECT id, controllers_count, price_per_hour FROM ps_rates WHERE system_id=? ORDER BY controllers_count", (system_id,))
                rows3 = cur.fetchall()
                rows = [(r[0], r[1], r[2], None) for r in rows3]
        except Exception:
            rows = []
        finally:
            conn.close()
        return rows

    def _set_rate(self, system_id, controllers_count, price):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ps_rates (system_id, controllers_count, price_per_hour)
            VALUES (?, ?, ?)
            ON CONFLICT(system_id, controllers_count) DO UPDATE SET price_per_hour=excluded.price_per_hour
        """, (system_id, controllers_count, price))
        conn.commit()
        conn.close()

    def _delete_rate(self, rate_id):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM ps_rates WHERE id=?", (rate_id,))
        conn.commit()
        conn.close()

    # ---------- تبدیل بین تک و چند تعرفه ----------
    def convert_system_to_multi(self, system_id):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (system_id,))
        r = cur.fetchone()
        price = r[0] if r and r[0] is not None else 0
        cur.execute("""
            INSERT INTO ps_rates (system_id, controllers_count, price_per_hour)
            VALUES (?, ?, ?)
            ON CONFLICT(system_id, controllers_count) DO UPDATE SET price_per_hour=excluded.price_per_hour
        """, (system_id, 1, price))
        # سیستم چندتعرفه‌ای نباید به قیمت تک‌تعرفه‌ای قدیمی fallback کند.
        # هنگام تبدیل مجدد به تک‌تعرفه، قیمت از اولین ps_rate بازیابی می‌شود.
        cur.execute("UPDATE systems SET price_per_hour=0 WHERE id=?", (system_id,))
        conn.commit()
        conn.close()
        self.load_systems()

    def convert_system_to_single(self, system_id):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT price_per_hour FROM ps_rates WHERE system_id=? ORDER BY controllers_count LIMIT 1", (system_id,))
        r = cur.fetchone()
        if r:
            chosen_price = r[0] if r[0] is not None else 0
            cur.execute("UPDATE systems SET price_per_hour=? WHERE id=?", (chosen_price, system_id))
        # حذف تمام ردیف‌های ps_rates برای این سیستم
        cur.execute("DELETE FROM ps_rates WHERE system_id=?", (system_id,))
        conn.commit()
        conn.close()
        self.load_systems()

    def on_system_selection_changed(self):
        selected_items = self.systemTable.selectedItems()
        if not selected_items:
            self._selected_system_id = None
            try:
                if hasattr(self, "editButton"):
                    self.editButton.setEnabled(False)
                if hasattr(self, "deleteButton"):
                    self.deleteButton.setEnabled(False)
            except Exception:
                pass
            return

        row = self.systemTable.currentRow()
        item = self.systemTable.item(row, 1)  # ستون 1 = نام سیستم در load_systems
        system_id = None
        if item is not None:
            try:
                system_id = item.data(Qt.ItemDataRole.UserRole)
            except Exception:
                system_id = None

        self._selected_system_id = system_id

        try:
            if hasattr(self, "editButton"):
                self.editButton.setEnabled(bool(system_id))
            if hasattr(self, "deleteButton"):
                self.deleteButton.setEnabled(bool(system_id))
        except Exception:
            pass

    def on_bottom_edit_clicked(self):
        sid = getattr(self, "_selected_system_id", None)
        if not sid:
            QMessageBox.information(self, "انتخاب کنید", "ابتدا یک سیستم انتخاب کنید")
            return

        # اگر متد ویرایش اختصاصی وجود دارد از آن استفاده کن
        if hasattr(self, "open_edit_system_dialog"):
            try:
                self.open_edit_system_dialog(sid)
                self.load_systems()
                return
            except Exception:
                pass

        # fallback ساده: ویرایش نام و قیمت
        try:
            system = get_system_by_id(sid)
        except Exception:
            system = None

        if not system:
            QMessageBox.warning(self, "خطا", "سیستم پیدا نشد")
            return

        current_name = system[1] if len(system) > 1 else ""
        current_price = system[2] if len(system) > 2 else 0

        new_name, ok1 = QInputDialog.getText(self, "ویرایش سیستم", "نام جدید:", text=str(current_name))
        if not ok1:
            return
        price_str, ok2 = QInputDialog.getText(self, "ویرایش سیستم", "قیمت جدید:", text=str(current_price))
        if not ok2:
            return

        try:
            new_price = int(str(price_str).replace(",", "").strip())
        except Exception:
            QMessageBox.warning(self, "خطا", "قیمت معتبر وارد کنید")
            return

        try:
            update_system(sid, new_name, new_price)
            self.load_systems()
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"خطا در به‌روزرسانی: {e}")


    def on_bottom_delete_clicked(self):
        """
        حذف سیستم انتخاب‌شده با تایید کاربر.
        """
        sid = getattr(self, "_selected_system_id", None)
        if not sid:
            QMessageBox.information(self, "انتخاب کنید", "ابتدا یک سیستم انتخاب کنید")
            return

        reply = QMessageBox.question(self, "تایید حذف", "آیا از حذف این سیستم مطمئن هستید؟")
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            remove_system(sid)
        except Exception:
            # fallback: حذف مستقیم از sqlite اگر remove_system موجود نبود
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("DELETE FROM session_rate_changes WHERE session_id IN (SELECT id FROM sessions WHERE system_id=?)", (sid,))
                cur.execute("DELETE FROM session_snacks WHERE session_id IN (SELECT id FROM sessions WHERE system_id=?)", (sid,))
                cur.execute("DELETE FROM sessions WHERE system_id=?", (sid,))
                cur.execute("DELETE FROM ps_rates WHERE system_id=?", (sid,))
                cur.execute("DELETE FROM systems WHERE id=?", (sid,))
                conn.commit()
                conn.close()
            except Exception as e:
                QMessageBox.warning(self, "خطا", f"خطا در حذف: {e}")
                return

        # پاکسازی انتخاب و رفرش جدول
        self._selected_system_id = None
        try:
            if hasattr(self, "editButton"):
                self.editButton.setEnabled(False)
            if hasattr(self, "deleteButton"):
                self.deleteButton.setEnabled(False)
        except Exception:
            pass
        self.load_systems()


    def open_manage_rates_dialog(self, system_id, system_name):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QHBoxLayout, QLineEdit, QPushButton, QMessageBox, QInputDialog
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QRegularExpressionValidator
        from PyQt6.QtCore import QRegularExpression

        dlg = QDialog(self)
        dlg.setWindowTitle(f"مدیریت تعرفه‌ها - {system_name}")
        dlg.resize(480, 420)
        layout = QVBoxLayout(dlg)

        rates_list = QListWidget()
        layout.addWidget(rates_list)

        def refresh_list():
            rates_list.clear()
            for r in self._get_rates_for_system(system_id):
                # پشتیبانی از فرمت 3 یا 4 عضوی
                if len(r) == 4:
                    rate_id, controllers_count, price, name = r
                elif len(r) == 3:
                    rate_id, controllers_count, price = r
                    name = None
                else:
                    continue

                if name:
                    label = f"{name} — {self.format_price(price)}"
                else:
                    label = f"{controllers_count} — {self.format_price(price)}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, rate_id)
                rates_list.addItem(item)

        refresh_list()

        # ورودی‌ها برای افزودن/ویرایش
        input_layout = QHBoxLayout()
        name_input = QLineEdit()
        name_input.setPlaceholderText("نام تعرفه؟")

        cnt_input = QLineEdit()
        cnt_input.setPlaceholderText("تعداد دسته (مثلاً 2 یا متن دلخواه)")
        try:
            cnt_input.setInputMask("")
            cnt_input.setValidator(None)
        except Exception:
            pass

        price_input = QLineEdit()
        price_input.setPlaceholderText("قیمت هر ساعت (مثلاً 15000)")
        price_input.setValidator(QRegularExpressionValidator(QRegularExpression(r'^\d{1,20}$'), price_input))

        if self._ps_rates_has_name_column():
            input_layout.addWidget(name_input)
            input_layout.addWidget(price_input)
        else:
            input_layout.addWidget(cnt_input)
            input_layout.addWidget(price_input)

        layout.addLayout(input_layout)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("افزودن/بروزرسانی")
        edit_btn = QPushButton("ویرایش انتخاب‌شده")
        del_btn = QPushButton("حذف انتخاب‌شده")
        convert_to_single_btn = QPushButton("تبدیل به تک تعرفه‌ای")
        close_btn = QPushButton("بستن")

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addWidget(convert_to_single_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        def _save_rate(system_id, controllers_count, price_per_hour, name=None):
            # تلاش برای فراخوانی متد داخلی کلاس
            try:
                # اگر متد self._set_rate پارامتر name را قبول کند، آن را پاس می‌دهیم
                self._set_rate(system_id, controllers_count, price_per_hour, name)
                return
            except TypeError:
                # ممکن است امضای _set_rate قدیمی باشد؛ ادامه می‌دهیم به استفاده از database
                pass
            except AttributeError:
                # متد وجود ندارد؛ ادامه می‌دهیم
                pass

            # استفاده از توابع موجود در ماژول database
            try:
                # اگر database.set_rate وجود دارد از آن استفاده کن
                if hasattr(database, "set_rate"):
                    database.set_rate(system_id, controllers_count, price_per_hour, name)
                    return
                # یا نام دیگر add_or_update_rate
                if hasattr(database, "add_or_update_rate"):
                    database.add_or_update_rate(system_id, controllers_count, price_per_hour, name)
                    return
                # fallback: درج مستقیم در sqlite
                conn = database.get_connection()
                cur = conn.cursor()
                if name is not None:
                    cur.execute("""
                        INSERT INTO ps_rates (system_id, controllers_count, price_per_hour, name)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(system_id, controllers_count) DO UPDATE SET
                            price_per_hour=excluded.price_per_hour,
                            name=excluded.name
                    """, (system_id, controllers_count, price_per_hour, name))
                else:
                    cur.execute("""
                        INSERT INTO ps_rates (system_id, controllers_count, price_per_hour)
                        VALUES (?, ?, ?)
                        ON CONFLICT(system_id, controllers_count) DO UPDATE SET
                            price_per_hour=excluded.price_per_hour
                    """, (system_id, controllers_count, price_per_hour))
                conn.commit()
                conn.close()
            except Exception as e:
                QMessageBox.warning(dlg, "خطا", f"خطا در ذخیره تعرفه: {e}")

        def _insert_rate_with_auto_controllers(system_id, price, name):
            conn = database.get_connection()
            cur = conn.cursor()
            # پیدا کردن بیشترین controllers_count موجود برای این system
            cur.execute("SELECT MAX(controllers_count) FROM ps_rates WHERE system_id=?", (system_id,))
            r = cur.fetchone()
            max_cnt = r[0] if r and r[0] is not None else 0
            new_cnt = max_cnt + 1
            # درج با controllers_count جدید و نام
            cur.execute("""
                INSERT INTO ps_rates (system_id, controllers_count, price_per_hour, name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(system_id, controllers_count) DO UPDATE SET
                    price_per_hour=excluded.price_per_hour,
                    name=excluded.name
            """, (system_id, new_cnt, price, name))
            conn.commit()
            conn.close()
            return new_cnt

        def _update_rate_by_id(rate_id, controllers_count, price_per_hour, name):
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE ps_rates
                SET controllers_count=?, price_per_hour=?, name=?
                WHERE id=?
            """, (controllers_count, price_per_hour, name, rate_id))
            conn.commit()
            conn.close()

        def on_add():
            # حالت با نام تعرفه
            if self._ps_rates_has_name_column():
                name_val = name_input.text().strip() or None
                price_text = price_input.text().replace(",", "").strip()
                if price_text == "":
                    QMessageBox.warning(dlg, "خطا", "قیمت را وارد کنید")
                    return
                try:
                    price = int(price_text)
                except Exception:
                    QMessageBox.warning(dlg, "خطا", "قیمت معتبر وارد کنید")
                    return
                if not name_val:
                    QMessageBox.warning(dlg, "خطا", "نام تعرفه را وارد کنید")
                    return
                try:
                    # درج با controllers_count خودکار (MAX+1)
                    new_cnt = _insert_rate_with_auto_controllers(system_id, price, name_val)
                except Exception as e:
                    QMessageBox.warning(dlg, "خطا", f"خطا در ذخیره تعرفه: {e}")
                    return
                name_input.clear()
                price_input.clear()
            else:
                # حالت قدیمی: cnt + price
                cnt_text = cnt_input.text().strip()
                price_text = price_input.text().replace(",", "").strip()
                if cnt_text == "" or price_text == "":
                    QMessageBox.warning(dlg, "خطا", "مقادیر معتبر وارد کنید")
                    return
                try:
                    cnt = int(cnt_text)
                    price = int(price_text)
                except Exception:
                    QMessageBox.warning(dlg, "خطا", "مقادیر معتبر وارد کنید")
                    return
                try:
                    # درج/بروزرسانی با cnt مشخص
                    _save_rate(system_id, cnt, price, None)
                except Exception as e:
                    QMessageBox.warning(dlg, "خطا", f"خطا در ذخیره تعرفه: {e}")
                    return
                cnt_input.clear()
                price_input.clear()
            refresh_list()

        def on_edit():
            item = rates_list.currentItem()
            if not item:
                QMessageBox.information(dlg, "انتخاب کنید", "یک تعرفه انتخاب کنید")
                return
            rate_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                conn = database.get_connection()
                cur = conn.cursor()
                if self._ps_rates_has_name_column():
                    cur.execute("SELECT controllers_count, price_per_hour, name FROM ps_rates WHERE id=?", (rate_id,))
                else:
                    cur.execute("SELECT controllers_count, price_per_hour FROM ps_rates WHERE id=?", (rate_id,))
                r = cur.fetchone()
                conn.close()
            except Exception as e:
                QMessageBox.warning(dlg, "خطا", f"خطا در خواندن دیتابیس: {e}")
                return

            if r:
                if self._ps_rates_has_name_column():
                    # پر کردن فیلدها برای ویرایش
                    cnt_input.setText(str(r[0]))
                    price_input.setText(str(int(r[1])))
                    name_input.setText(r[2] or "")
                    # حالا بازنویسی دکمه افزودن برای تبدیل به عمل "ذخیره ویرایش"
                    def save_edit():
                        name_val = name_input.text().strip() or None
                        price_text = price_input.text().replace(",", "").strip()
                        cnt_text = cnt_input.text().strip()
                        if price_text == "" or cnt_text == "":
                            QMessageBox.warning(dlg, "خطا", "مقادیر معتبر وارد کنید")
                            return
                        try:
                            price = int(price_text)
                            cnt = int(cnt_text)
                        except Exception:
                            QMessageBox.warning(dlg, "خطا", "مقادیر معتبر وارد کنید")
                            return
                        try:
                            _update_rate_by_id(rate_id, cnt, price, name_val)
                        except Exception as e:
                            QMessageBox.warning(dlg, "خطا", f"خطا در به‌روزرسانی: {e}")
                            return
                        refresh_list()
                        # بازگرداندن رفتار دکمه افزودن به حالت اولیه
                        add_btn.clicked.disconnect()
                        add_btn.clicked.connect(on_add)
                        edit_btn.setEnabled(True)
                        del_btn.setEnabled(True)
                        # پاک کردن فیلدها
                        name_input.clear()
                        price_input.clear()
                        cnt_input.clear()

                    # تغییر موقت رفتار دکمه افزودن به ذخیره ویرایش
                    try:
                        add_btn.clicked.disconnect()
                    except Exception:
                        pass
                    add_btn.clicked.connect(save_edit)
                    edit_btn.setEnabled(False)
                    del_btn.setEnabled(False)
                else:
                    cnt_input.setText(str(r[0]))
                    price_input.setText(str(int(r[1])))
                    # مشابه بالا می‌توان ویرایش برای حالت قدیمی پیاده کرد
            else:
                QMessageBox.warning(dlg, "خطا", "ردیف پیدا نشد")

        def on_delete():
            item = rates_list.currentItem()
            if not item:
                QMessageBox.information(dlg, "انتخاب کنید", "یک تعرفه انتخاب کنید")
                return
            rate_id = item.data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(dlg, "حذف تعرفه", "آیا از حذف این تعرفه مطمئنی؟")
            if reply == QMessageBox.StandardButton.Yes:
                # تلاش برای استفاده از متد داخلی یا database
                try:
                    if hasattr(self, "_delete_rate"):
                        self._delete_rate(rate_id)
                    elif hasattr(database, "delete_rate"):
                        database.delete_rate(rate_id)
                    else:
                        conn = database.get_connection()
                        cur = conn.cursor()
                        cur.execute("DELETE FROM ps_rates WHERE id=?", (rate_id,))
                        conn.commit()
                        conn.close()
                except Exception as e:
                    QMessageBox.warning(dlg, "خطا", f"خطا در حذف تعرفه: {e}")
                refresh_list()

        def on_convert_to_single():
            reply = QMessageBox.question(dlg, "تبدیل به تک تعرفه‌ای", "آیا می‌خواهید این سیستم را به تک تعرفه‌ای تبدیل کنید؟ تمام تعرفه‌ها حذف خواهند شد و یکی به عنوان قیمت واحد انتخاب می‌شود.")
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    if hasattr(self, "convert_system_to_single"):
                        self.convert_system_to_single(system_id)
                    else:
                        # fallback ساده: برداشتن اولین نرخ و حذف بقیه
                        conn = database.get_connection()
                        cur = conn.cursor()
                        cur.execute("SELECT price_per_hour FROM ps_rates WHERE system_id=? LIMIT 1", (system_id,))
                        r = cur.fetchone()
                        price = r[0] if r and r[0] is not None else 0
                        cur.execute("DELETE FROM ps_rates WHERE system_id=?", (system_id,))
                        cur.execute("UPDATE systems SET price_per_hour=? WHERE id=?", (price, system_id))
                        conn.commit()
                        conn.close()
                    dlg.accept()
                except Exception as e:
                    QMessageBox.warning(dlg, "خطا", f"خطا در تبدیل به تک تعرفه‌ای: {e}")

        def on_convert_to_multi():
            reply = QMessageBox.question(dlg, "تبدیل به چند تعرفه‌ای", "آیا می‌خواهید این سیستم را به چند تعرفه‌ای تبدیل کنید؟ یک تعرفه اولیه اضافه خواهد شد.")
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    if self._ps_rates_has_name_column():
                        name_val, ok = QInputDialog.getText(dlg, "نام تعرفه اولیه", "نام تعرفه اولیه را وارد کنید:", text="ساعت عادی")
                        if ok:
                            conn = database.get_connection()
                            cur = conn.cursor()
                            cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (system_id,))
                            r = cur.fetchone()
                            price = r[0] if r and r[0] is not None else 0
                            conn.close()
                            # تبدیل باید هم تعرفه را ایجاد کند و هم نرخ پایهٔ تک‌تعرفه‌ای را پاک کند.
                            # هر دو تغییر در یک تراکنش انجام می‌شوند تا سیستم در وضعیت دوگانه نماند.
                            conn = database.get_connection()
                            try:
                                cur = conn.cursor()
                                cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (system_id,))
                                r = cur.fetchone()
                                price = r[0] if r and r[0] is not None else 0
                                cur.execute("""
                                    INSERT INTO ps_rates (system_id, controllers_count, price_per_hour, name)
                                    VALUES (?, 1, ?, ?)
                                    ON CONFLICT(system_id, controllers_count) DO UPDATE SET
                                        price_per_hour=excluded.price_per_hour, name=excluded.name
                                """, (system_id, price, name_val.strip() or "ساعت عادی"))
                                cur.execute("UPDATE systems SET price_per_hour=0 WHERE id=?", (system_id,))
                                conn.commit()
                            except Exception:
                                conn.rollback()
                                raise
                            finally:
                                conn.close()
                            self.load_systems()
                            dlg.accept()
                            return
                    if hasattr(self, "convert_system_to_multi"):
                        self.convert_system_to_multi(system_id)
                    else:
                        # fallback: اضافه کردن یک نرخ پیش‌فرض با controllers_count=1
                        conn = database.get_connection()
                        cur = conn.cursor()
                        cur.execute("SELECT price_per_hour FROM systems WHERE id=?", (system_id,))
                        r = cur.fetchone()
                        price = r[0] if r and r[0] is not None else 0
                        cur.execute("""
                            INSERT INTO ps_rates (system_id, controllers_count, price_per_hour, name)
                            VALUES (?, 1, ?, ?)
                            ON CONFLICT(system_id, controllers_count) DO UPDATE SET price_per_hour=excluded.price_per_hour
                        """, (system_id, price, "ساعت عادی"))
                        conn.commit()
                        conn.close()
                        self.load_systems()
                        dlg.accept()
                except Exception as e:
                    QMessageBox.warning(dlg, "خطا", f"خطا در تبدیل به چند تعرفه‌ای: {e}")

        add_btn.clicked.connect(on_add)
        edit_btn.clicked.connect(on_edit)
        del_btn.clicked.connect(on_delete)
        convert_to_single_btn.clicked.connect(on_convert_to_single)
        close_btn.clicked.connect(dlg.accept)

        dlg.exec()
        self.load_systems()

    # ---------- بارگذاری جدول با فیلتر تک/چند تعرفه ----------
    def load_systems(self):
        systems = get_all_systems()
        systems.sort(key=lambda s: self.safe_sort_key(s[1]))

        # تعیین حالت از ComboBox (اگر وجود دارد)
        multi_mode = False
        if hasattr(self, "modeCombo") and self.modeCombo is not None:
            multi_mode = (self.modeCombo.currentIndex() == 1)

        # فقط 2 ستون: ستون 0 = قیمت/تعرفه (یا ویجت)، ستون 1 = نام سیستم
        self.systemTable.setColumnCount(2)
        if multi_mode:
            self.systemTable.setHorizontalHeaderLabels(["تعرفه‌ها", "نام سیستم"])
        else:
            self.systemTable.setHorizontalHeaderLabels(["قیمت هر ساعت", "نام سیستم"])

        # --- پاک‌سازی ایمن ویجت‌های سلولی قبل از پاک کردن محتوا ---
        prev_rows = self.systemTable.rowCount()
        prev_cols = self.systemTable.columnCount()
        for r in range(prev_rows):
            for c in range(prev_cols):
                w = self.systemTable.cellWidget(r, c)
                if w is not None:
                    self.systemTable.removeCellWidget(r, c)

        self.systemTable.clearContents()

        # فیلتر کردن سیستم‌ها بر اساس حالت انتخابی
        filtered = []
        for s in systems:
            sid = s[0]
            has_rates = self._has_rates(sid)
            if multi_mode:
                if has_rates:
                    filtered.append(s)
            else:
                if not has_rates:
                    filtered.append(s)

        self.systemTable.setRowCount(len(filtered))
        self.systemTable.setMinimumWidth(0)
        self.systemTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.systemTable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.systemTable.verticalHeader().setDefaultSectionSize(58)

        for row, system in enumerate(filtered):
            system_id = system[0]
            name = system[1]
            # فرض معمول: price در اندیس 2 قرار دارد؛ اگر در دیتابیس تو متفاوت است این را اصلاح کن
            try:
                price = system[2]
            except Exception:
                price = 0

            # نام سیستم (ستون 1)
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # ذخیره system_id در UserRole تا بعداً بتوانیم آن را بخوانیم
            try:
                name_item.setData(Qt.ItemDataRole.UserRole, system_id)
            except Exception:
                pass
            self.systemTable.setItem(row, 1, name_item)

            # ستون 0: یا ویجت مدیریت تعرفه (multi_mode) یا قیمت + دکمه تبدیل
            if multi_mode:
                count = self._count_rates_for_system(system_id)
                container = QWidget()
                hl = QHBoxLayout(container)
                hl.setContentsMargins(4, 3, 4, 3)
                hl.setSpacing(5)
                lbl = QLabel(str(count))
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                btn = QPushButton("مدیریت تعرفه‌ها")
                btn.setMinimumWidth(0)
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                btn.clicked.connect(lambda _, sid=system_id, sname=name: self.open_manage_rates_dialog(sid, sname))
                hl.addWidget(lbl)
                hl.addWidget(btn)
                self.systemTable.setCellWidget(row, 0, container)
            else:
                container = QWidget()
                hl = QHBoxLayout(container)
                hl.setContentsMargins(4, 3, 4, 3)
                hl.setSpacing(5)
                price_lbl = QLabel(self.format_price(price))
                price_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                convert_btn = QPushButton("تبدیل به چندتعرفه‌ای")
                convert_btn.setMinimumWidth(0)
                convert_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                if self._has_rates(system_id):
                    convert_btn.setEnabled(False)
                convert_btn.clicked.connect(lambda _, sid=system_id: self.convert_system_to_multi(sid))
                hl.addWidget(price_lbl)
                hl.addWidget(convert_btn)
                self.systemTable.setCellWidget(row, 0, container)


    def delete_system(self, system_id):
        reply = QMessageBox.question(self, "تایید حذف", "آیا از حذف سیستم مطمن هستید؟!")
        if reply == QMessageBox.StandardButton.Yes:
            remove_system(system_id)
            # حذف نرخ‌های مرتبط در ps_rates
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM ps_rates WHERE system_id=?", (system_id,))
            conn.commit()
            conn.close()
            self.load_systems()

    def edit_system(self, system_id):
        system = get_system_by_id(system_id)
        if system is None:
            return

        name = system[1]
        price_value = system[2]

        new_name, ok1 = QInputDialog.getText(self, "ویرایش نام", "نام جدید را وارد کنید:", text=name)
        if not ok1:
            return

        if new_name != name and system_name_exists(new_name):
            QMessageBox.warning(self, "خطا!", "این نام سیستم قبلا ثبت شده است")
            return

        price_str, ok2 = QInputDialog.getText(self, "ویرایش قیمت", "قیمت هر ساعت را وارد کنید:", text=self.format_price(price_value))
        if not ok2:
            return

        try:
            new_price = int(price_str.replace(",", ""))
            update_system(system_id, new_name, new_price)
        except Exception:
            QMessageBox.warning(self, "خطا", "لطفا مبلغ معتبر وارد کنید")
            return

        self.load_systems()