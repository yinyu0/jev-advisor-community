# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Windows global capture shortcut, owned by the Qt GUI thread."""
import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter


class CaptureHotkey(QAbstractNativeEventFilter):
    ID = 0x4A56
    WM_HOTKEY = 0x0312
    MODIFIERS = 0x0002 | 0x0001 | 0x4000  # Ctrl + Alt + no auto-repeat

    def __init__(self, app, callback, user32=None, *, key='J', ident=None):
        super().__init__()
        self.app = app
        self.callback = callback
        self.user32 = user32 if user32 is not None else ctypes.windll.user32
        self.registered = False
        self.key = key
        if ident is not None:
            self.ID = ident

    def register(self):
        if self.registered:
            return True
        self.registered = bool(self.user32.RegisterHotKey(None, self.ID, self.MODIFIERS, ord(self.key)))
        if self.registered:
            self.app.installNativeEventFilter(self)
            self.app.aboutToQuit.connect(self.close)
        return self.registered

    def nativeEventFilter(self, event_type, message):
        if self.registered and bytes(event_type) in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_HOTKEY and msg.wParam == self.ID:
                self.callback()
                return True, 0
        return False, 0

    def close(self):
        if self.registered:
            self.registered = False
            self.user32.UnregisterHotKey(None, self.ID)
            self.app.removeNativeEventFilter(self)
