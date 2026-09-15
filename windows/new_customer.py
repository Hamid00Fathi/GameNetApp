from PyQt6 import uic
from PyQt6.QtWidgets import QWidget , QMessageBox
from customer_repository import add_customer

class NewCustomerWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/new_customer.ui" , self)
        self.submit_btn.clicked.connect(self.save_customer)
        self.balanceCheckBox.stateChanged.connect(self.toggle_balance)

    def save_customer(self):
        name = self.name_input.text()
        family = self.family_input.text()
        code = self.code_input.text()

        if not name or not family or not code:
            QMessageBox.warning(self, "خطا" , "لطفا فیلد های ضروری را پر کنید")
            return

        if self.balanceCheckBox.isChecked():
            balance = self.balanceSpinBox.value()
        else:
            balance = 0

        add_customer(name , family , code , balance)

        QMessageBox.information(self , "موفقیت" , "مشتری با موفقیا ثبت شد")

        self.close()

    def toggle_balance(self , state):
        self.balanceSpinBox.setEnabled(state == 2)


