from PyQt6 import uic
from PyQt6.QtWidgets import QWidget

class RemoveSystemWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/remove_system.ui" , self)

        