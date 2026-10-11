"""Native PyQt6 layouts for GameNet. No Qt Designer .ui files are used."""
from PyQt6.QtWidgets import (QWidget,QMainWindow,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QLabel,QPushButton,QLineEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QRadioButton,QComboBox,QTableWidget,QTableWidgetItem,QStatusBar,QMenuBar,QMenu,QGroupBox,QTextEdit,QDialogButtonBox,QListWidget,QHeaderView)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

STYLE = '''
QWidget{font-family:'Segoe UI','Tahoma';font-size:11pt;color:#e8edf7;background:#0b1120}
QLabel{background:transparent;color:#dce5f5}
QPushButton{background:#18243a;border:1px solid #2a3b59;border-radius:9px;padding:10px 14px;min-height:24px;font-weight:600;font-size:11pt}
QPushButton:hover{background:#223653;border-color:#4e8cff} QPushButton:pressed{background:#10203a}
QPushButton:disabled{color:#64748b;background:#121b2b;border-color:#202d42}
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit{background:#111b2d;border:1px solid #293b58;border-radius:8px;padding:9px;selection-background-color:#3478f6;min-height:20px}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus,QTextEdit:focus{border:1px solid #5b9aff}
QTableWidget{background:#0f1929;alternate-background-color:#121f32;gridline-color:#202e44;border:1px solid #24334b;border-radius:12px;padding:5px;selection-background-color:#234d88;selection-color:white}
QTableWidget::item{padding:7px;border-bottom:1px solid #1d2a3d}
QHeaderView::section{background:#17253b;color:#bcd5ff;border:0;border-bottom:2px solid #3978ed;padding:13px 7px;font-weight:700;font-size:11pt}
QScrollBar:vertical{background:#101a2a;width:11px;margin:2px} QScrollBar::handle:vertical{background:#344966;border-radius:5px;min-height:30px} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
QStatusBar{background:#0b1120;color:#9aaac2;border-top:1px solid #202e44} QCheckBox,QRadioButton{background:transparent;spacing:8px}
'''

def action(menu, name, title):
    a=QAction(title, menu); a.setObjectName(name); menu.addAction(a); return a

def table(cols, headers):
    t=QTableWidget(0,cols); t.setHorizontalHeaderLabels(headers); t.setAlternatingRowColors(True); t.setShowGrid(False); t.verticalHeader().setVisible(False); t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); t.setSortingEnabled(False); t.horizontalHeader().setMinimumSectionSize(44); t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); t.verticalHeader().setDefaultSectionSize(58); t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); return t

