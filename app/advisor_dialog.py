# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
"""Explicit per-conversation opt-in and preview, using only session memory."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QComboBox,
                              QPlainTextEdit, QCheckBox, QPushButton, QMessageBox)
from core.advisor import payload

class AdvisorDialog(QDialog):
    def __init__(self, title, messages, profile, apply, forget, parent=None):
        super().__init__(parent)
        self.setWindowTitle('军师模式 · ' + title)
        self.resize(560, 650)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('当前对象：' + title))
        notice = QLabel('仅当前会话生效，切换会话需重新确认。背景仅保留到程序退出。\n'
                        '启用后，下方消息与背景、模型生成的策略及设置中的口吻会用于模型请求。\n'
                        '新增消息也会继续分析并产生调用费用；支持单聊文字。')
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.fields = {}
        for key, label in [('relationship', '当前关系'), ('goal', '当前目标'),
                           ('background', '确认过的背景'), ('boundaries', '边界 / 不希望做的事')]:
            layout.addWidget(QLabel(label))
            if key == 'goal':
                widget = QComboBox()
                widget.addItems(['自然接话', '邀约', '澄清', '修复', '拒绝', '退出'])
                widget.setCurrentText(profile.get(key, '自然接话'))
            else:
                widget = QLineEdit(profile.get(key, ''))
                widget.setMaxLength(3000)
            self.fields[key] = widget
            layout.addWidget(widget)
        self.confirm = QCheckBox('我已核对当前对象与消息归属，允许发送这些资料用于分析')
        layout.addWidget(self.confirm)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview)
        def values():
            return {k: (w.currentText() if k == 'goal' else w.text()) for k, w in self.fields.items()}
        def refresh():
            data = payload(messages, values(), len(messages))
            lines = ['即将分析的聊天文字（请检查是否识别正确）：', '']
            for item in data['messages']:
                who, text = (item.get('from'), item.get('text')) if isinstance(item, dict) else item[:2]
                lines.extend([('我：' if who == 'me' else '对方：') + str(text), ''])
            lines.append('本次背景：')
            for key, label in [('relationship', '关系'), ('goal', '目标'), ('background', '背景'), ('boundaries', '边界')]:
                lines.append(label + '：' + (data['profile'][key] or '未填写'))
            self.preview.setPlainText('\n'.join(lines))
        for key, widget in self.fields.items():
            (widget.currentTextChanged if key == 'goal' else widget.textChanged).connect(refresh)
        refresh()
        for label, deep in [('启用并生成回复', False), ('深入分析（额外一次模型调用）', True)]:
            button = QPushButton(label)
            def submit(checked=False, deep=deep):
                if not self.confirm.isChecked():
                    QMessageBox.information(self, '请确认', '请先核对预览中的对象与说话人。')
                    return
                if apply(values(), deep):
                    self.accept()
            button.clicked.connect(submit)
            layout.addWidget(button)
        clear = QPushButton('停用并清除此对象的临时背景')
        clear.clicked.connect(lambda: (forget(), self.reject()))
        layout.addWidget(clear)
