from PyQt6 import uic
from PyQt6.QtWidgets import QWidget

class PricePerMinuteWindow(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi("ui/price_per_hour.ui" , self)