import sqlite3
from PyQt6 import uic
from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QSpinBox, QMessageBox
from PyQt6.QtCore import Qt

class AddSnackToSystem(QWidget):
    def __init__(self, system_id):
        super().__init__()
        uic.loadUi("ui/add_snack_to_system.ui", self)



        self.system_id = system_id
        self.snacks = []              # لیست کامل خوراکی‌ها
        self.selected_ids = set()     # جلوگیری از دوباره اضافه شدن

        self.load_selected_snacks()

        self.deleteBtn.clicked.connect(self.delete_selected_snack)

        # اتصال ویجت‌ها
        self.searchInput.textChanged.connect(self.filter_snacks)
        self.addBtn.clicked.connect(self.add_snack_to_selected)
        self.saveBtn.clicked.connect(self.save_snacks)

        # تنظیم جدول‌ها
        self.snackTable.verticalHeader().setVisible(False)
        self.selectedTable.verticalHeader().setVisible(False)

        self.selectedTable.setColumnCount(4)
        self.selectedTable.setColumnHidden(3, True)

        self.load_snacks()

    # ---------------------------------------------------------
    # لود کردن خوراکی‌ها از دیتابیس
    # ---------------------------------------------------------
    def load_snacks(self):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("SELECT id, name, price FROM snacks ORDER BY name ASC")
        self.snacks = cur.fetchall()

        conn.close()

        # آپدیت جدول
        self.update_snack_table(self.snacks)

        # 🔥 حذف خوراکی‌هایی که قبلاً انتخاب شده‌اند
        rows_to_remove = []
        for r in range(self.snackTable.rowCount()):
            sid = int(self.snackTable.item(r, 2).text())
            if sid in self.selected_ids:
                rows_to_remove.append(r)

        # حذف از snackTable
        for r in reversed(rows_to_remove):
            self.snackTable.removeRow(r)

    # ---------------------------------------------------------
    # آپدیت جدول snackTable
    # ---------------------------------------------------------
    def update_snack_table(self, items):
        self.snackTable.setColumnCount(3)
        self.snackTable.setRowCount(len(items))

        for row, (sid, name, price) in enumerate(items):

            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.snackTable.setItem(row, 1, item_name)

            item_price = QTableWidgetItem(f"{price:,}")
            item_price.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.snackTable.setItem(row, 0, item_price)

            item_id = QTableWidgetItem(str(sid))
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.snackTable.setItem(row, 2, item_id)

        self.snackTable.setColumnHidden(2, True)

    # ---------------------------------------------------------
    # فیلتر کردن خوراکی‌ها با سرچ
    # ---------------------------------------------------------
    def filter_snacks(self):
        text = self.searchInput.text().strip().lower()

        filtered = []
        for sid, name, price in self.snacks:
            if text in name.lower():
                filtered.append((sid, name, price))

        self.update_snack_table(filtered)

    # ---------------------------------------------------------
    # افزودن خوراکی به selectedTable
    # ---------------------------------------------------------
    def add_snack_to_selected(self):
        row = self.snackTable.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "هیچ خوراکی انتخاب نشده است.")
            return

        sid = int(self.snackTable.item(row, 2).text())
        name = self.snackTable.item(row, 1).text()
        price = int(self.snackTable.item(row, 0).text().replace(",", ""))

        # جلوگیری از دوباره اضافه شدن
        if sid in self.selected_ids:
            QMessageBox.warning(self, "خطا", "این خوراکی قبلاً اضافه شده است.")
            return

        self.selected_ids.add(sid)

        # افزودن خوراکی به جدول انتخاب‌شده‌ها
        new_row = self.selectedTable.rowCount()
        self.selectedTable.insertRow(new_row)

        # تعداد
        spin = QSpinBox()
        spin.setMinimum(1)
        spin.setMaximum(50)
        self.selectedTable.setCellWidget(new_row, 0, spin)

        # قیمت
        item_price = QTableWidgetItem(f"{price:,}")
        item_price.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selectedTable.setItem(new_row, 1, item_price)

        # نام
        item_name = QTableWidgetItem(name)
        item_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selectedTable.setItem(new_row, 2, item_name)

        # ستون ID (مخفی)
        self.selectedTable.setItem(new_row, 3, QTableWidgetItem(str(sid)))
        self.selectedTable.setColumnHidden(3, True)

        # حذف خوراکی از لیست اصلی
        self.snackTable.removeRow(row)


    def save_snacks(self):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        # گرفتن سشن فعال
        cur.execute("""
            SELECT id FROM sessions
            WHERE system_id=? AND end_time IS NULL
        """, (self.system_id,))
        session = cur.fetchone()

        if not session:
            QMessageBox.warning(self, "خطا", "هیچ سشن فعالی برای این سیستم وجود ندارد.")
            conn.close()
            return

        session_id = session[0]

        # -----------------------------
        # محاسبه هزینه فقط از selectedTable
        # -----------------------------
        total_cost = 0

        for row in range(self.selectedTable.rowCount()):
            sid = int(self.selectedTable.item(row, 3).text())
            qty = self.selectedTable.cellWidget(row, 0).value()

            # گرفتن قیمت
            cur.execute("SELECT price FROM snacks WHERE id=?", (sid,))
            price = cur.fetchone()[0]

            total_cost += price * qty

            # چک کردن وجود رکورد
            cur.execute("""
                SELECT quantity FROM session_snacks
                WHERE session_id=? AND snack_id=?
            """, (session_id, sid))
            exists = cur.fetchone()

            if exists:
                # 🔥 مقدار جدید جایگزین مقدار قبلی می‌شود
                cur.execute("""
                    UPDATE session_snacks
                    SET quantity = ?
                    WHERE session_id=? AND snack_id=?
                """, (qty, session_id, sid))
            else:
                # 🔥 رکورد جدید
                cur.execute("""
                    INSERT INTO session_snacks (session_id, snack_id, quantity)
                    VALUES (?, ?, ?)
                """, (session_id, sid, qty))

        # -----------------------------
        # ذخیره هزینه نهایی (بدون جمع قبلی)
        # -----------------------------
        cur.execute("""
            UPDATE sessions
            SET snack_cost = ?
            WHERE id=?
        """, (total_cost, session_id))

        conn.commit()
        conn.close()

        QMessageBox.information(self, "ثبت شد", "خوراکی‌ها با موفقیت ذخیره شدند.")
        self.close()

    def delete_selected_snack(self):
        row = self.selectedTable.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "هیچ خوراکی برای حذف انتخاب نشده است.")
            return

        sid = int(self.selectedTable.item(row, 3).text())
        name = self.selectedTable.item(row, 2).text()
        price = int(self.selectedTable.item(row, 1).text().replace(",", ""))

        # حذف از دیتابیس
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("""
            SELECT id FROM sessions
            WHERE system_id=? AND end_time IS NULL
        """, (self.system_id,))
        session = cur.fetchone()

        if session:
            session_id = session[0]

            # حذف رکورد خوراکی از session_snacks
            cur.execute("""
                DELETE FROM session_snacks
                WHERE session_id=? AND snack_id=?
            """, (session_id, sid))

            # هزینه را دوباره محاسبه می‌کنیم
            cur.execute("""
                SELECT ss.quantity, s.price
                FROM session_snacks ss
                JOIN snacks s ON ss.snack_id = s.id
                WHERE ss.session_id=?
            """, (session_id,))
            rows = cur.fetchall()

            new_cost = sum(q * p for q, p in rows)

            cur.execute("""
                UPDATE sessions
                SET snack_cost=?
                WHERE id=?
            """, (new_cost, session_id))

            conn.commit()

        conn.close()

        # حذف از selected_ids
        if sid in self.selected_ids:
            self.selected_ids.remove(sid)

        # حذف از selectedTable
        self.selectedTable.removeRow(row)

        # برگرداندن خوراکی به snackTable
        new_row = self.snackTable.rowCount()
        self.snackTable.insertRow(new_row)

        item_price = QTableWidgetItem(f"{price:,}")
        item_price.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.snackTable.setItem(new_row, 0, item_price)

        item_name = QTableWidgetItem(name)
        item_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.snackTable.setItem(new_row, 1, item_name)

        item_id = QTableWidgetItem(str(sid))
        item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.snackTable.setItem(new_row, 2, item_id)
        self.snackTable.setColumnHidden(2, True)

    def load_selected_snacks(self):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("""
            SELECT id FROM sessions
            WHERE system_id=? AND end_time IS NULL
        """, (self.system_id,))
        session = cur.fetchone()

        if not session:
            conn.close()
            return

        session_id = session[0]

        cur.execute("""
            SELECT ss.snack_id, ss.quantity, s.name, s.price
            FROM session_snacks ss
            JOIN snacks s ON ss.snack_id = s.id
            WHERE ss.session_id=?
        """, (session_id,))
        rows = cur.fetchall()

        self.selectedTable.setRowCount(0)

        for snack_id, qty, name, price in rows:
            new_row = self.selectedTable.rowCount()
            self.selectedTable.insertRow(new_row)

            # تعداد
            spin = QSpinBox()
            spin.setMinimum(1)
            spin.setMaximum(50)
            spin.setValue(qty)
            self.selectedTable.setCellWidget(new_row, 0, spin)

            # قیمت
            item_price = QTableWidgetItem(f"{price:,}")
            item_price.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.selectedTable.setItem(new_row, 1, item_price)

            # نام
            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.selectedTable.setItem(new_row, 2, item_name)

            # ID
            self.selectedTable.setItem(new_row, 3, QTableWidgetItem(str(snack_id)))
            self.selectedTable.setColumnHidden(3, True)

            # جلوگیری از دوباره انتخاب شدن
            self.selected_ids.add(snack_id)

            # 🔥 غیرفعال کردن خوراکی در snackTable
            for r in range(self.snackTable.rowCount()):
                if int(self.snackTable.item(r, 2).text()) == snack_id:
                    for c in range(self.snackTable.columnCount()):
                        item = self.snackTable.item(r, c)
                        if item:
                            item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # فقط نمایش، بدون انتخاب
                    break

        conn.close()