from PyQt6.QtWidgets import QApplication
from windows.main_window import MainWindow
from database import create_tables

create_tables()
app = QApplication([])

window = MainWindow()
window.show()


app.exec()



