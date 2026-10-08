# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Synthetic UI demo and opt-in capture smoke of ONLY a window created by this script."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
native = '--capture-smoke' in sys.argv
if not native:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtCore import QTimer
from unittest.mock import patch
import queue
import threading

app = QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
app.setFont(QFont('Microsoft YaHei', 10))
if native:
    from app.manual_capture import snapshot, read_region, window_signature
    fixture = QWidget()
    fixture.setWindowTitle('Jev synthetic capture test - no real chat')
    fixture.resize(620, 400)
    fixture.setStyleSheet('background:#f5f5f5;')
    layout = QVBoxLayout(fixture)
    for text, color in [('Hello synthetic chat', '#ffffff'), ('Saturday coffee sounds good', '#b5efab'),
                         ('Only this test window is captured', '#ffffff')]:
        label = QLabel(text)
        label.setStyleSheet('font-size:22px;padding:24px;background:'+color)
        layout.addWidget(label)
    fixture.show()
    hwnd = int(fixture.winId())
    done = queue.Queue()
    def work():
        try:
            frame, sig = snapshot(hwnd)
            rows = read_region(frame, (0, 0, frame.shape[1], frame.shape[0]))
            combined = ' '.join(text for _, text in rows).lower()
            assert 'synthetic' in combined and 'coffee' in combined, 'Synthetic OCR text missing'
            done.put(None)
        except Exception as exc:
            done.put(type(exc).__name__ + ': ' + str(exc))
    QTimer.singleShot(800, lambda: threading.Thread(target=work, daemon=True).start())
    result = []
    timer = QTimer()
    def poll():
        if not done.empty():
            result.append(done.get())
            fixture.close()
            app.quit()
    timer.timeout.connect(poll)
    timer.start(100)
    QTimer.singleShot(20000, app.quit)
    app.exec()
    if not result or result[0] is not None:
        raise RuntimeError(str(result or 'capture test timeout'))
    print('Native WGC snapshot + local OCR passed on synthetic app-owned window; no image saved.')
else:
    from app.screenshot_assistant import ScreenshotAssistant
    with patch('app.screenshot_assistant.list_windows', return_value=[(1, '示例聊天窗口（虚构内容）', 1)]), \
         patch('app.screenshot_assistant.CaptureHotkey'):
        window = ScreenshotAssistant()
        window.windows.setCurrentIndex(1)
        window.replace_rows([('her', '这周有点忙，周末想出去走走'), ('me', '想去公园还是找家咖啡店？'),
                             ('her', '咖啡店吧，想找个安静的地方')])
        window.edited()
        window.output.setPlainText('以下仅为虚构界面示例，未调用模型：\n\n1. 好呀，那找家安静的，你周六还是周日方便？\n\n2. 那就喝杯咖啡歇一歇，我也想放空一下。\n\n3. 行，找个能坐着慢慢聊的地方。')
        window.show()
        app.processEvents()
        out = Path(__file__).resolve().parents[1] / 'docs' / 'screenshot-assistant-preview.png'
        assert window.grab().save(str(out))
        window.close()
        print('Synthetic screenshot assistant UI smoke passed; no capture, profile access or API calls.')
