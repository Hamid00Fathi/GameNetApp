from PyQt6 import uic
from PyQt6.QtWidgets import QWidget

class StartSystemWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/start_system.ui" , self)