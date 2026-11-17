"""Ice Glass: calm blue, soft surfaces and Windows 11 variable typography."""
STYLE = """
QWidget { background:#EDF5FD; color:#213A56; font-family:"Segoe UI Variable", "Segoe UI", sans-serif; font-size:13px; }
QMainWindow { background:#EAF3FD; }
QFrame#sidebar { background:#F9FCFF; border-right:1px solid #DAE7F4; }
QFrame#sidebar QLabel { background:transparent; }
QLabel { background:transparent; }
QLabel#brand { font-size:23px; font-weight:800; color:#284C74; letter-spacing:2px; }
QLabel#heading { font-size:28px; font-weight:700; color:#203C60; }
QLabel#hero { font-size:34px; font-weight:700; color:#244D76; }
QLabel#muted { color:#6D859F; background:transparent; }
QLabel#metric { font-size:27px; font-weight:700; color:#2C679A; background:transparent; }
QLabel#dropTitle { font-size:22px; font-weight:650; color:#2A537F; background:transparent; }
QFrame#card {
 background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FFFFFF,stop:1 #F0F8FF);
 border:1px solid #DBEAF8; border-radius:20px;
}
QFrame#card QLabel { background:transparent; }
QFrame#dropzone {
 background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #FAFDFF,stop:1 #E6F4FF);
 border:2px dashed #B2D0EC; border-radius:22px;
}
QFrame#dropzone QLabel { background:transparent; }
QComboBox,QDoubleSpinBox,QSpinBox,QLineEdit {
 background:#FDFEFF; color:#2B4967; border:1px solid #CADFF0;
 border-radius:11px; padding:9px 11px; min-height:24px;
 selection-background-color:#C5E3FA;
}
QComboBox:hover,QDoubleSpinBox:hover,QSpinBox:hover,QLineEdit:hover { border:1px solid #8ABBE1; }
QComboBox:focus,QDoubleSpinBox:focus,QSpinBox:focus,QLineEdit:focus { border:1px solid #5DA8E6; }
QComboBox QAbstractItemView {background:#FFFFFF;color:#2D4A69;selection-background-color:#D9EFFF;border:1px solid #D5E7F6;outline:0;}
QSlider::groove:horizontal {height:6px;background:#D8E9F8;border-radius:3px;}
QSlider::sub-page:horizontal {background:#87BEE9;border-radius:3px;}
QSlider::handle:horizontal {background:#65A8DB;width:15px;margin:-5px 0;border-radius:7px;}
QProgressBar {background:#DDECF8;border:0;border-radius:4px;text-align:center;min-height:8px;}
QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #9FD1F5,stop:1 #6AADE3);border-radius:4px;}
QListWidget,QTableWidget {background:#FAFDFF;color:#2C4C6E;border:1px solid #D6E5F3;border-radius:14px;alternate-background-color:#F0F8FF;}
QListWidget::item {padding:12px;border-radius:8px;}
QListWidget::item:selected {background:#CEE8FA;color:#214A73;}
QHeaderView::section {background:#E8F4FD;color:#64819E;border:0;padding:9px;}
QScrollArea {border:0;background:transparent;}
QScrollArea > QWidget > QWidget {background:transparent;}
QScrollBar:vertical {background:transparent;width:9px;}
QScrollBar::handle:vertical {background:#C7DDED;border-radius:4px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QToolTip {background:#FCFEFF;border:1px solid #BFD9EE;color:#345878;padding:8px;}
QCheckBox {spacing:8px;color:#355572;}
QCheckBox::indicator {width:17px;height:17px;border:1px solid #A7CBE7;border-radius:5px;background:#F8FCFF;}
QCheckBox::indicator:checked {background:#7CB6E3;border:1px solid #65A4D6;}
QFrame#glassOverlay {background:rgba(234,245,255,235);border:2px dashed #8DBDE1;border-radius:28px;}
QLabel#overlaySymbol {font-size:48px;color:#498EC7;font-weight:700;}
QLabel#overlayTitle {font-size:30px;color:#244B73;font-weight:750;}
QLabel#overlaySubtitle {font-size:15px;color:#6686A4;}
"""
