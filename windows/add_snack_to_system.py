# add_snack_to_system.py
import sqlite3
from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QTableWidget, QTableWidgetItem, QSpinBox, QVBoxLayout,
    QHBoxLayout, QSplitter, QMessageBox, QSizePolicy, QPushButton, QLabel, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
import database

DB_PATH = database.DB_PATH

class AddSnackToSystem(QWidget):
    def __init__(self, system_id, parent=None):
        super().__init__(parent)
        self.system_id = system_id

        # مجموعه شناسه‌های انتخاب‌شده
        self.selected_ids = set()
        # ساختار نگهداری انتخاب‌ها بر اساس دسته
        self.selected_by_cat = {}  # {"یخچال":[{id,name,price,qty},...], ...}
        # نگاشت دسته -> جدول دسته‌ای
        self.category_tables = {}
        # نگاشت id -> info (name, price, category)
        self._foods_map = {}
        # نگاشت ردیف جدول انتخاب‌شده -> (category, id)
        self._selected_row_map = {}

        # ویجت‌ها
        self._create_widgets()
        self._build_layout()
        self._connect_signals()

        # بارگذاری داده‌ها
        self.load_snacks()
        self.load_selected_snacks()


    # ---------------- UI ----------------
    def _create_widgets(self):
        # جدول انتخاب‌شده (سمت چپ، ارتفاع بیشتر)
        self.selectedTable = QTableWidget()
        self.selectedTable.setColumnCount(4)
        self.selectedTable.setHorizontalHeaderLabels(["تعداد", "قیمت", "نام", "id"])
        self.selectedTable.setColumnHidden(3, True)
        self.selectedTable.verticalHeader().setVisible(False)
        self.selectedTable.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.selectedTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.selectedTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.selectedTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # سه جدول دسته‌ای (سمت راست بالا، کنار هم)
        self.fridgeTable = QTableWidget()
        self.buffetTable = QTableWidget()
        self.foodTable = QTableWidget()
        for t in (self.fridgeTable, self.buffetTable, self.foodTable):
            t.setColumnCount(3)
            t.setHorizontalHeaderLabels(["قیمت", "نام", "id"])
            t.setColumnHidden(2, True)
            t.verticalHeader().setVisible(False)
            t.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # دکمه‌های ذخیره و بستن
        self.saveBtn = QPushButton("ذخیره")
        self.closeBtn = QPushButton("بستن")

        # نگاشت دسته‌ها (در صورت نیاز نام‌ها را تغییر بده)
        self.category_tables = {
            "یخچال": self.fridgeTable,
            "بوفه": self.buffetTable,
            "غذا": self.foodTable
        }

    def _build_layout(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # left: selectedTable
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)
        left_layout.addWidget(QLabel("خوراکی‌های انتخاب‌شده"))
        left_layout.addWidget(self.selectedTable)
        splitter.addWidget(left_widget)

        # right: دسته‌ها + دکمه‌ها
        right_widget = QWidget()
        right_v = QVBoxLayout(right_widget)
        right_v.setContentsMargins(6, 6, 6, 6)
        right_v.setSpacing(6)

        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)
        top_row_layout.setSpacing(6)
        top_row_layout.addWidget(self.fridgeTable)
        top_row_layout.addWidget(self.buffetTable)
        top_row_layout.addWidget(self.foodTable)

        right_v.addWidget(QLabel("دسته‌ها"))
        right_v.addWidget(top_row)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()
        btn_layout.addWidget(self.saveBtn)
        btn_layout.addWidget(self.closeBtn)
        right_v.addWidget(btn_row)

        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
        self.resize(1000, 600)
        self.setMinimumSize(900, 600)

    def _connect_signals(self):
        for tbl in (self.fridgeTable, self.buffetTable, self.foodTable):
            tbl.itemDoubleClicked.connect(self.on_category_double_clicked)
        self.selectedTable.itemDoubleClicked.connect(self.on_selected_double_clicked)
        self.saveBtn.clicked.connect(self.save_snacks)
        self.closeBtn.clicked.connect(self.close)

    # ---------------- دیتابیس ----------------
    def _get_conn(self):
        return sqlite3.connect(DB_PATH)

    def _get_active_session_id(self):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM sessions WHERE system_id=? AND end_time IS NULL", (self.system_id,))
            s = cur.fetchone()
            return s[0] if s else None
        except Exception:
            return None
        finally:
            conn.close()

    # ---------------- helper: پاک‌سازی ایمن ردیف‌ها ----------------
    def _clear_all_rows_safe(self, tbl):
        """
        حذف ایمن همه ردیف‌ها و ویجت‌های سلولی از tbl.
        حذف از انتها به ابتدا تا ایمن باشد.
        """
        for r in reversed(range(tbl.rowCount())):
            # حذف ویجت‌های سلولی در آن ردیف
            for c in range(tbl.columnCount()):
                w = tbl.cellWidget(r, c)
                if w is not None:
                    try:
                        tbl.removeCellWidget(r, c)
                        w.deleteLater()
                    except Exception:
                        pass
            try:
                tbl.removeRow(r)
            except Exception:
                pass

    # ---------------- بارگذاری دسته‌ها ----------------
    def load_snacks(self):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT f.id, f.name, f.price, fc.name as category_name
                FROM foods f
                LEFT JOIN food_categories fc ON fc.id = f.category_id
                ORDER BY fc.name, f.name
            """)
            rows = cur.fetchall()
        except Exception as e:
            rows = []
        finally:
            conn.close()

        # ساخت mapping id -> info
        self._foods_map = {}
        for fid, name, price, cat in rows:
            cat_name = (cat or "سایر").strip()
            self._foods_map[fid] = {"name": name, "price": price or 0, "category": cat_name}

        # تفکیک بر اساس دسته ولی حذف آیتم‌هایی که در selected_ids هستند
        fridge_items = []
        buffet_items = []
        food_items = []
        others = []
        for fid, info in self._foods_map.items():
            if fid in self.selected_ids:
                continue
            cat = info["category"]
            tup = (fid, info["name"], info["price"])
            if cat == "یخچال":
                fridge_items.append(tup)
            elif cat == "بوفه":
                buffet_items.append(tup)
            elif cat == "غذا":
                food_items.append(tup)
            else:
                others.append(tup)
        food_items.extend(others)

        def fill_table(tbl, items, price_header="قیمت"):
            # پاک‌سازی کامل قبل از پر کردن
            self._clear_all_rows_safe(tbl)
            tbl.setRowCount(len(items))
            tbl.setHorizontalHeaderLabels([price_header, "نام", "id"])
            for r, (fid, name, price) in enumerate(items):
                price_text = f"{int(price):,}" if price is not None else "0"
                it_price = QTableWidgetItem(price_text)
                it_price.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_price.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(r, 0, it_price)

                it_name = QTableWidgetItem(name)
                it_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_name.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(r, 1, it_name)

                it_id = QTableWidgetItem(str(fid))
                it_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(r, 2, it_id)
            tbl.setColumnHidden(2, True)

        fill_table(self.fridgeTable, fridge_items)
        fill_table(self.buffetTable, buffet_items)
        fill_table(self.foodTable, food_items)

    # ---------------- بارگذاری انتخاب‌شده‌ها ----------------
    def load_selected_snacks(self):
        session_id = self._get_active_session_id()
        self.selected_by_cat = {}
        self.selected_ids = set()

        if not session_id:
            self._rebuild_selected_table()
            self.load_snacks()
            return

        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT ss.snack_id, ss.quantity, COALESCE(ss.name_snapshot, f.name, 'خوراکی حذف‌شده'), COALESCE(ss.price_snapshot, f.price, 0), fc.name as category_name
                FROM session_snacks ss
                LEFT JOIN foods f ON ss.snack_id = f.id
                LEFT JOIN food_categories fc ON f.category_id = fc.id
                WHERE ss.session_id=?
            """, (session_id,))
            rows = cur.fetchall()
        except Exception as e:
            rows = []
        finally:
            conn.close()

        for sid, qty, name, price, cat in rows:
            cat_name = (cat or "سایر")
            self.selected_by_cat.setdefault(cat_name, []).append({
                "id": sid, "name": name, "price": price or 0, "qty": qty or 1
            })
            self.selected_ids.add(sid)

        self._rebuild_selected_table()
        self.load_snacks()

    # ---------------- افزودن به انتخاب‌شده (محلی + DB) ----------------
    def _add_item_to_selected(self, sid, name, price, category_name, qty=1):
        if sid in self.selected_ids:
            return
        cat = category_name or "سایر"
        self.selected_by_cat.setdefault(cat, []).append({
            "id": sid, "name": name, "price": price, "qty": qty
        })
        self.selected_ids.add(sid)

        session_id = self._get_active_session_id()
        if session_id:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute("SELECT quantity FROM session_snacks WHERE session_id=? AND snack_id=?", (session_id, sid))
                ex = cur.fetchone()
                if ex:
                    cur.execute("UPDATE session_snacks SET quantity=? WHERE session_id=? AND snack_id=?", (qty, session_id, sid))
                else:
                    cur.execute("INSERT INTO session_snacks (session_id, snack_id, quantity, name_snapshot, price_snapshot) VALUES (?, ?, ?, (SELECT name FROM foods WHERE id=?), (SELECT price FROM foods WHERE id=?))", (session_id, sid, qty, sid, sid))
                cur.execute("""
                    SELECT SUM(ss.quantity * COALESCE(ss.price_snapshot, f.price, 0))
                    FROM session_snacks ss
                    LEFT JOIN foods f ON ss.snack_id = f.id
                    WHERE ss.session_id=?
                """, (session_id,))
                total = cur.fetchone()[0] or 0
                cur.execute("UPDATE sessions SET snack_cost=? WHERE id=?", (total, session_id))
                conn.commit()
            except Exception as e:
                conn.rollback()
            finally:
                conn.close()

        # بازسازی امن selectedTable
        self._rebuild_selected_table()

        # حذف امن از جدول دسته‌ای بر اساس id (نه row)
        for tbl in (self.fridgeTable, self.buffetTable, self.foodTable):
            removed = False
            for r in range(tbl.rowCount()):
                try:
                    id_item = tbl.item(r, 2)
                    if id_item and int(id_item.text()) == sid:
                        # حذف ویجت‌های سلولی آن ردیف اگر وجود دارد
                        for c in range(tbl.columnCount()):
                            w = tbl.cellWidget(r, c)
                            if w is not None:
                                try:
                                    tbl.removeCellWidget(r, c)
                                    w.deleteLater()
                                except Exception:
                                    pass
                        tbl.removeRow(r)
                        removed = True
                        break
                except Exception:
                    continue
            if removed:
                break

    # ---------------- حذف از انتخاب‌شده (محلی + DB) و بازگردانی به دسته ----------------
    def _remove_item_from_selected(self, sid, cat=None):
        removed_item = None
        removed_cat = cat

        # اگر دسته مشخص است، حذف مستقیم بر اساس id در آن دسته
        if cat is not None and cat in self.selected_by_cat:
            lst = self.selected_by_cat[cat]
            for i, it in enumerate(lst):
                if it['id'] == sid:
                    removed_item = lst.pop(i)
                    if not lst:
                        del self.selected_by_cat[cat]
                    break

        # fallback: جستجو در همهٔ دسته‌ها
        if removed_item is None:
            for c, lst in list(self.selected_by_cat.items()):
                for i, it in enumerate(lst):
                    if it['id'] == sid:
                        removed_item = lst.pop(i)
                        removed_cat = c
                        if not lst:
                            del self.selected_by_cat[c]
                        break
                if removed_item:
                    break

        if not removed_item:
            return

        if sid in self.selected_ids:
            self.selected_ids.remove(sid)

        session_id = self._get_active_session_id()
        if session_id:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM session_snacks WHERE session_id=? AND snack_id=?", (session_id, sid))
                cur.execute("""
                    SELECT SUM(ss.quantity * COALESCE(ss.price_snapshot, f.price, 0))
                    FROM session_snacks ss
                    LEFT JOIN foods f ON ss.snack_id = f.id
                    WHERE ss.session_id=?
                """, (session_id,))
                total = cur.fetchone()[0] or 0
                cur.execute("UPDATE sessions SET snack_cost=? WHERE id=?", (total, session_id))
                conn.commit()
            except Exception as e:
                conn.rollback()
            finally:
                conn.close()

        # بازگرداندن به جدول دسته‌ای مربوطه (مرتب‌شده بر اساس نام)
        try:
            fid = removed_item['id']
            name = removed_item['name']
            price = removed_item['price']
            cat_name = removed_cat or self._foods_map.get(fid, {}).get("category", "سایر")
            tbl = self.category_tables.get(cat_name, self.foodTable)

            # جمع‌آوری آیتم‌های فعلی، اضافه کردن آیتم حذف‌شده و مرتب‌سازی
            items = []
            for r in range(tbl.rowCount()):
                try:
                    nid = int(tbl.item(r, 2).text())
                    nname = tbl.item(r, 1).text()
                    nprice = int(tbl.item(r, 0).text().replace(",", "")) if tbl.item(r,0) else 0
                    items.append((nid, nname, nprice))
                except Exception:
                    continue
            items.append((fid, name, price))
            items.sort(key=lambda x: x[1].lower())

            # بازسازی جدول دسته‌ای به‌صورت ایمن
            self._clear_all_rows_safe(tbl)
            tbl.setRowCount(len(items))
            for r, (nid, nname, nprice) in enumerate(items):
                item_price = QTableWidgetItem(f"{int(nprice):,}" if nprice is not None else "0")
                item_price.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_price.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(r, 0, item_price)

                item_name = QTableWidgetItem(nname)
                item_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_name.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(r, 1, item_name)

                item_id = QTableWidgetItem(str(nid))
                item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item_id.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(r, 2, item_id)
            tbl.setColumnHidden(2, True)
        except Exception:
            pass

        self._rebuild_selected_table()
        self.load_snacks()

    # ---------------- بازسازی selectedTable با نقشهٔ ردیف→(دسته,id) ----------------
    def _rebuild_selected_table(self):
        tbl = self.selectedTable

        # 1. مسدود کردن سیگنال‌ها و غیرفعال کردن آپدیت برای ثبات
        try:
            tbl.blockSignals(True)
            tbl.setUpdatesEnabled(False)
        except Exception:
            pass

        # 2. پاک‌سازی ایمن همهٔ ردیف‌ها و ویجت‌ها
        self._clear_all_rows_safe(tbl)

        # 3. محاسبه تعداد ردیف‌ها و تنظیم آن پیش از درج ویجت‌ها
        total_rows = sum(1 + len(lst) for lst in self.selected_by_cat.values()) if self.selected_by_cat else 0
        tbl.setRowCount(total_rows)
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["تعداد", "قیمت", "نام", "id"])
        tbl.setColumnHidden(3, True)
        tbl.verticalHeader().setVisible(False)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # 4. پر کردن جدول و ساخت نقشه ردیف -> (category, id)
        self._selected_row_map = {}
        row = 0
        for cat, items in self.selected_by_cat.items():
            header = QTableWidgetItem(f"— {cat} —")
            header.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            tbl.setSpan(row, 0, 1, 4)
            tbl.setItem(row, 0, header)
            row += 1

            for it in items:
                self._selected_row_map[row] = (cat, it['id'])

                spin = QSpinBox()
                spin.setMinimum(1)
                spin.setMaximum(999)
                spin.setValue(it.get('qty', 1))
                spin.valueChanged.connect(partial(self._on_qty_changed, it['id']))
                tbl.setCellWidget(row, 0, spin)

                price_item = QTableWidgetItem(f"{int(it.get('price') or 0):,}")
                price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                price_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(row, 1, price_item)

                name_item = QTableWidgetItem(it.get('name') or "")
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                name_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(row, 2, name_item)

                id_item = QTableWidgetItem(str(it['id']))
                id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                id_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                tbl.setItem(row, 3, id_item)

                row += 1

        # 5. بازگرداندن آپدیت و سیگنال‌ها و رفرش امن UI
        try:
            tbl.setUpdatesEnabled(True)
            tbl.blockSignals(False)
            QTimer.singleShot(0, tbl.viewport().update)
        except Exception:
            pass

    # ---------------- رویدادها ----------------
    def on_category_double_clicked(self, item):
        try:
            tbl = item.tableWidget()
        except Exception:
            tbl = self.sender()
        row = item.row()
        id_item = tbl.item(row, 2)
        if id_item is None:
            return
        try:
            sid = int(id_item.text())
        except Exception:
            return
        info = self._foods_map.get(sid, {})
        name = info.get("name", "")
        price = info.get("price", 0)
        cat_name = None
        for k, v in self.category_tables.items():
            if v is tbl:
                cat_name = k
                break
        cat_name = cat_name or info.get("category", "سایر")

        self._add_item_to_selected(sid, name, price, cat_name, qty=1)

    def on_selected_double_clicked(self, item):
        row = item.row()
        mapping = getattr(self, "_selected_row_map", {})
        if row not in mapping:
            return
        cat, sid = mapping[row]
        self._remove_item_from_selected(sid, cat=cat)

    # ---------------- تغییر مقدار تعداد ----------------
    def _on_qty_changed(self, sid, val):
        for lst in self.selected_by_cat.values():
            for x in lst:
                if x['id'] == sid:
                    x['qty'] = val
                    break
        session_id = self._get_active_session_id()
        if session_id:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                cur.execute("UPDATE session_snacks SET quantity=? WHERE session_id=? AND snack_id=?", (val, session_id, sid))
                cur.execute("""
                    SELECT SUM(ss.quantity * COALESCE(ss.price_snapshot, f.price, 0))
                    FROM session_snacks ss
                    LEFT JOIN foods f ON ss.snack_id = f.id
                    WHERE ss.session_id=?
                """, (session_id,))
                total = cur.fetchone()[0] or 0
                cur.execute("UPDATE sessions SET snack_cost=? WHERE id=?", (total, session_id))
                conn.commit()
            except Exception as e:
                conn.rollback()
            finally:
                conn.close()

    # ---------------- ذخیره کلی (اختیاری) ----------------
    def save_snacks(self):
        session_id = self._get_active_session_id()
        if not session_id:
            QMessageBox.warning(self, "خطا", "هیچ سشن فعالی برای این سیستم وجود ندارد.")
            return
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM session_snacks WHERE session_id=?", (session_id,))
            total = 0
            for cat, items in self.selected_by_cat.items():
                for it in items:
                    cur.execute("INSERT INTO session_snacks (session_id, snack_id, quantity, name_snapshot, price_snapshot) VALUES (?, ?, ?, (SELECT name FROM foods WHERE id=?), (SELECT price FROM foods WHERE id=?))",
                                (session_id, it['id'], it.get('qty', 1), it['id'], it['id']))
                    total += (it.get('price') or 0) * (it.get('qty') or 0)
            cur.execute("UPDATE sessions SET snack_cost=? WHERE id=?", (total, session_id))
            conn.commit()
            QMessageBox.information(self, "ثبت شد", "خوراکی‌ها با موفقیت ذخیره شدند.")
        except Exception as e:
            conn.rollback()
            QMessageBox.warning(self, "خطا", f"خطا در ذخیره خوراکی‌ها: {e}")
        finally:
            conn.close()