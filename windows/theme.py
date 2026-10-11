"""Modern dark theme for GameNet.

This module intentionally contains presentation-only styling. It does not
change application workflows, database behavior, or tariff/session logic.
"""


def apply_dark_theme():
    return r"""
    * {
        font-family: "Segoe UI", "Tahoma", sans-serif;
        font-size: 10pt;
        outline: 0;
    }
    QWidget {
        background-color: #111827;
        color: #e5eaf3;
        selection-background-color: #2563eb;
        selection-color: #ffffff;
    }
    QMainWindow, QDialog {
        background-color: #0b1220;
    }
    QMainWindow::separator {
        background: #263348;
        width: 1px;
        height: 1px;
    }
    QLabel {
        background: transparent;
        color: #dbe4f0;
        padding: 2px;
    }
    QLabel:disabled { color: #64748b; }

    QPushButton, QToolButton {
        color: #f8fafc;
        background-color: #243247;
        border: 1px solid #34465f;
        border-radius: 8px;
        padding: 8px 14px;
        min-height: 18px;
    }
    QPushButton:hover, QToolButton:hover {
        background-color: #30445f;
        border-color: #4b6b92;
    }
    QPushButton:pressed, QToolButton:pressed {
        background-color: #1e293b;
        padding-top: 9px;
        padding-bottom: 7px;
    }
    QPushButton:disabled, QToolButton:disabled {
        color: #64748b;
        background-color: #182233;
        border-color: #263348;
    }
    QPushButton#btnAddSystem, QPushButton#btnAddCustomer,
    QPushButton#btnChargeCustomer {
        background-color: #2563eb;
        border: 1px solid #3b82f6;
        font-weight: 600;
    }
    QPushButton#btnAddSystem:hover, QPushButton#btnAddCustomer:hover,
    QPushButton#btnChargeCustomer:hover { background-color: #1d4ed8; }

    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox,
    QDateEdit, QTimeEdit, QDateTimeEdit, QComboBox {
        background-color: #0f1a2b;
        color: #f1f5f9;
        border: 1px solid #33445c;
        border-radius: 7px;
        padding: 7px 9px;
        selection-background-color: #2563eb;
        min-height: 18px;
    }
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
    QTimeEdit:focus, QDateTimeEdit:focus, QComboBox:focus {
        border: 1px solid #60a5fa;
        background-color: #111f34;
    }
    QLineEdit:disabled, QComboBox:disabled { color: #64748b; }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 25px;
        border-left: 1px solid #33445c;
        border-top-right-radius: 7px;
        border-bottom-right-radius: 7px;
    }
    QComboBox QAbstractItemView {
        background-color: #172338;
        color: #e5eaf3;
        border: 1px solid #3b4d67;
        selection-background-color: #2563eb;
        padding: 4px;
    }
    QCheckBox, QRadioButton { spacing: 8px; background: transparent; }
    QCheckBox::indicator, QRadioButton::indicator {
        width: 16px; height: 16px;
    }
    QCheckBox::indicator {
        border: 1px solid #52647e; border-radius: 4px; background: #0f1a2b;
    }
    QCheckBox::indicator:checked { background: #2563eb; border-color: #60a5fa; }
    QRadioButton::indicator { border: 1px solid #52647e; border-radius: 8px; background: #0f1a2b; }
    QRadioButton::indicator:checked { background: #3b82f6; border: 4px solid #0f1a2b; }

    QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget, QListView {
        background-color: #111c2e;
        alternate-background-color: #142137;
        color: #e2e8f0;
        gridline-color: #26364d;
        border: 1px solid #293950;
        border-radius: 10px;
        selection-background-color: #1d4ed8;
        selection-color: #ffffff;
        padding: 3px;
    }
    QTableWidget::item, QTableView::item, QListWidget::item {
        padding: 7px 5px;
        border-bottom: 1px solid #1e2b40;
    }
    QTableWidget::item:hover, QTableView::item:hover,
    QListWidget::item:hover { background-color: #1b2b43; }
    QHeaderView::section {
        background-color: #1c2a40;
        color: #bfdbfe;
        padding: 10px 7px;
        border: none;
        border-bottom: 2px solid #3b82f6;
        font-weight: 600;
    }
    QTableCornerButton::section { background-color: #1c2a40; border: none; }
    QTableWidget QLineEdit { border-radius: 4px; padding: 3px; }
    QScrollBar:vertical {
        background: #111c2e; width: 12px; margin: 3px; border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background: #3a4c65; min-height: 28px; border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover { background: #526b8c; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal {
        background: #111c2e; height: 12px; margin: 3px; border-radius: 6px;
    }
    QScrollBar::handle:horizontal { background: #3a4c65; min-width: 28px; border-radius: 5px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

    QMenuBar {
        background-color: #101a2a;
        color: #dbeafe;
        border-bottom: 1px solid #293950;
        padding: 4px;
    }
    QMenuBar::item { padding: 8px 12px; border-radius: 6px; background: transparent; }
    QMenuBar::item:selected { background-color: #243b5a; color: #ffffff; }
    QMenu {
        background-color: #172338;
        color: #e5eaf3;
        border: 1px solid #34465f;
        padding: 5px;
    }
    QMenu::item { padding: 8px 28px 8px 12px; border-radius: 5px; }
    QMenu::item:selected { background-color: #2563eb; color: #ffffff; }
    QStatusBar {
        background-color: #0e1726;
        color: #94a3b8;
        border-top: 1px solid #26364d;
    }
    QStatusBar::item { border: none; }
    QGroupBox {
        border: 1px solid #2c3d55;
        border-radius: 10px;
        margin-top: 14px;
        padding: 12px 9px 9px 9px;
        font-weight: 600;
        color: #bfdbfe;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top right;
        padding: 0 8px;
        right: 12px;
        background-color: #111827;
    }
    QTabWidget::pane { border: 1px solid #293950; border-radius: 8px; top: -1px; }
    QTabBar::tab {
        background: #172338; color: #94a3b8;
        padding: 9px 16px; margin-right: 3px;
        border-top-left-radius: 7px; border-top-right-radius: 7px;
    }
    QTabBar::tab:selected { background: #2563eb; color: white; }
    QProgressBar {
        border: 1px solid #33445c; border-radius: 6px;
        background: #0f1a2b; text-align: center; color: white;
    }
    QProgressBar::chunk { background: #3b82f6; border-radius: 5px; }
    QToolTip {
        color: #f8fafc; background-color: #172338;
        border: 1px solid #52647e; padding: 5px 8px; border-radius: 5px;
    }
    QMessageBox { background-color: #111827; }
    """
