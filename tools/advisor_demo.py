# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
"""Synthetic preview only: no screen capture, API calls, or message sending."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.overlay import Overlay
from app.advisor_dialog import AdvisorDialog
from app import settings
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont

if '--smoke' in sys.argv:
    # Windows offscreen Qt does not automatically enumerate system fonts.
    app = QApplication.instance() or QApplication([])
    for font in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/segoeui.ttf'):
        if Path(font).exists():
            QFontDatabase.addApplicationFont(font)
    app.setFont(QFont('Microsoft YaHei', 10))

# Preview does not read credentials or modify user settings.
settings._read = lambda name, default=None: default
settings._read_env = lambda name: ''
settings.save = lambda *args, **kwargs: None

MESSAGES = [('me', '周末想出去走走', None), ('her', '可以呀，不过周六要加班', None)]
PROFILE = {'relationship': '刚认识两周', 'goal': '邀约', 'background': '尚未单独见面', 'boundaries': '不催促'}
RESULT = {'candidates': ['那周日有空吗，一起喝杯咖啡', '那等你忙完，周日出来走走？', '周日怎么样，有家咖啡店想去试试'],
          'best_index': 0, 'scores': [], 'answers': {}, 'advisor': {
              'strategy': '问一次具体的替代时间，给对方选择空间（示例内容）',
              'facts': ['对方表示周六加班'], 'unknowns': ['周日是否有空'],
              'stop_condition': '再次含糊且没有替代安排时，暂缓邀约', 'should_reply': True}}

ov = Overlay(on_fill=lambda text: ov.set_status('演示模式：不会填入或发送', 'warning'))
ov.win.setWindowTitle('军师模式 · 示例预览（无网络 / 无采集）')
ov.subtitle.setText('军师模式 · 示例预览')
ov.captureSwitch.setEnabled(False)
ov.settingsButton.setEnabled(False)
ov.setupButton.setEnabled(False)
ov.set_capture(False, '示例预览：不读取真实聊天，不调用模型')
ov.set_chat('示例对象')
for who, text, name in MESSAGES:
    ov.log_message(who, text, name, chat='示例对象')
ov.show(RESULT)
def open_demo():
    dialog = AdvisorDialog('示例对象', MESSAGES, PROFILE,
                           lambda profile, deep: True, lambda: None)
    dialog.exec()
ov.advisorButton.clicked.connect(open_demo)
if '--smoke' in sys.argv:
    ov.app.processEvents()
    assert '问一次' in ov.advisorText.toPlainText()
    assert len(ov.cards) == 3
    dialog = AdvisorDialog('示例对象', MESSAGES, PROFILE, lambda p, d: True, lambda: None)
    dialog.show()
    ov.app.processEvents()
    assert not dialog.confirm.isChecked()
    assert '周六' in dialog.preview.toPlainText()
    out = Path(__file__).resolve().parents[1] / 'docs'
    ov.win.grab().save(str(out / 'advisor-preview.png'))
    dialog.grab().save(str(out / 'advisor-settings-preview.png'))
    dialog.close()
    ov.open_settings()
    ov.app.processEvents()
    ov.settingsPage.ensureWidgetVisible(ov.draft.modelBox, 20, 80)
    ov.settingsPage.horizontalScrollBar().setValue(0)
    ov.app.processEvents()
    assert ov.settingsPage.widget().width() <= ov.settingsPage.viewport().width()
    ov.win.grab().save(str(out / 'single-model-settings.png'))
    ov.win.close()
    print('UI smoke passed: overlay, candidates, preview, explicit confirmation')
else:
    ov.run()
