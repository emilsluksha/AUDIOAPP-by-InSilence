"""Dark Liquid Glass: smoked surfaces, restrained highlights and readable text."""
STYLE = """
QWidget { background:transparent; color:#D4DEEC; font-family:"Segoe UI Variable", "Segoe UI", sans-serif; font-size:13px; }
QWidget#applicationSurface { background:qradialgradient(cx:0.7,cy:0.05,radius:1.2,fx:0.7,fy:0.05,stop:0 #1C3045,stop:0.5 #101A28,stop:1 #0A1019); }
QMainWindow { background:#0B1018; }
QFrame#sidebar { background:#101721; border-right:1px solid #273343; }
QFrame#sidebar QLabel { background:transparent; }
QLabel { background:transparent; }
QLabel#brand { font-size:23px; font-weight:800; color:#C5D4E6; letter-spacing:2px; }
QLabel#heading { font-size:28px; font-weight:700; color:#D4DEEC; }
QLabel#hero { font-size:34px; font-weight:700; color:#CAD9EB; }
QLabel#muted { color:#9EAFC3; background:transparent; }
QLabel#metric { font-size:27px; font-weight:700; color:#9ABFE1; background:transparent; }
QLabel#dropTitle { font-size:22px; font-weight:650; color:#CBD9EA; background:transparent; }
QFrame#card {
 background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1D2938,stop:1 #121C29);
 border:1px solid #334356; border-top:1px solid #4B5D72; border-radius:20px;
}
QFrame#card QLabel { background:transparent; }
QFrame#dropzone {
 background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #182534,stop:1 #111B29);
 border:2px dashed #415A73; border-radius:22px;
}
QFrame#dropzone QLabel { background:transparent; }
QComboBox,QDoubleSpinBox,QSpinBox,QLineEdit {
 background:#101925; color:#D4DEEC; border:1px solid #344357;
 border-radius:11px; padding:9px 11px; min-height:24px;
 selection-background-color:#35597C;
}
QComboBox:hover,QDoubleSpinBox:hover,QSpinBox:hover,QLineEdit:hover { border:1px solid #55789A; }
QComboBox:focus,QDoubleSpinBox:focus,QSpinBox:focus,QLineEdit:focus { border:1px solid #80ACD1; }
QComboBox QAbstractItemView {background:#1D2938;color:#D4DEEC;selection-background-color:#2C4865;border:1px solid #34485F;outline:0;}
QSlider::groove:horizontal {height:6px;background:#29394D;border-radius:3px;}
QSlider::sub-page:horizontal {background:#648FB5;border-radius:3px;}
QSlider::handle:horizontal {background:#A2BDD5;width:15px;margin:-5px 0;border-radius:7px;}
QProgressBar {background:#1D2C3D;border:0;border-radius:4px;text-align:center;min-height:8px;}
QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #567C9F,stop:1 #799DBF);border-radius:4px;}
QListWidget,QTableWidget {background:#182534;color:#C9D6E6;border:1px solid #334357;border-radius:14px;alternate-background-color:#121C29;}
QListWidget::item {padding:12px;border-radius:8px;}
QListWidget::item:selected {background:#29445F;color:#D4DEEC;}
QHeaderView::section {background:#1C293A;color:#A8BBD0;border:0;padding:9px;}
QScrollArea {border:0;background:transparent;}
QScrollArea > QWidget > QWidget {background:transparent;}
QScrollBar:vertical {background:transparent;width:9px;}
QScrollBar::handle:vertical {background:#3C5066;border-radius:4px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QToolTip {background:#1B293A;border:1px solid #52708D;color:#D4DEEC;padding:8px;}
QAbstractSpinBox::up-button,QAbstractSpinBox::down-button {background:#24364A;border:0;border-radius:4px;}
QWidget:disabled {color:#78899D;}
QCheckBox {spacing:8px;color:#C3D1E2;}
QCheckBox::indicator {width:17px;height:17px;border:1px solid #526B84;border-radius:5px;background:#142131;}
QCheckBox::indicator:checked {background:#7299BD;border:1px solid #89ADCE;}
QFrame#glassOverlay {background:rgba(17,29,44,245);border:2px dashed #7293B5;border-radius:28px;}
QLabel#overlaySymbol {font-size:48px;color:#A0BDD8;font-weight:700;}
QLabel#overlayTitle {font-size:30px;color:#D4DEEC;font-weight:750;}
QLabel#overlaySubtitle {font-size:15px;color:#A7BCD1;}
"""
