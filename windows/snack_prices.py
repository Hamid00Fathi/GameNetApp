from PyQt6 import uic
from PyQt6.QtWidgets import QWidget

class SnackPriceWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/snack_prices.ui" , self)