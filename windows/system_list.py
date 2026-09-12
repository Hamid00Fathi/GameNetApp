from PyQt6 import uic
from PyQt6.QtWidgets import QWidget , QTableWidgetItem , QPushButton , QHBoxLayout , QInputDialog , QMessageBox
from system_repository import get_all_systems , get_system_by_id , update_system , add_system , system_name_exists , remove_system
from PyQt6.QtCore import Qt
import re

class System_List(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/system_list.ui" , self)

        self.addButton.clicked.connect(self.add_systems)

        self.load_systems()

    def format_price(self ,price):
        return f"{price:,}"

    def add_systems(self):
        name , ok1 = QInputDialog.getText(self , "افزودن سیستم" , "نام سیستم را وارد کنید:")
        if not ok1 or name.split() == "":
            return

        if system_name_exists(name):
            QMessageBox.warning(self, "خطا!" , "این سیستم قبلا ذخیره شده است")
            return

        

        price_str , ok2 = QInputDialog.getText(self , "افزودن سیستم" , "قیمت هر ساعت را وارد کنید" , text= "0")

        if not ok2:
            return

        price = int(price_str.replace("," , ""))

        add_system(name , price)

        self.load_systems()

    def load_systems(self):
        systems = get_all_systems()
        systems.sort(key=lambda s: (re.sub(r'\d+', '', s[1]).strip().lower(), int(re.findall(r'\d+', s[1])[0])))

        self.systemTable.setRowCount(len(systems))
        self.systemTable.setColumnCount(4)
        self.systemTable.setHorizontalHeaderLabels(["حذف" , "ویرایش" , "قیمت هر ساعت" , "نام سیستم"])

        for row , system in enumerate(systems):
            system_id = system[0]
            name = system[1]
            price = system[2]


            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row , 3 , name_item)
            self.systemTable.setColumnWidth(3 , 283)

            price_item = QTableWidgetItem(self.format_price(price))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.systemTable.setItem(row , 2 , price_item)
            self.systemTable.setColumnWidth(2 , 283)

            delete_btn = QPushButton("حذف")
            delete_btn.clicked.connect(lambda _, sid = system_id: self.delete_system(sid))
            self.systemTable.setColumnWidth(0 , 80)

            delete_layout = QHBoxLayout()
            delete_layout.addWidget(delete_btn)
            delete_layout.setContentsMargins(0 ,0 ,0 ,0)

            delete_widget = QWidget()
            delete_widget.setLayout(delete_layout)
            self.systemTable.setCellWidget(row , 0 , delete_widget)

            edit_btn = QPushButton("ویرایش")
            edit_btn.clicked.connect(lambda _ , sid = system_id: self.edit_system(sid))
            self.systemTable.setColumnWidth(1, 80)

            edit_layout = QHBoxLayout()
            edit_layout.addWidget(edit_btn)
            edit_layout.setContentsMargins(0 ,0 ,0 ,0)

            edit_widget = QWidget()
            edit_widget.setLayout(edit_layout)
            self.systemTable.setCellWidget(row , 1 , edit_widget)


    def delete_system(self , system_id):
        reply = QMessageBox.question(self ,
            "تایید حذف" ,
            "آیا از حذف سیستم مطمن هستید؟!")

        if reply == QMessageBox.StandardButton.Yes:
            remove_system(system_id)
            self.load_systems()

        
        
        
    def edit_system(self, system_id):
        system = get_system_by_id(system_id)

        if system is None:
            return

        name = system[1]
        price_value = system[2]
   
        new_name, ok1 = QInputDialog.getText(
            self,
            "ویرایش نام",
            "نام جدی را وارد کنید:",
            text=name
        )
        if not ok1:
            return

        if new_name != name and system_name_exists(new_name):
            QMessageBox.warning(self , "خطا!" , "این نام سیستم قبلا ثبت شده است")
            return

        price_str , ok2 = QInputDialog.getText(
            self,
            "ویرایش قیمت",
            "قیمت هر ساعت را وارد کنید:",
            text=self.format_price(price_value)
        )
        if not ok2:
            return

        new_price = int(price_str.replace("," , ""))

        update_system(system_id, new_name, new_price)
        self.load_systems()