import sqlite3
from PyQt6 import uic
from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QMessageBox, QInputDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class CustomerListWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/customer_list.ui", self)

        self.customerTable.verticalHeader().setVisible(False)

        self.customerTable.itemSelectionChanged.connect(self.select_customer)
        self.selected_customer_id = None

        self.searchInput.textChanged.connect(self.search_customer)

        self.editBtn.clicked.connect(self.edit_customer)
        self.deleteBtn.clicked.connect(self.delete_customer)

        self.load_customers()

    def select_customer(self):
        row = self.customerTable.currentRow()
        if row < 0:
            self.selected_customer_id = None
            return

        # ستون 4 = ID
        id_item = self.customerTable.item(row, 4)
        if id_item:
            self.selected_customer_id = int(id_item.text())

    def delete_customer(self):
        if not self.selected_customer_id:
            QMessageBox.warning(self, "خطا", "لطفاً یک مشتری را انتخاب کنید")
            return

        reply = QMessageBox.question(
            self,
            "تایید حذف",
            "آیا از حذف این مشتری مطمئن هستید؟"
        )

        if reply == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect("gamenet.db")
            cur = conn.cursor()
            cur.execute("DELETE FROM customers WHERE id=?", (self.selected_customer_id,))
            conn.commit()
            conn.close()

            self.load_customers()

    def load_customers(self):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("SELECT id, name, family, code, balance FROM customers ORDER BY balance ASC")
        customers = cur.fetchall()

        self.customerTable.setRowCount(len(customers))
        self.customerTable.setColumnCount(5)
        self.customerTable.setHorizontalHeaderLabels(["شارژ", "کد", "فامیل", "نام", "ID"])

        # ستون ID مخفی
        self.customerTable.setColumnHidden(4, True)

        for row, (cid, name, family, code, balance) in enumerate(customers):

            # شارژ → ستون 0
            balance_item = QTableWidgetItem(f"{balance:,}")
            balance_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # رنگ شارژ
            if balance < 0:
                balance_item.setForeground(QColor("#FF0000"))

            self.customerTable.setItem(row, 0, balance_item)

            # کد → ستون 1
            code_item = QTableWidgetItem(code)
            code_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.customerTable.setItem(row, 1, code_item)

            # فامیل → ستون 2
            family_item = QTableWidgetItem(family)
            family_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.customerTable.setItem(row, 2, family_item)

            # نام → ستون 3
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.customerTable.setItem(row, 3, name_item)

            # ID → ستون 4
            id_item = QTableWidgetItem(str(cid))
            self.customerTable.setItem(row, 4, id_item)

        conn.close()

    def search_customer(self, text):
        text = text.strip().lower()

        for row in range(self.customerTable.rowCount()):
            row_text = ""

            for col in range(self.customerTable.columnCount()):
                item = self.customerTable.item(row, col)
                if item:
                    row_text += item.text().lower() + " "

            self.customerTable.setRowHidden(row, text not in row_text)

    def edit_customer(self):
        if not self.selected_customer_id:
            QMessageBox.warning(self, "خطا", "لطفاً یک مشتری را انتخاب کنید")
            return

        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()
        cur.execute("SELECT name, family, code FROM customers WHERE id=?", (self.selected_customer_id,))
        customer = cur.fetchone()
        conn.close()

        if not customer:
            return

        name, family, code = customer

        new_name, ok1 = QInputDialog.getText(self, "ویرایش نام", "نام جدید:", text=name)
        if not ok1:
            return

        new_family, ok2 = QInputDialog.getText(self, "ویرایش فامیل", "فامیل جدید:", text=family)
        if not ok2:
            return

        new_code, ok3 = QInputDialog.getText(self, "ویرایش کد", "کد جدید:", text=code)
        if not ok3:
            return

        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()
        cur.execute("""
            UPDATE customers
            SET name=?, family=?, code=?
            WHERE id=?
        """, (new_name, new_family, new_code, self.selected_customer_id))
        conn.commit()
        conn.close()

        self.load_customers()