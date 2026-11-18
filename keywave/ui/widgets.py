from __future__ import annotations
from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, Signal, Qt, QThread
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QFont
from PySide6.QtWidgets import QPushButton, QFrame, QVBoxLayout, QLabel
import logging
from ..core import Progress, AudioError, Cancelled


class Worker(QThread):
    progress_changed = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)
    details = Signal(object)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
        self.progress = Progress(self.progress_changed.emit)
        self.progress.details = self.details.emit

    def run(self):
        try:
            result = self.function(self.progress)
            self.progress.check()
            self.succeeded.emit(result)
        except Cancelled:
            self.failed.emit('cancelled')
        except AudioError as error:
            self.failed.emit(str(error))
        except MemoryError:
            self.failed.emit('too_large')
        except PermissionError:
            self.failed.emit('write_error')
        except Exception:
            logging.exception('Operation failed')
            self.failed.emit('operation_error')


class Button(QPushButton):
    def __init__(self, text='', primary=False, parent=None):
        super().__init__(text, parent)
        self.primary = primary
        self.motion = True
        self._hover = 0.
        self.anim = QPropertyAnimation(self, b'hover', self)
        self.anim.setDuration(160)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)

    @Property(float)
    def hover(self):
        return self._hover

    @hover.setter
    def hover(self, value):
        self._hover = value
        self.update()

    def enterEvent(self, event):
        self.animate(1.)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate(0.)
        super().leaveEvent(event)

    def animate(self, value):
        self.anim.stop()
        self.anim.setDuration(160 if self.motion else 0)
        self.anim.setStartValue(self._hover)
        self.anim.setEndValue(value)
        self.anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -2, -2)
        highlighted = self.primary or self.isChecked()
        def tint(start, end):
            a, b = QColor(start), QColor(end)
            return QColor.fromRgbF(*[a.getRgbF()[i] + (b.getRgbF()[i]-a.getRgbF()[i])*self._hover for i in range(4)])
        if not self.isEnabled():
            painter.setOpacity(.55)
        if highlighted:
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, tint('#385D7E', '#456F92'))
            gradient.setColorAt(1, tint('#243F5C', '#2D4D6B'))
            painter.setBrush(gradient)
            painter.setPen(QPen(tint('#577B9D', '#87ACCA'), 1))
        else:
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, tint('#223244', '#30465D'))
            gradient.setColorAt(1, tint('#152232', '#203247'))
            painter.setBrush(gradient)
            painter.setPen(QPen(tint('#384B61', '#6C89A6'), 1))
        painter.drawRoundedRect(rect, 14, 14)
        # A faint inner reflection defines the glass edge without brightening the text.
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(187, 211, 231, 30), 1))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 13, 13)
        painter.setPen(QColor('#DCE7F1' if highlighted else '#C6D5E5'))
        font = painter.font()
        font.setWeight(QFont.Weight.DemiBold if highlighted else QFont.Weight.Medium)
        painter.setFont(font)
        if self.hasFocus():
            painter.setPen(QPen(QColor('#97B9D5'), 1, Qt.DotLine))
            painter.drawRoundedRect(rect.adjusted(3,3,-3,-3), 11, 11)
            painter.setPen(QColor('#DCE7F1'))
        painter.drawText(rect, Qt.AlignCenter, self.text())

class DropZone(QFrame):
    dropped = Signal(str)
    browse = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName('dropzone')
        self.setMinimumHeight(210)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.title = QLabel()
        self.title.setObjectName('dropTitle')
        self.subtitle = QLabel()
        self.subtitle.setObjectName('muted')
        self.button = Button(primary=True)
        self.button.setFixedWidth(220)
        self.button.clicked.connect(self.browse)
        for widget in (self.title, self.subtitle, self.button):
            layout.addWidget(widget, alignment=Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and event.mimeData().urls()[0].isLocalFile():
            event.acceptProposedAction()
            self.setStyleSheet('QFrame#dropzone {border:2px solid #789DBC;background:#203247;border-radius:22px;}')
            self.button.animate(1.)

    def dragLeaveEvent(self, event):
        self.setStyleSheet('')
        self.button.animate(0.)

    def dropEvent(self, event):
        self.setStyleSheet('')
        self.button.animate(0.)
        self.dropped.emit(event.mimeData().urls()[0].toLocalFile())
        event.acceptProposedAction()


class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName('card')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        self.title = QLabel()
        self.title.setObjectName('muted')
        self.value = QLabel('—')
        self.value.setObjectName('metric')
        self.detail = QLabel('—')
        self.detail.setWordWrap(True)
        self.detail.setObjectName('muted')
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)
