def apply_dark_theme():
    return """
    QWidget {
        background-color: #0d0d0d;
        color: #cfcfcf;
        font-size: 14px;
    }

    QPushButton {
        background-color: #111;
        border: 1px solid #00eaff;
        padding: 6px;
        color: #00eaff;
        border-radius: 4px;
        font-size: 15px;
    }

    QPushButton:hover {
        background-color: #003b45;
        border: 1px solid #00ffff;
        color: #00ffff;
    }

    QLineEdit, QTextEdit, QPlainTextEdit {
        background-color: #1a1a1a;
        border: 1px solid #00eaff;
        color: #00eaff;
        padding: 4px;
        font-size: 15px;
    }

    QComboBox {
        background-color: #1a1a1a;
        border: 1px solid #00eaff;
        color: #00eaff;
    }

    QTableWidget {
        background-color: #1a1a1a;
        gridline-color: #00eaff;
        color: #cfcfcf;
        font-size: 17px;
    }

    QHeaderView::section {
        background-color: #111;
        color: #00eaff;
        padding: 4px;
        border: 1px solid #00eaff;
    }

    QMenuBar {
        background-color: #0d0d0d;
        color: #00eaff;
    }

    QMenuBar::item:selected {
        background-color: #003b45;
    }

    QMenu {
        background-color: #0d0d0d;
        color: #00eaff;
    }

    QMenu::item:selected {
        background-color: #003b45;
    }

    QStatusBar {
        background-color: #0d0d0d;
        color: #00eaff;
    }

    QLabel {
        font-size: 15px;
    }
    """