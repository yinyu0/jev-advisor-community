# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Single-window WGC snapshots, never saved or uploaded. No application allowlist."""
import ctypes
from ctypes import wintypes
import os
import threading
import numpy as np

u32 = ctypes.WinDLL('user32', use_last_error=True)
u32.IsWindow.argtypes = [wintypes.HWND]
u32.IsWindowVisible.argtypes = [wintypes.HWND]
u32.IsIconic.argtypes = [wintypes.HWND]
u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u32.GetDpiForWindow.argtypes = [wintypes.HWND]


def window_signature(hwnd):
    if not u32.IsWindow(hwnd):
        raise ValueError('目标窗口已关闭，请重新选择。')
    if u32.IsIconic(hwnd):
        raise ValueError('请先还原目标窗口，再采集。')
    rect, pid = wintypes.RECT(), wintypes.DWORD()
    if not u32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise ValueError('无法读取窗口尺寸。')
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return (pid.value, rect.right - rect.left, rect.bottom - rect.top, u32.GetDpiForWindow(hwnd))


def list_windows():
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    @callback_type
    def visit(hwnd, _):
        if u32.IsWindowVisible(hwnd):
            name = ctypes.create_unicode_buffer(1024)
            u32.GetWindowTextW(hwnd, name, len(name))
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if name.value.strip() and pid.value != os.getpid():
                found.append((int(hwnd), name.value, pid.value))
        return True
    u32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    u32.EnumWindows(visit, 0)
    return found


def snapshot(hwnd, timeout=8):
    from windows_capture import WindowsCapture
    signature = window_signature(hwnd)
    ready, frames = threading.Event(), []
    cap = WindowsCapture(cursor_capture=None, draw_border=None, window_hwnd=hwnd)
    @cap.event
    def on_frame_arrived(frame, control):
        if not ready.is_set():
            frames.append(np.ascontiguousarray(frame.frame_buffer[:, :, :3][:, :, ::-1]))
            ready.set()
    @cap.event
    def on_closed():
        ready.set()
    control = cap.start_free_threaded()
    try:
        if not ready.wait(timeout) or not frames:
            raise ValueError('窗口没有返回画面，请检查是否支持截图，或还原窗口后重试。')
        if window_signature(hwnd) != signature:
            raise ValueError('截图期间窗口尺寸或缩放已变化，请重新框选。')
        frame = frames[0]
        if frame.size == 0 or float(frame.std()) < 1:
            raise ValueError('截图为空白或黑屏，请检查目标窗口后重试。')
        return frame, signature
    finally:
        control.stop()


def read_region(frame, region):
    from app.ocr import _engine
    x, y, w, h = region
    crop = np.ascontiguousarray(frame[y:y+h, x:x+w])
    if crop.size == 0 or float(crop.std()) < 1:
        raise ValueError('框选区域为空白，请重新选择聊天区域。')
    result, _ = _engine()(crop, use_cls=False)
    messages = []
    for box, text, score in sorted(result or [], key=lambda row: (row[0][0][1], row[0][0][0])):
        if not text.strip():
            continue
        center = sum(point[0] for point in box) / len(box) / w
        # A suggestion, never confirmed automatically. Arbitrary layouts need correction.
        role = 'me' if center > .6 else 'her' if center < .4 else ''
        messages.append((role, text.strip()))
    if not messages:
        raise ValueError('没有识别到文字，请调整区域、放大文字或手动输入。')
    return messages


def merge_messages(old, new, limit=200):
    """Only dedupe contiguous suffix/prefix overlap; preserve repeated messages within a frame."""
    overlap = 0
    for size in range(1, min(len(old), len(new)) + 1):
        if old[-size:] == new[:size]:
            overlap = size
    if new and len(new) <= len(old):
        # Identical re-capture of any complete contiguous viewport.
        if any(old[i:i+len(new)] == new for i in range(len(old)-len(new)+1)):
            return old[-limit:]
    return (old + new[overlap:])[-limit:]
