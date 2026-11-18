"""Match native Windows caption controls to the app without losing Snap/resize."""
import ctypes
from ctypes import wintypes
import sys


def dark_caption(window):
    if sys.platform != 'win32':
        return
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.platformName() != 'windows':
        return
    set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
    set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    set_attribute.restype = ctypes.c_long
    # Windows 10 supports immersive dark captions; 11 also supports explicit colors.
    attributes = {20: 1, 33: 2, 34: 0x433327, 35: 0x211710, 36: 0xECDED4}
    for attribute, number in attributes.items():
        value = wintypes.DWORD(number)
        set_attribute(int(window.winId()), attribute, ctypes.byref(value), ctypes.sizeof(value))
