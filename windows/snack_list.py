from PyQt6 import uic
from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QInputDialog, QMessageBox
from PyQt6.QtCore import Qt
import sqlite3

class SnackListWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/snack_list.ui", self)

        self.addButton.clicked.connect(self.add_snack)
        self.searchInput.textChanged.connect(self.search_snacks)

        self.load_snacks()

    def format_price(self, price):
        return f"{price:,}"

    def add_snack(self):
        name, ok1 = QInputDialog.getText(self, "افزودن خوراکی", "نام خوراکی را وارد کنید:")
        if not ok1 or name.strip() == "":
            return

        price_str, ok2 = QInputDialog.getText(self, "افزودن خوراکی", "قیمت را وارد کنید:", text="0")
        if not ok2:
            return

        price = int(price_str.replace(",", ""))

        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO snacks (name, price) VALUES (?, ?)", (name, price))
        conn.commit()
        conn.close()

        self.load_snacks()

    def load_snacks(self):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("SELECT id, name, price FROM snacks")
        snacks = cur.fetchall()

        self.snackTable.setRowCount(len(snacks))
        self.snackTable.setColumnCount(4)
        self.snackTable.setHorizontalHeaderLabels(["حذف", "ویرایش", "قیمت", "نام خوراکی"])

        for row, snack in enumerate(snacks):
            snack_id = snack[0]
            name = snack[1]
            price = snack[2]

            # نام خوراکی
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.snackTable.setItem(row, 3, name_item)
            self.snackTable.setColumnWidth(3, 200)

            # قیمت
            price_item = QTableWidgetItem(self.format_price(price))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.snackTable.setItem(row, 2, price_item)
            self.snackTable.setColumnWidth(2, 200)

            # دکمه حذف
            delete_btn = QPushButton("حذف")
            delete_btn.clicked.connect(lambda _, sid=snack_id: self.delete_snack(sid))
            self.snackTable.setColumnWidth(0, 80)

            delete_layout = QHBoxLayout()
            delete_layout.addWidget(delete_btn)
            delete_layout.setContentsMargins(0, 0, 0, 0)

            delete_widget = QWidget()
            delete_widget.setLayout(delete_layout)
            self.snackTable.setCellWidget(row, 0, delete_widget)

            # دکمه ویرایش
            edit_btn = QPushButton("ویرایش")
            edit_btn.clicked.connect(lambda _, sid=snack_id: self.edit_snack(sid))
            self.snackTable.setColumnWidth(1, 80)

            edit_layout = QHBoxLayout()
            edit_layout.addWidget(edit_btn)
            edit_layout.setContentsMargins(0, 0, 0, 0)

            edit_widget = QWidget()
            edit_widget.setLayout(edit_layout)
            self.snackTable.setCellWidget(row, 1, edit_widget)

        conn.close()


    def search_snacks(self):
        text = self.searchInput.text().strip()

        for row in range(self.snackTable.rowCount()):
            name_item = self.snackTable.item(row, 3)   # ستون نام
            price_item = self.snackTable.item(row, 2)  # ستون قیمت

            name = name_item.text() if name_item else ""
            price = price_item.text() if price_item else ""

            if text in name or text in price:
                self.snackTable.setRowHidden(row, False)
            else:
                self.snackTable.setRowHidden(row, True)

    def delete_snack(self, snack_id):
        reply = QMessageBox.question(
            self,
            "تایید حذف",
            "آیا از حذف خوراکی مطمئن هستید؟"
        )

        if reply == QMessageBox.StandardButton.Yes:
            conn = sqlite3.connect("gamenet.db")
            cur = conn.cursor()
            cur.execute("DELETE FROM snacks WHERE id=?", (snack_id,))
            conn.commit()
            conn.close()

            self.load_snacks()

    def edit_snack(self, snack_id):
        conn = sqlite3.connect("gamenet.db")
        cur = conn.cursor()

        cur.execute("SELECT name, price FROM snacks WHERE id=?", (snack_id,))
        snack = cur.fetchone()

        if snack is None:
            conn.close()
            return

        name, price_value = snack

        new_name, ok1 = QInputDialog.getText(
            self,
            "ویرایش نام",
            "نام جدید را وارد کنید:",
            text=name
        )
        if not ok1:
            conn.close()
            return

        price_str, ok2 = QInputDialog.getText(
            self,
            "ویرایش قیمت",
            "قیمت جدید را وارد کنید:",
            text=self.format_price(price_value)
        )
        if not ok2:
            conn.close()
            return

        new_price = int(price_str.replace(",", ""))

        cur.execute("UPDATE snacks SET name=?, price=? WHERE id=?", (new_name, new_price, snack_id))
        conn.commit()
        conn.close()

        self.load_snacks()