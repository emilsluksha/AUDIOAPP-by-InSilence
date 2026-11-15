STYLE = '''
QWidget { background:#0D0A14; color:#F8F5FF; font-family:"Segoe UI"; font-size:13px; }
QMainWindow { background:#0D0A14; }
QFrame#sidebar { background:#171120; border-right:1px solid #2D2239; }
QFrame#sidebar QLabel { background:transparent; }
QLabel#brand { font-size:24px; font-weight:800; letter-spacing:3px; }
QLabel#heading { font-size:28px; font-weight:700; }
QLabel#hero { font-size:34px; font-weight:700; }
QLabel#muted { color:#A9A0BB; background:transparent; }
QLabel#metric { font-size:27px; font-weight:700; color:#F8F5FF; background:transparent; }
QLabel#dropTitle { font-size:22px; font-weight:600; background:transparent; }
QFrame#card { background:#21182E; border:1px solid #352741; border-radius:14px; }
QFrame#card QLabel { background:transparent; }
QFrame#dropzone { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #221731,stop:1 #191221); border:1px dashed #75529C; border-radius:18px; }
QFrame#dropzone QLabel {background:transparent;}
QComboBox,QDoubleSpinBox,QSpinBox,QLineEdit { background:#21182E; border:1px solid #443252; border-radius:7px; padding:7px; min-height:20px; }
QComboBox QAbstractItemView {background:#21182E;selection-background-color:#8B5CF6;}
QSlider::groove:horizontal {height:5px;background:#352741;border-radius:2px;}
QSlider::sub-page:horizontal {background:#8B5CF6;border-radius:2px;}
QSlider::handle:horizontal {background:#F472B6;width:14px;margin:-5px 0;border-radius:7px;}
QProgressBar {background:#21182E;border:0;border-radius:4px;text-align:center;min-height:8px;}
QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #8B5CF6,stop:1 #EC4899);border-radius:4px;}
QListWidget,QTableWidget {background:#171120;border:1px solid #352741;border-radius:10px;alternate-background-color:#21182E;}
QListWidget::item {padding:12px;}
QListWidget::item:selected {background:#44305D;}
QHeaderView::section {background:#21182E;color:#A9A0BB;border:0;padding:9px;}
QScrollArea {border:0;}
QScrollBar:vertical {background:#171120;width:8px;}
QScrollBar::handle:vertical {background:#443252;border-radius:4px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QToolTip {background:#21182E;border:1px solid #8B5CF6;color:#F8F5FF;padding:8px;}
QCheckBox {spacing:8px;}
QCheckBox::indicator {width:17px;height:17px;border:1px solid #75529C;border-radius:4px;background:#21182E;}
QCheckBox::indicator:checked {background:#8B5CF6;}
'''
