from PyQt6 import uic
from PyQt6.QtWidgets import QWidget , QMessageBox , QCompleter
from customer_repository import get_customers , charge_customer
from PyQt6.QtCore import Qt


class ChargeCustomerWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/charge_customer.ui" , self)

        self.load_customers()
        self.chargeButton.clicked.connect(self.do_charge)

    def load_customers(self):
        customers = get_customers()

        names = []
        for c in customers:
            id_ , name , family , code , balance = c
            if balance < 0:
                format_balance = f"بدهکار {abs(balance):,}"
            else:
                format_balance = f"{balance:,}"
            text = f"{code} - {name} {family} (موجودی: {format_balance})"
            self.customerCombo.addItem(text , id_)

            names.append(text)

        completer = QCompleter(names)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.customerCombo.setCompleter(completer)

    def do_charge(self):
        customer_id = self.customerCombo.currentData()
        amount = self.amountSpin.value()

        if self.radioReduce.isChecked():
            amount = -amount
        if amount == 0:
            QMessageBox.warning(self, "خطا" , "مقدار شارژ نمیتواند صفر باشد")
            return

        charge_customer(customer_id , amount)

        QMessageBox.information(self , "موفقیت" , "حساب مشتری با موفقیت شارژ شد")
        self.close()




