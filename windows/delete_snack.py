from PyQt6 import uic
from PyQt6.QtWidgets import QWidget , QMessageBox , QCompleter
from snack_repository import delete_snack , get_snacks
from PyQt6.QtCore import pyqtSignal , Qt

class DeleteSnackWindow(QWidget):
    snack_deleted = pyqtSignal()

    def __init__(self):
        super().__init__()
        uic.loadUi("ui/delete_snack.ui" , self)


        self.load_snacks()
        self.deleteBtn.clicked.connect(self.delete_selected)

    def load_snacks(self):
        snacks = get_snacks()
        self.comboSnacks.clear()

        names = []


        for snack_id , name , price in snacks:
            self.comboSnacks.addItem(name , snack_id)
            names.append(name)

        completer = QCompleter(names)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.comboSnacks.setEditable(True)
        self.comboSnacks.setCompleter(completer)

    def delete_selected(self):
        snack_id = self.comboSnacks.currentData()

        if snack_id is None:
            QMessageBox.warning(self , "خطا" , "خوراکی معتبر انتخاب نشده")

        delete_snack(snack_id)
        self.snack_deleted.emit()

        QMessageBox.information(self , "موفقیت" , "خوراکی حذف شد")
        self.close()