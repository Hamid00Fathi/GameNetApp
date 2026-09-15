from PyQt6 import uic
from PyQt6.QtWidgets import QWidget , QMessageBox
from snack_repository import add_snack , snack_name_exists
from PyQt6.QtCore import pyqtSignal


class NewSnackWindow(QWidget):
    snack_added = pyqtSignal()
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/new_snack.ui" , self)

        
        self.saveBtn.clicked.connect(self.save_snack)

    def save_snack(self):
        name = self.nameInput.text().strip()
        price  = self.priceInput.value()

        if name == "":
            QMessageBox.warning(self , "خطا" , "نام خوراکی نمیتواند خالی باشد")
            return
        if price <= 0:
            QMessageBox.warning(self , "خطا" , "قیمت باید بیشتر از صفر باشد")
            return

        if snack_name_exists(name):
            QMessageBox.warning(self , "خطا" , "این نام خوراکی قبلا ذخیره شده")
            return

        add_snack(name , price)

        self.snack_added.emit()

        QMessageBox.information(self, "موفقیت" , "خوراکی با موفقیت اضافه شد")
        self.close()
        