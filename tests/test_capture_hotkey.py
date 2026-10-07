# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
import ctypes
from ctypes import wintypes
import unittest
from unittest.mock import Mock

from app.capture_hotkey import CaptureHotkey


class HotkeyTests(unittest.TestCase):
    def test_dispatch_and_release(self):
        app, callback, api = Mock(), Mock(), Mock()
        hotkey = CaptureHotkey(app, callback, api)
        self.assertTrue(hotkey.register())
        self.assertTrue(hotkey.register())
        api.RegisterHotKey.assert_called_once_with(None, hotkey.ID, 0x4003, ord('J'))
        msg = wintypes.MSG()
        msg.message, msg.wParam = hotkey.WM_HOTKEY, hotkey.ID
        self.assertEqual(hotkey.nativeEventFilter(b'windows_dispatcher_MSG', ctypes.addressof(msg)), (True, 0))
        callback.assert_called_once()
        msg.wParam += 1
        self.assertEqual(hotkey.nativeEventFilter(b'windows_dispatcher_MSG', ctypes.addressof(msg)), (False, 0))
        callback.assert_called_once()
        hotkey.close()
        hotkey.close()
        api.UnregisterHotKey.assert_called_once_with(None, hotkey.ID)
        app.removeNativeEventFilter.assert_called_once_with(hotkey)
        hotkey.nativeEventFilter(b'windows_dispatcher_MSG', ctypes.addressof(msg))
        callback.assert_called_once()

    def test_conflict_does_not_install_or_unregister(self):
        app, api = Mock(), Mock()
        api.RegisterHotKey.return_value = 0
        hotkey = CaptureHotkey(app, Mock(), api)
        self.assertFalse(hotkey.register())
        hotkey.close()
        app.installNativeEventFilter.assert_not_called()
        api.UnregisterHotKey.assert_not_called()