def build_ui(w, kind):
    w.setStyleSheet(STYLE)
    if kind=='main':
        w.setWindowTitle('GameNet Manager | مدیریت گیم‌نت'); w.resize(1600,950); w.setMinimumSize(1100,700)
        root=QWidget(); w.setCentralWidget(root); lay=QVBoxLayout(root); lay.setContentsMargins(14,10,14,8); lay.setSpacing(8)
        head=QHBoxLayout(); header_buttons={}; brand=QVBoxLayout(); title=QLabel('GAMENET MANAGER'); title.setStyleSheet('font-size:22px;font-weight:900;letter-spacing:2px;color:#f5f8ff'); sub=QLabel('کنسول مدیریت مجموعه'); sub.setStyleSheet('color:#8295b4;font-size:10pt'); brand.addWidget(title);brand.addWidget(sub);head.addLayout(brand);head.addStretch()
        for text,name in [('＋ افزودن سیستم','btnAddSystem'),('＋ افزودن مشتری','btnAddCustomer'),('شارژ حساب','btnChargeCustomer')]:
            b=QPushButton(text); b.setObjectName(name); b.setMinimumHeight(38); b.setStyleSheet('QPushButton{background:#2864e8;border:1px solid #4380ff;border-radius:10px;padding:10px 15px} QPushButton:hover{background:#3977f4}');head.addWidget(b);header_buttons[name]=b
        lay.addLayout(head)
        metrics=QHBoxLayout(); metrics.setSpacing(8)
        for caption, key in [('درآمد امروز','revenue'),('جلسات فعال','sessions'),('مشتریان','customers')]:
            card=QFrameCompat(); card.setStyleSheet('QWidget{background:#111d30;border:1px solid #22334c;border-radius:13px}'); cl=QVBoxLayout(card);cl.setContentsMargins(12,7,12,7);lab=QLabel(caption);lab.setStyleSheet('color:#92a6c4;border:0;font-size:10pt');val=QLabel('در حال بارگذاری…');val.setObjectName('metric_'+key);val.setStyleSheet('color:#f5f8ff;border:0;font-size:23px;font-weight:800');cl.addWidget(lab);cl.addWidget(val);metrics.addWidget(card)
        lay.addLayout(metrics)
        bar=QHBoxLayout(); lbl=QLabel('سیستم‌ها و نشست‌های جاری');lbl.setStyleSheet('font-size:16px;font-weight:800;color:#f1f5ff');bar.addWidget(lbl);bar.addStretch();hint=QLabel('مدیریت لحظه‌ای سیستم‌ها');hint.setStyleSheet('color:#7e91ad');bar.addWidget(hint);lay.addLayout(bar)
        w.systemTable=table(12,['تسویه','مشتری','هزینه','مدت','خوراکی','تغییر مشتری','توقف','شروع','وضعیت','سیستم','یادداشت','تعرفه / دسته‌ها'])
        w.systemTable.setObjectName('systemTable'); w.systemTable.horizontalHeader().setMinimumSectionSize(44); w.systemTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); w.systemTable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); w.systemTable.setMinimumHeight(420); lay.addWidget(w.systemTable,5)
        w.statusbar=QStatusBar();w.setStatusBar(w.statusbar)
        menubar=QMenuBar(w);w.setMenuBar(menubar)
        actions = {}
        for title, items in [('عملیات',[('btnAddSystem','افزودن سیستم'),('btnAddCustomer','افزودن مشتری'),('btnChargeCustomer','شارژ مشتری')]),('فهرست‌ها',[('btnSystemList','فهرست سیستم‌ها'),('btnCustomerList','فهرست مشتریان'),('btnSnackList','مدیریت خوراکی‌ها')]),('حساب',[('btnUsername','حساب کاربری'),('actionRenewSubscription','تمدید اشتراک'),('actionOnlineLogin','ورود آنلاین'),('actionOfflineLogin','حالت آفلاین'),('actionLogout','خروج')])]:
            m=QMenu(title,w);menubar.addMenu(m)
            for n,t in items:
                actions[n] = action(m,n,t)
        w.actionOnlineLogin=actions['actionOnlineLogin'];w.actionOfflineLogin=actions['actionOfflineLogin'];w.actionRenewSubscription=actions['actionRenewSubscription'];w.actionLogout=actions['actionLogout']
        for n in ['btnAddSystem','btnAddCustomer','btnChargeCustomer','btnCustomerList','btnSnackList','btnSystemList','btnUsername']:
            act=actions[n]
            if n in header_buttons:
                header_buttons[n].clicked.connect(act.trigger)
            setattr(w,n,act)
    elif kind=='system_list':
        w.setWindowTitle('مدیریت سیستم‌ها');w.resize(1000,680);lay=QVBoxLayout(w);lay.setContentsMargins(22,22,22,20);lay.setSpacing(14)
        title=QLabel('مدیریت سیستم‌ها');title.setStyleSheet('font-size:22px;font-weight:800');lay.addWidget(title)
        sub=QLabel('تعریف سیستم‌ها و تنظیم مدل تعرفه‌گذاری');sub.setStyleSheet('color:#8ea2c0');lay.addWidget(sub)
        top=QHBoxLayout();w.modeCombo=QComboBox();w.modeCombo.addItems(['تک تعرفه ای','چند تعرفه ای']);top.addWidget(w.modeCombo);top.addWidget(QLabel('مدل تعرفه'));top.addStretch();lay.addLayout(top)
        w.systemTable=table(2,['قیمت / مدیریت تعرفه','نام سیستم']); w.systemTable.horizontalHeader().setMinimumSectionSize(180); w.systemTable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); lay.addWidget(w.systemTable,1)
        buttons=QHBoxLayout();w.addButton=QPushButton('＋ افزودن سیستم');w.editButton=QPushButton('ویرایش');w.deleteButton=QPushButton('حذف');w.editButton.setEnabled(False);w.deleteButton.setEnabled(False)
        for b in (w.addButton,w.editButton,w.deleteButton):buttons.addWidget(b)
        buttons.addStretch();lay.addLayout(buttons)
    elif kind=='customer_list':
        w.setWindowTitle('فهرست مشتریان');w.resize(1000,650);lay=QVBoxLayout(w);lay.setContentsMargins(22,22,22,20);lay.addWidget(QLabel('مشتریان'));w.searchInput=QLineEdit();w.searchInput.setPlaceholderText('جستجو بر اساس نام، کد یا شماره…');lay.addWidget(w.searchInput);w.customerTable=table(5,['شارژ','کد','فامیل','نام','ID']);lay.addWidget(w.customerTable,1);row=QHBoxLayout();w.editBtn=QPushButton('ویرایش مشتری');w.deleteBtn=QPushButton('حذف مشتری');row.addWidget(w.editBtn);row.addWidget(w.deleteBtn);row.addStretch();lay.addLayout(row)
    elif kind=='add_system':
        w.setWindowTitle('افزودن سیستم');lay=QVBoxLayout(w);lay.setContentsMargins(24,24,24,24);lay.addWidget(QLabel('افزودن سیستم جدید'));form=QFormLayout();w.systemNameLineEdit=QLineEdit();w.systemNameLineEdit.setPlaceholderText('مثلاً PS5 - شماره ۱');w.priceSpinBox=QSpinBox();w.priceSpinBox.setMaximum(999999999);w.priceSpinBox.setSuffix(' تومان / ساعت');w.priceSpinBox.setSingleStep(5000);form.addRow('نام سیستم',w.systemNameLineEdit);form.addRow('تعرفه پایه',w.priceSpinBox);lay.addLayout(form);w.addButton=QPushButton('ثبت سیستم');lay.addWidget(w.addButton)
    elif kind=='new_customer':
        w.setWindowTitle('مشتری جدید');lay=QVBoxLayout(w);lay.setContentsMargins(24,24,24,24);lay.addWidget(QLabel('ثبت مشتری جدید'));form=QFormLayout();w.name_input=QLineEdit();w.family_input=QLineEdit();w.code_input=QLineEdit();w.balanceSpinBox=QSpinBox();w.balanceSpinBox.setMaximum(999999999);w.balanceSpinBox.setSuffix(' تومان');w.balanceSpinBox.setSingleStep(5000);w.balanceCheckBox=QCheckBox('ثبت موجودی اولیه');form.addRow('نام',w.name_input);form.addRow('نام خانوادگی',w.family_input);form.addRow('کد مشتری',w.code_input);form.addRow(w.balanceCheckBox,w.balanceSpinBox);lay.addLayout(form);w.submit_btn=QPushButton('ثبت مشتری');lay.addWidget(w.submit_btn)
    elif kind=='charge_customer':
        w.setWindowTitle('شارژ حساب مشتری');lay=QVBoxLayout(w);lay.setContentsMargins(24,24,24,24);form=QFormLayout();w.customerCombo=QComboBox();w.amountSpin=QSpinBox();w.amountSpin.setMaximum(999999999);w.amountSpin.setSuffix(' تومان');w.amountSpin.setSingleStep(5000);form.addRow('مشتری',w.customerCombo);form.addRow('مبلغ',w.amountSpin);lay.addLayout(form);row=QHBoxLayout();w.radioAdd=QRadioButton('افزایش اعتبار');w.radioReduce=QRadioButton('کاهش اعتبار');w.radioAdd.setChecked(True);row.addWidget(w.radioAdd);row.addWidget(w.radioReduce);lay.addLayout(row);w.chargeButton=QPushButton('ثبت تراکنش');lay.addWidget(w.chargeButton)
    elif kind=='select_username':
        w.setWindowTitle('ورود به GameNet');lay=QVBoxLayout(w);lay.setContentsMargins(26,26,26,26);lay.addWidget(QLabel('ورود به حساب کاربری'));form=QFormLayout();w.txtUsername=QLineEdit();w.txtPassword=QLineEdit();w.txtPassword.setEchoMode(QLineEdit.EchoMode.Password);form.addRow('نام کاربری',w.txtUsername);form.addRow('رمز عبور',w.txtPassword);lay.addLayout(form);w.linkBtn=QPushButton('ادامه');lay.addWidget(w.linkBtn)
    elif kind=='new_snack':
        w.setWindowTitle('خوراکی جدید');lay=QVBoxLayout(w);lay.setContentsMargins(24,24,24,24);form=QFormLayout();
        w.nameInput=QLineEdit();w.priceInput=QSpinBox();w.priceInput.setMaximum(999999999);w.priceInput.setSuffix(' تومان');form.addRow('نام خوراکی',w.nameInput);form.addRow('قیمت',w.priceInput);lay.addLayout(form);w.saveBtn=QPushButton('ذخیره خوراکی');lay.addWidget(w.saveBtn)
    elif kind=='snack_list':
        w.setWindowTitle('مدیریت خوراکی‌ها');w.resize(1000,620);lay=QVBoxLayout(w);lay.setContentsMargins(20,20,20,20);w.searchInput=QLineEdit();w.searchInput.setPlaceholderText('جستجوی خوراکی…');lay.addWidget(w.searchInput);w.snackTable=table(4,['دسته','موجودی','قیمت','نام خوراکی']);lay.addWidget(w.snackTable,1);row=QHBoxLayout();w.addButton=QPushButton('افزودن');w.editButton=QPushButton('ویرایش');w.deleteButton=QPushButton('حذف');[row.addWidget(b) for b in (w.addButton,w.editButton,w.deleteButton)];lay.addLayout(row)


class QFrameCompat(QWidget): pass
