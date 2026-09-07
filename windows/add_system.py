from PyQt6 import uic
from PyQt6.QtWidgets import QWidget , QMessageBox
from system_repository import add_system , system_name_exists


class AddSystemWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/add_system.ui" , self)

        self.addButton.clicked.connect(self.save_system)

    def save_system(self):
        try:
            name = self.systemNameLineEdit.text().strip()

            if name == "":
                QMessageBox.warning(self, "خطا", "لطفا نام سیستم را وارد کنید")
                return

            if system_name_exists(name):
                QMessageBox.warning(self, "خطا!", "این نام سیستم قبلا ثبت شده است")
                return

            # گرفتن قیمت از اسپین‌باکس
            price_per_hour = self.priceSpinBox.value()

            add_system(name, price_per_hour)

            QMessageBox.information(self, "موفق", "سیستم با موفقیت اضافه شد")
            self.close()

        except Exception as e:
            self.statusLabel.setText(f"خطا: {e}")