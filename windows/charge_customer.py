from PyQt6.QtWidgets import QWidget, QMessageBox, QLineEdit
from customer_repository import get_customers, charge_customer
from PyQt6.QtCore import Qt


class ChargeCustomerWindow(QWidget):
    def __init__(self):
        super().__init__()
        from windows.ui_builder import build_ui
        build_ui(self, 'charge_customer')

        # Search is inserted into the existing layout, so the rest of the
        # user's customized charge screen remains unchanged.
        self.searchInput = QLineEdit(self)
        self.searchInput.setObjectName("chargeCustomerSearch")
        self.searchInput.setPlaceholderText("جستجوی مشتری با نام، نام خانوادگی یا کد...")
        layout = self.layout()
        if layout is not None:
            layout.insertWidget(0, self.searchInput)

        self._all_customers = []
        self.load_customers()
        self.searchInput.textChanged.connect(self.filter_customers)
        self.chargeButton.clicked.connect(self.do_charge)

    def load_customers(self):
        self._all_customers = list(get_customers() or [])
        self.filter_customers(self.searchInput.text() if hasattr(self, "searchInput") else "")

    def filter_customers(self, text=""):
        """Filter the customer combo without changing customer IDs or balances."""
        query = str(text or "").strip().casefold()
        combo = self.customerCombo
        previous_id = combo.currentData()
        combo.blockSignals(True)
        combo.clear()

        for customer in self._all_customers:
            customer_id, name, family, code, balance = customer
            name = str(name or "")
            family = str(family or "")
            code = str(code or "")
            searchable = f"{name} {family} {code}".casefold()
            if query and query not in searchable:
                continue

            balance_value = int(balance or 0)
            balance_text = f"بدهکار {abs(balance_value):,}" if balance_value < 0 else f"{balance_value:,}"
            display = f"{code} - {name} {family} (موجودی: {balance_text})"
            combo.addItem(display, customer_id)

        # Keep the previous choice if it remains among the filtered results.
        if previous_id is not None:
            idx = combo.findData(previous_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

        has_results = combo.count() > 0
        self.chargeButton.setEnabled(has_results)
        if not has_results:
            combo.setToolTip("مشتری‌ای با این عبارت پیدا نشد.")
        else:
            combo.setToolTip("مشتری موردنظر را انتخاب کنید.")

    def do_charge(self):
        customer_id = self.customerCombo.currentData()
        if customer_id is None:
            QMessageBox.warning(self, "مشتری پیدا نشد", "ابتدا مشتری موردنظر را جست‌وجو و انتخاب کنید.")
            return

        amount = self.amountSpin.value()
        if self.radioReduce.isChecked():
            amount = -amount
        if amount == 0:
            QMessageBox.warning(self, "خطا", "مقدار شارژ نمی‌تواند صفر باشد")
            return

        try:
            charge_customer(customer_id, amount)
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"ثبت تراکنش انجام نشد:\\n{exc}")
            return

        QMessageBox.information(self, "موفقیت", "حساب مشتری با موفقیت شارژ شد")
        self.close()
