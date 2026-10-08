# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Persistent profile editor; selecting/saving never invokes a model."""
from copy import deepcopy
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPlainTextEdit, QCheckBox, QPushButton, QMessageBox, QTabWidget, QWidget)
from core.advisor import payload
from app.advisor_store import FIELDS, PERSONAL, GOALS, StoreError

class AdvisorDialog(QDialog):
    def __init__(self, title, messages, profile, apply, forget, parent=None,
                 *, store=None, link=None, confirmed=False, manual=False):
        super().__init__(parent)
        self.store, self.link = store, link
        self.apply_profile, self.forget_profile = apply, forget
        self.messages = messages
        self.loading = True
        self.selected = store.candidate(link) if store else None
        if store and profile.get('profile_id') in store.data['profiles']:
            self.selected = profile['profile_id']
        self.setWindowTitle('军师模式 · ' + title)
        self.resize(660, 720)
        layout = QVBoxLayout(self)
        self.mapping = QLabel()
        layout.addWidget(self.mapping)
        notice = QLabel('资料在本机加密保存，重启可复用；切换对象需确认。保存不调用模型。\n'
                        '启用后，当前资料、聊天和设置中的口吻将发送给模型；新增消息会继续分析并产生费用。')
        notice.setWordWrap(True)
        if manual:
            notice.setText('资料在本机加密保存。保存和选择档案不调用模型。\n'
                           '使用后返回截图助手；只有点击“生成回复”才会发送已确认的资料和聊天。')
        layout.addWidget(notice)
        row = QHBoxLayout()
        self.selector = QComboBox()
        row.addWidget(self.selector, 1)
        new = QPushButton('新建对象')
        new.clicked.connect(self.new_profile)
        row.addWidget(new)
        delete = QPushButton('删除档案')
        delete.clicked.connect(self.delete_profile)
        row.addWidget(delete)
        layout.addLayout(row)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        target = QWidget()
        form = QVBoxLayout(target)
        self.name = QLineEdit()
        self.name.setMaxLength(100)
        form.addWidget(QLabel('档案名称（用于区分对象）'))
        form.addWidget(self.name)
        self.fields = {}
        labels = [('relationship', '当前关系'), ('goal', '本次目标（按对象记住）'),
                  ('background', '对方已知背景'), ('experiences', '共同经历'),
                  ('boundaries', '此对象的沟通边界')]
        for key, label in labels:
            form.addWidget(QLabel(label))
            widget = QComboBox() if key == 'goal' else QLineEdit()
            if key == 'goal':
                widget.addItems(GOALS)
            else:
                widget.setMaxLength(3000)
            self.fields[key] = widget
            form.addWidget(widget)
        tabs.addTab(target, '对象档案')
        mine = QWidget()
        personal_form = QVBoxLayout(mine)
        self.personal_fields = {}
        for key, label in [('name', '我的称呼（选填）'), ('background', '我的基本背景（选填）'),
                           ('boundaries', '我的表达偏好与沟通边界（选填）')]:
            personal_form.addWidget(QLabel(label))
            widget = QLineEdit()
            widget.setMaxLength(3000)
            self.personal_fields[key] = widget
            personal_form.addWidget(widget)
        personal_form.addWidget(QLabel('说话风格沿用软件“设置”里的配置；这里不重复保存。'))
        personal_form.addStretch()
        tabs.addTab(mine, '我的资料（所有对象共用）')
        self.associate = QCheckBox('保存时关联当前聊天，下次自动带出候选档案')
        self.associate.setChecked(True)
        layout.addWidget(self.associate)
        self.confirm = QCheckBox('我已核对当前对象、档案与消息归属，允许用于分析')
        layout.addWidget(self.confirm)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(120)
        layout.addWidget(self.preview)
        self.status = QLabel()
        layout.addWidget(self.status)
        row = QHBoxLayout()
        save = QPushButton('保存资料')
        save.clicked.connect(lambda: self.save_profile())
        row.addWidget(save)
        actions = [('保存并使用此档案（不生成）', False)] if manual else [('保存并启用，生成回复', False), ('保存并深入分析', True)]
        for label, deep in actions:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, deep=deep: self.submit(deep))
            row.addWidget(button)
        layout.addLayout(row)
        stop = QPushButton('停用军师（保留已保存档案）')
        stop.clicked.connect(self.stop)
        layout.addWidget(stop)
        self.chat_title = title
        self.reload_choices()
        # Persisted facts win over an older in-memory activation, including edits from another instance.
        initial = profile if profile and not profile.get('profile_id') and not self.selected else None
        self.load_profile(initial)
        matches = payload([], profile)['profile'] == payload([], self.values())['profile']
        self.confirm.setChecked(confirmed and matches)
        self.selector.currentIndexChanged.connect(self.choose)
        for key, widget in self.fields.items():
            (widget.currentTextChanged if key == 'goal' else widget.textChanged).connect(self.changed)
        for widget in [self.name, *self.personal_fields.values()]:
            widget.textChanged.connect(self.changed)
        self.associate.toggled.connect(self.changed)
        self.loading = False
        self.baseline = self.snapshot()
        self.refresh()
        if not store:
            save.setEnabled(False)
            delete.setEnabled(False)
            new.setEnabled(False)
            self.associate.setEnabled(False)
            notice.setText('示例或临时会话：不保存档案。启用前请检查对象与消息。')

    def snapshot(self):
        return (self.name.text(), self.values(), self.associate.isChecked())

    def values(self):
        data = {k: (w.currentText() if k == 'goal' else w.text()) for k, w in self.fields.items()}
        data['personal'] = {k: w.text() for k, w in self.personal_fields.items()}
        if self.selected:
            data['profile_id'] = self.selected
        return data

    def reload_choices(self):
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem('新对象（未保存）', None)
        if self.store:
            for ident, data in self.store.data['profiles'].items():
                self.selector.addItem(data['name'] + ' · ' + ident[:6], ident)
        self.selector.setCurrentIndex(max(0, self.selector.findData(self.selected)))
        self.selector.blockSignals(False)

    def load_profile(self, active=None):
        self.loading = True
        data = deepcopy(active) if active else deepcopy(self.store.data['profiles'].get(self.selected, {}) if self.store else {})
        personal = data.get('personal', self.store.data['personal'] if self.store else {})
        saved = self.store.data['profiles'].get(self.selected, {}) if self.store else {}
        self.name.setText(saved.get('name', self.chat_title))
        for k, w in self.fields.items():
            if k == 'goal':
                w.setCurrentText(data.get(k) or GOALS[0])
            else:
                w.setText(data.get(k, ''))
        for k, w in self.personal_fields.items():
            w.setText(personal.get(k, ''))
        self.confirm.setChecked(False)
        self.loading = False
        self.baseline = self.snapshot()
        self.refresh()

    def changed(self, *args):
        if not self.loading:
            self.confirm.setChecked(False)
            self.status.setText('有未保存修改；生成前请重新核对。')
            self.refresh()

    def refresh(self):
        self.mapping.setText('当前聊天：' + self.chat_title + '  →  档案：' + (self.name.text() or '未命名'))
        data = payload(self.messages, self.values(), len(self.messages))
        lines = ['即将用于分析的内容：']
        for item in data['messages']:
            who, text = (item.get('from'), item.get('text')) if isinstance(item, dict) else item[:2]
            lines.append(('我：' if who == 'me' else '对方：') + str(text))
        labels = dict(relationship='关系', goal='目标', background='对方背景', experiences='共同经历', boundaries='对象边界')
        lines.extend(label + '：' + (data['profile'].get(k) or '未填写') for k, label in labels.items())
        personal = data['profile'].get('personal', {})
        for k, label in [('name', '我的称呼'), ('background', '我的背景'), ('boundaries', '我的偏好与边界')]:
            lines.append(label + '：' + (personal.get(k) or '未填写'))
        self.preview.setPlainText('\n'.join(lines))

    def save_profile(self):
        if not self.store:
            self.baseline = self.snapshot()
            return True
        try:
            previous = deepcopy(self.store.data)
            data = self.values()
            self.selected = self.store.save(self.selected, self.name.text(), data,
                                            data['personal'], self.link, self.associate.isChecked())
            if self.store.data != previous:
                # Invalidate any active cached strategy when persisted facts change.
                self.forget_profile()
            self.reload_choices()
            self.baseline = self.snapshot()
            self.status.setText('已加密保存到当前 Windows 用户；没有调用模型。')
            return True
        except StoreError as exc:
            QMessageBox.warning(self, '未保存', str(exc))
            return False

    def resolve_changes(self):
        if self.snapshot() == self.baseline:
            return True
        result = QMessageBox.question(self, '未保存的修改', '是否保存当前资料？',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        return self.save_profile() if result == QMessageBox.Save else result == QMessageBox.Discard

    def choose(self, index):
        ident = self.selector.itemData(index)
        if ident == self.selected:
            return
        if not self.resolve_changes():
            self.reload_choices()
            return
        self.selected = ident
        self.forget_profile()
        self.reload_choices()
        self.load_profile()

    def new_profile(self):
        if self.resolve_changes():
            self.forget_profile()
            self.selected = None
            self.reload_choices()
            self.load_profile()
            self.status.setText('新建对象；填写名称后保存。')

    def delete_profile(self):
        if not self.store or not self.selected:
            return
        if QMessageBox.question(self, '永久删除档案', '删除此对象档案及所有聊天关联？未保存编辑将放弃；我的公共资料仍保留。',
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.store.delete(self.selected)
            self.forget_profile()
            self.selected = None
            self.reload_choices()
            self.load_profile()
            self.status.setText('对象档案已删除。')
        except StoreError as exc:
            QMessageBox.warning(self, '删除失败', str(exc))

    def submit(self, deep):
        if not self.confirm.isChecked():
            QMessageBox.information(self, '请确认', '请先核对当前对象、档案及消息归属。')
            return
        if self.save_profile() and self.apply_profile(self.values(), deep):
            self.accept()

    def stop(self):
        if self.resolve_changes():
            self.forget_profile()
            super().reject()

    def reject(self):
        if self.resolve_changes():
            super().reject()

    def closeEvent(self, event):
        if self.resolve_changes():
            event.accept()
        else:
            event.ignore()
