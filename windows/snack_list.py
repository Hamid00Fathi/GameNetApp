# snack_list.py
from PyQt6.QtWidgets import (
    QWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QInputDialog, QMessageBox,
    QTableWidget, QVBoxLayout, QHeaderView, QLabel, QSizePolicy, QLineEdit
)
from PyQt6.QtCore import Qt
import os, sys

from snack_repository import (
    ensure_schema, get_all_sections, get_snacks_by_section,
    add_snack, snack_name_exists, delete_snack, update_snack
)


class SnackListWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("مدیریت خوراکی ها")
        self.resize(1100 , 600)

        ensure_schema()

        # main layout
        existing_layout = self.layout()
        if existing_layout is None:
            main_layout = QVBoxLayout(self)
            self.setLayout(main_layout)
        else:
            main_layout = existing_layout

        # Controls (built in code)
        # Search input: bigger width as requested
        self.searchInput = QLineEdit(self)
        self.searchInput.setPlaceholderText("جستجو... (نام یا قیمت)")
        self.searchInput.setMaximumWidth(760)
        self.searchInput.setMinimumWidth(420)
        self.searchInput.setClearButtonEnabled(True)

        # Buttons
        self.addButton = QPushButton("افزودن", self)
        self.editButton = QPushButton("ویرایش انتخاب‌شده", self)
        self.deleteButton = QPushButton("حذف انتخاب‌شده", self)
        self.editButton.setEnabled(False)
        self.deleteButton.setEnabled(False)

        # --- ساخت container برای جدول‌ها (تا به بالا بچسبند و کنترل ارتفاع داشته باشیم) ---
        tables_container = QWidget(self)
        tables_container_layout = QHBoxLayout(tables_container)
        tables_container_layout.setSpacing(12)
        tables_container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(tables_container , 1)




        # Create tables for each section
        self.section_tables = {}
        self.sections = get_all_sections()  # list of (key, display_name)
        for key, display_name in self.sections:
            table = QTableWidget(self)
            table.setObjectName(f"{key}Table")
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["قیمت", "نام"])
            table.verticalHeader().setVisible(False)

            # header styling: make it a bit more colorful and readable
            table.setStyleSheet(
                "QHeaderView::section {background-color: #111;color: #00eaff ;padding: 4px; border: 1px solid #00eaff; }"
                "QTableWidget { gridline-color: #0f2a2d; }"
            )

            header = table.horizontalHeader()
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # نام کشیده شود
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)    # قیمت ثابت کنیم
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # selection behavior
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

            # connect click to selection handler
            table.cellClicked.connect(lambda r, c, sk=key: self.on_table_row_clicked(sk, r))
            # column layout: label (styled) + table
            col_layout = QVBoxLayout()
            label = QLabel(display_name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            label.setStyleSheet(
                "QLabel { background-color: #003b45; font-weight: 600; padding:6px 8px; border-radius:6px; }"
            )
            col_layout.addWidget(label)
            col_layout.addWidget(table)

            # سپس هنگام ساخت هر col_layout به جای tables_layout.addLayout(col_layout) بنویس:
            tables_container_layout.addLayout(col_layout)
            tables_container_layout.setStretchFactor(col_layout , 1)
            # --- پایان بسته‌بندی ---

            self.section_tables[key] = table

        # sensible minimum width so tables have room
        self.setMinimumWidth(1100)

        bottom_widget = QWidget(self)
        bottom_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(8, 6, 8, 6)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.searchInput)
        bottom_layout.addSpacing(12)
        bottom_layout.addWidget(self.addButton)
        bottom_layout.addSpacing(8)
        bottom_layout.addWidget(self.editButton)
        bottom_layout.addSpacing(8)
        bottom_layout.addWidget(self.deleteButton)
        bottom_layout.addStretch(1)

        main_layout.addWidget(bottom_widget , 0)

        # selection state
        self.selected_section = None
        self.selected_snack_id = None

        # connect signals
        self.addButton.clicked.connect(self.on_add_clicked)
        self.editButton.clicked.connect(self.on_edit_selected)
        self.deleteButton.clicked.connect(self.on_delete_selected)
        self.searchInput.textChanged.connect(self.search_snacks)

        # initial load
        self.load_all_sections()

    # ---------- helpers ----------
    def format_price(self, price):
        try:
            return f"{int(price):,}"
        except Exception:
            try:
                return f"{int(float(price)):,}"
            except Exception:
                return str(price or 0)

    def update_table_heights_based_on_controls(self):
        try:
            ref_h = max(self.addButton.sizeHint().height(), self.searchInput.sizeHint().height())
        except Exception:
            ref_h = 40
        row_height = int(ref_h * 1.05)

        for key, table in self.section_tables.items():
            table.verticalHeader().setDefaultSectionSize(row_height)

            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # اطمینان از اینکه اسکرول عمودی فعال است وقتی ردیف‌ها بیشتر شدند
            table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    # ---------- loading ----------
    def load_all_sections(self):
        for section_key, _ in self.sections:
            self.load_section_table(section_key)

    def load_section_table(self, section_key: str):
        table = self.section_tables.get(section_key)
        if table is None:
            return

        snacks = get_snacks_by_section(section_key)
        table.clearContents()
        table.setRowCount(len(snacks))

        for row, snack in enumerate(snacks):
            snack_id, name, price = snack

            # name (store id in UserRole)
            name_item = QTableWidgetItem(name or "")
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            name_item.setData(Qt.ItemDataRole.UserRole, snack_id)
            table.setItem(row, 1, name_item)
            # price
            try:
                price_int = int(price)
            except Exception:
                try:
                    price_int = int(float(price))
                except Exception:
                    price_int = 0
            price_item = QTableWidgetItem(self.format_price(price_int))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, price_item)

        # set price column wider so numbers fit
        table.setColumnWidth(0, 300)   # قیمت
        # name column is stretch

        # update heights so tables don't move
        self.update_table_heights_based_on_controls()

    # ---------- selection ----------
    def on_table_row_clicked(self, section_key: str, row: int):
        table = self.section_tables.get(section_key)
        if table is None:
            return

        name_item = table.item(row, 1)
        if name_item is None:
            self.selected_snack_id = None
            self.selected_section = None
            self.editButton.setEnabled(False)
            self.deleteButton.setEnabled(False)
            return

        snack_id = name_item.data(Qt.ItemDataRole.UserRole)
        self.selected_snack_id = snack_id
        self.selected_section = section_key

        self.editButton.setEnabled(True)
        self.deleteButton.setEnabled(True)

    # ---------- add / edit / delete ----------
    def _choose_section_for_add(self):
        names = [name for key, name in self.sections]
        # show a simple selection dialog
        idx, ok = QInputDialog.getItem(self, "انتخاب بخش", "کدام بخش؟", names, 0, False)
        if not ok:
            return None
        # find corresponding key
        for key, name in self.sections:
            if name == idx:
                return key
        return None

    def on_add_clicked(self):
        # ask which section to add into
        section_key = self._choose_section_for_add()
        if section_key is None:
            return

        name, ok1 = QInputDialog.getText(self, "افزودن آیتم", "نام را وارد کنید:")
        if not ok1 or name.strip() == "":
            return
        name = name.strip()

        if snack_name_exists(section_key, name):
            QMessageBox.warning(self, "خطا", "این آیتم قبلاً در این بخش ثبت شده است")
            return

        price_str, ok2 = QInputDialog.getText(self, "افزودن آیتم", "قیمت را وارد کنید:", text="0")
        if not ok2:
            return
        try:
            price = int(price_str.replace(",", "").strip())
        except Exception:
            QMessageBox.warning(self, "خطا", "قیمت معتبر وارد کنید")
            return

        try:
            add_snack(section_key, name, price)
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"خطا در ذخیره: {e}")
            return

        # refresh only the affected table
        self.load_section_table(section_key)

    def on_edit_selected(self):
        if not getattr(self, "selected_snack_id", None):
            return
        sid = self.selected_snack_id
        sk = self.selected_section

        snacks = get_snacks_by_section(sk)
        snack = next((s for s in snacks if s[0] == sid), None)
        if snack is None:
            QMessageBox.warning(self, "خطا", "آیتم پیدا نشد")
            return

        current_name, current_price = snack[1], snack[2]

        new_name, ok1 = QInputDialog.getText(self, "ویرایش نام", "نام جدید را وارد کنید:", text=current_name)
        if not ok1:
            return
        price_str, ok2 = QInputDialog.getText(self, "ویرایش قیمت", "قیمت جدید را وارد کنید:", text=self.format_price(current_price))
        if not ok2:
            return
        try:
            new_price = int(price_str.replace(",", "").strip())
        except Exception:
            QMessageBox.warning(self, "خطا", "قیمت معتبر وارد کنید")
            return

        try:
            update_snack(sid, new_name, new_price)
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"خطا در به‌روزرسانی: {e}")
            return

        # refresh and restore selection
        self.load_section_table(sk)
        self._restore_selection_after_reload(sk, sid)

    def on_delete_selected(self):
        if not getattr(self, "selected_snack_id", None):
            return
        sid = self.selected_snack_id
        sk = self.selected_section

        reply = QMessageBox.question(self, "تایید حذف", "آیا از حذف آیتم مطمئن هستید؟")
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_snack(sid)
            except Exception as e:
                QMessageBox.warning(self, "خطا", f"خطا در حذف: {e}")
                return
            self.load_section_table(sk)
            self.selected_snack_id = None
            self.selected_section = None
            self.editButton.setEnabled(False)
            self.deleteButton.setEnabled(False)

    def _restore_selection_after_reload(self, section_key: str, snack_id: int):
        table = self.section_tables.get(section_key)
        if table is None:
            return
        for row in range(table.rowCount()):
            item = table.item(row, 1)
            if item and item.data(Qt.ItemDataRole.UserRole) == snack_id:
                table.selectRow(row)
                self.selected_snack_id = snack_id
                self.selected_section = section_key
                self.editButton.setEnabled(True)
                self.deleteButton.setEnabled(True)
                break

    # ---------- search ----------
    def search_snacks(self):
        text = self.searchInput.text().strip()
        for section_key, table in self.section_tables.items():
            for row in range(table.rowCount()):
                name_item = table.item(row, 1)
                price_item = table.item(row, 0)
                name = name_item.text() if name_item else ""
                price = price_item.text() if price_item else ""
                if text == "" or text in name or text in price:
                    table.setRowHidden(row, False)
                else:
                    table.setRowHidden(row, True)

    # ---------- resize handling ----------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            self.update_table_heights_based_on_controls()
        except Exception:
            pass
