# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Manual screenshot assistant. All chat state is RAM-only; generation is explicit."""
from copy import deepcopy
import queue
import threading
import uuid
import numpy as np
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QInputDialog, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QSpinBox, QPlainTextEdit, QSplitter)
from app import settings
from app.manual_capture import list_windows, snapshot, window_signature, read_region, merge_messages
from app.capture_hotkey import CaptureHotkey
from app.advisor_dialog import AdvisorDialog
from app.advisor_store import ProfileStore, StoreError
from core.engine import analyze


class RegionCanvas(QWidget):
    def __init__(self, frame):
        super().__init__()
        h, w = frame.shape[:2]
        self.image = QImage(frame.data, w, h, frame.strides[0], QImage.Format_RGB888).copy()
        self.origin = None
        self.selection = QRect()
        self.setMinimumSize(320, 240)
        self.setCursor(Qt.CrossCursor)

    def image_rect(self):
        size = self.image.size().scaled(self.size(), Qt.KeepAspectRatio)
        return QRect((self.width()-size.width())//2, (self.height()-size.height())//2, size.width(), size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#20252a'))
        painter.drawImage(self.image_rect(), self.image)
        painter.setPen(QPen(QColor('#19c886'), 2))
        painter.drawRect(self.selection)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.image_rect().contains(event.position().toPoint()):
            self.origin = event.position().toPoint()
            self.selection = QRect(self.origin, self.origin)
            self.update()

    def mouseMoveEvent(self, event):
        if self.origin is not None and event.buttons() & Qt.LeftButton:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.image_rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = None

    def region(self):
        r, box = self.selection.intersected(self.image_rect()), self.image_rect()
        if r.width() < 10 or r.height() < 10:
            raise ValueError('请拖动鼠标圈定聊天区域。')
        sx, sy = self.image.width()/box.width(), self.image.height()/box.height()
        return (int((r.x()-box.x())*sx), int((r.y()-box.y())*sy), int(r.width()*sx), int(r.height()*sy))


class RegionDialog(QDialog):
    def __init__(self, frame, parent=None):
        super().__init__(parent)
        self.setWindowTitle('框选聊天区域 · 在窗口快照上拖动，排除无关内容')
        self.resize(880, 650)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('只在内存中预览当前窗口快照，不保存图片。'))
        self.canvas = RegionCanvas(frame)
        layout.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.region = None
        ok, cancel = QPushButton('使用此区域'), QPushButton('取消')
        ok.clicked.connect(self.finish)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        layout.addLayout(row)

    def finish(self):
        try:
            self.region = self.canvas.region()
            self.accept()
        except ValueError as exc:
            QMessageBox.information(self, '请框选', str(exc))


class ScreenshotAssistant(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('截图助手 · 手动识别与回复建议')
        self.resize(1000, 780)
        self.jobs = queue.Queue()
        self.sessions = {}
        self.current = None
        self.loading = False
        self.capture_busy = self.model_busy = False
        self.target_epoch = 0
        self.region = self.signature = self.frame_size = None
        self.hotkey = None
        self.build_ui()
        self.add_session('会话 1')
        self.refresh_windows()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)

    def build_ui(self):
        layout = QVBoxLayout(self)
        heading = QLabel('框选 → 识别并核对 → 手动生成 → 自行输入发送')
        heading.setStyleSheet('font-size:18px;font-weight:600;color:#18794e;padding:8px')
        layout.addWidget(heading)
        note = QLabel('不限定聊天软件。截图不落盘；临时聊天关闭程序即清除。识别、保存资料不调用模型。')
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.windows = QComboBox()
        self.windows.setMinimumWidth(280)
        self.windows.currentIndexChanged.connect(self.target_changed)
        row.addWidget(self.windows, 1)
        refresh, select, capture = QPushButton('刷新窗口'), QPushButton('框选 / 重新框选'), QPushButton('识别聊天')
        refresh.clicked.connect(self.refresh_windows)
        select.clicked.connect(lambda: self.capture(True))
        capture.clicked.connect(lambda: self.capture(False))
        for button in (refresh, select, capture):
            row.addWidget(button)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel('单次采集快捷键：Ctrl + Alt +'))
        self.key = QComboBox()
        self.key.addItems([c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if c != 'J'])
        self.key.setCurrentText('K')
        row.addWidget(self.key)
        bind = QPushButton('应用快捷键')
        bind.clicked.connect(self.register_hotkey)
        row.addWidget(bind)
        self.key_status = QLabel('打开助手时启用，关闭助手时释放；J 仍用于原采集开关。')
        self.key_status.setWordWrap(True)
        row.addWidget(self.key_status, 1)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.session_box = QComboBox()
        self.session_box.currentIndexChanged.connect(self.switch_session)
        row.addWidget(QLabel('当前对象 / 会话'))
        row.addWidget(self.session_box, 1)
        new = QPushButton('新建会话')
        new.clicked.connect(self.new_session)
        row.addWidget(new)
        self.advisor_mode = QCheckBox('使用军师档案')
        self.advisor_mode.toggled.connect(self.mode_changed)
        row.addWidget(self.advisor_mode)
        profiles = QPushButton('选择 / 保存资料')
        profiles.clicked.connect(self.open_profiles)
        row.addWidget(profiles)
        layout.addLayout(row)
        self.profile_label = QLabel('普通回复：不强制建档')
        layout.addWidget(self.profile_label)
        split = QSplitter(Qt.Vertical)
        editor = QWidget()
        form = QVBoxLayout(editor)
        form.setContentsMargins(0, 0, 0, 0)
        form.addWidget(QLabel('按时间顺序核对；我 / 对方仅为左右位置推测，可点击更改。多行同一消息可手动合并。'))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['说话人', '聊天文字（可编辑）'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 120)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.cellChanged.connect(lambda *args: self.edited())
        form.addWidget(self.table)
        row = QHBoxLayout()
        add, remove, clear = QPushButton('补充一条'), QPushButton('删除选中'), QPushButton('清空当前聊天')
        add.clicked.connect(lambda: self.add_row('', ''))
        remove.clicked.connect(self.remove_rows)
        clear.clicked.connect(self.clear_chat)
        for b in (add, remove, clear):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(QLabel('本次发送最近'))
        self.context = QSpinBox()
        self.context.setRange(3, 30)
        self.context.setValue(10)
        self.context.valueChanged.connect(lambda *args: self.edited())
        row.addWidget(self.context)
        row.addWidget(QLabel('条非空消息'))
        form.addLayout(row)
        order = QHBoxLayout()
        for label, action in [('上移选中', lambda: self.move_row(-1)), ('下移选中', lambda: self.move_row(1)),
                              ('合并选中行', self.merge_rows)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            order.addWidget(button)
        order.addStretch()
        form.addLayout(order)
        self.confirm = QCheckBox('我已核对当前对象、消息归属及使用资料，同意将所选内容发给已配置模型')
        form.addWidget(self.confirm)
        generate = QPushButton('生成回复 / 重新生成')
        generate.clicked.connect(self.generate)
        form.addWidget(generate)
        split.addWidget(editor)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText('生成后在这里显示候选回复。请自行输入并发送。')
        split.addWidget(self.output)
        split.setSizes([460, 160])
        layout.addWidget(split, 1)
        self.status = QLabel('先选择窗口并框选聊天区域；选择档案不触发模型。')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def add_session(self, name):
        ident = uuid.uuid4().hex
        self.sessions[ident] = dict(name=name, messages=[], profile=None, mode=False, rev=0, result='', context=10)
        self.session_box.addItem(name, ident)
        self.session_box.setCurrentIndex(self.session_box.findData(ident))

    def new_session(self):
        name, ok = QInputDialog.getText(self, '新建会话', '给对象起一个便于区分的名称：')
        if ok and name.strip():
            name = name.strip()[:100]
            if any(s['name'] == name for s in self.sessions.values()):
                QMessageBox.information(self, '名称重复', '请直接切换已有会话，或使用不同名称区分对象。')
                return
            self.add_session(name)

    def rows(self):
        return [(self.table.cellWidget(i, 0).currentData(), self.table.item(i, 1).text())
                for i in range(self.table.rowCount())]

    def replace_rows(self, messages):
        self.loading = True
        self.table.setRowCount(0)
        for role, text in messages:
            self.add_row(role, text)
        self.loading = False

    def add_row(self, role, text):
        loading = self.loading
        self.loading = True
        i = self.table.rowCount()
        self.table.insertRow(i)
        combo = QComboBox()
        for label, data in [('待标注', ''), ('对方', 'her'), ('我', 'me')]:
            combo.addItem(label, data)
        combo.setCurrentIndex(max(0, combo.findData(role)))
        combo.currentIndexChanged.connect(lambda *args: self.edited())
        self.table.setCellWidget(i, 0, combo)
        self.table.setItem(i, 1, QTableWidgetItem(text))
        self.loading = loading
        if not loading:
            self.edited()

    def remove_rows(self):
        for i in sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(i)
        self.edited()

    def move_row(self, offset):
        i = self.table.currentRow()
        messages = self.rows()
        if 0 <= i < len(messages) and 0 <= i+offset < len(messages):
            messages[i], messages[i+offset] = messages[i+offset], messages[i]
            self.replace_rows(messages)
            self.table.selectRow(i+offset)
            self.edited()

    def merge_rows(self):
        indexes = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if len(indexes) < 2 or indexes != list(range(indexes[0], indexes[-1]+1)):
            self.status.setText('请选中同一条消息的连续几行再合并。')
            return
        messages = self.rows()
        roles = {messages[i][0] for i in indexes}
        if len(roles) != 1:
            self.status.setText('说话人不同，请先修正归属再合并。')
            return
        messages[indexes[0]:indexes[-1]+1] = [(roles.pop(), '\n'.join(messages[i][1] for i in indexes))]
        self.replace_rows(messages)
        self.edited()

    def clear_chat(self):
        if QMessageBox.question(self, '清空聊天', '清空当前临时聊天和候选回复？已保存档案不会删除。') == QMessageBox.Yes:
            self.replace_rows([])
            self.edited()

    def switch_session(self, index):
        ident = self.session_box.itemData(index)
        if not ident or ident == self.current:
            return
        if self.current:
            self.sessions[self.current]['rev'] += 1
        self.current = ident
        s = self.sessions[ident]
        s['rev'] += 1
        self.loading = True
        self.advisor_mode.setChecked(s['mode'])
        self.context.setValue(s['context'])
        self.replace_rows(s['messages'])
        self.loading = False
        self.confirm.setChecked(False)
        self.output.setPlainText(s['result'])
        self.update_profile_label()

    def edited(self):
        if self.loading or not self.current:
            return
        s = self.sessions[self.current]
        s['messages'], s['context'] = self.rows(), self.context.value()
        s['rev'] += 1
        s['result'] = ''
        self.confirm.setChecked(False)
        self.output.setPlainText('内容或资料已变化，旧回复已失效；核对后重新生成。')

    def mode_changed(self, value):
        if not self.loading and self.current:
            self.sessions[self.current]['mode'] = value
            self.edited()
            self.update_profile_label()

    def update_profile_label(self):
        s = self.sessions[self.current]
        self.profile_label.setText('当前会话：' + s['name'] + ' → 档案：' + (s.get('profile_name', '已选择') if s['profile'] else '尚未选择，请点击“选择 / 保存资料”')
                                  if s['mode'] else '普通回复：不发送对象档案')

    def open_profiles(self):
        ident = self.current
        s = self.sessions[ident]
        try:
            store = ProfileStore()
        except StoreError as exc:
            QMessageBox.warning(self, '无法读取档案', str(exc))
            return
        def forget():
            s['profile'] = None
            self.advisor_mode.setChecked(False)
            self.edited()
            self.update_profile_label()
        def use(profile, deep):
            s['profile'] = deepcopy(profile)
            s['profile_name'] = store.data['profiles'].get(profile.get('profile_id'), {}).get('name', '未命名')
            self.advisor_mode.setChecked(True)
            self.edited()
            self.update_profile_label()
            return True
        dialog = AdvisorDialog(s['name'], self.rows(), s['profile'] or {}, use, forget,
            self, store=store, link='manual:'+s['name'], confirmed=False, manual=True)
        dialog.exec()

    def refresh_windows(self):
        old = self.windows.currentData()
        self.windows.blockSignals(True)
        self.windows.clear()
        self.windows.addItem('请选择目标窗口', None)
        try:
            for hwnd, title, pid in list_windows():
                self.windows.addItem(title[:100] + ' · PID ' + str(pid), (hwnd, pid))
        except Exception:
            self.status.setText('窗口列表读取失败，请稍后重试。')
        self.windows.setCurrentIndex(next((i for i in range(self.windows.count())
                                           if self.windows.itemData(i) == old), 0))
        self.windows.blockSignals(False)
        if old != self.windows.currentData():
            self.target_changed()

    def target_changed(self, *args):
        self.target_epoch += 1
        self.region = self.signature = self.frame_size = None
        if self.current:
            self.edited()
        if hasattr(self, 'status'):
            self.status.setText('窗口已更换，请核对当前聊天对象并重新框选。')

    def register_hotkey(self):
        if self.hotkey:
            self.hotkey.close()
        self.hotkey = CaptureHotkey(QApplication.instance(), lambda: self.capture(False),
                                    key=self.key.currentText(), ident=0x4A57)
        ok = self.hotkey.register()
        self.key_status.setText('已启用 Ctrl + Alt + ' + self.key.currentText() if ok else '快捷键被占用，请换一个字母或点击“识别聊天”。')

    def capture(self, select=False):
        if not self.isVisible() or self.capture_busy or QApplication.activeModalWidget() is not None:
            return
        target = self.windows.currentData()
        if not target:
            self.status.setText('请先选择目标窗口。')
            return
        self.capture_busy = True
        token = (self.current, self.sessions[self.current]['rev'], self.target_epoch)
        region, signature, shape = self.region, self.signature, self.frame_size
        self.status.setText('正在截取目标窗口…')
        def work():
            try:
                frame, sig = snapshot(target[0])
                if sig[0] != target[1]:
                    raise ValueError('窗口身份已变化，请刷新窗口列表并重新选择。')
                if select or region is None:
                    self.jobs.put(('frame', token, (frame, sig)))
                    return
                if sig != signature or frame.shape[:2] != shape:
                    self.jobs.put(('resize', token, None))
                    return
                messages = read_region(frame, region)
                self.jobs.put(('ocr', token, messages))
            except Exception as exc:
                message = str(exc) if isinstance(exc, ValueError) else '截图或 OCR 失败，请检查目标窗口后重试。'
                self.jobs.put(('capture_error', token, message))
        threading.Thread(target=work, daemon=True).start()

    def generate(self):
        if self.capture_busy:
            self.status.setText('正在识别，请等待并核对最新文字后再生成。')
            return
        if self.model_busy:
            self.status.setText('上一次请求仍在执行，请等待，避免重复付费请求。')
            return
        s = self.sessions[self.current]
        messages = [(role, text.strip()) for role, text in self.rows() if text.strip()][-self.context.value():]
        if not messages or any(role not in ('me', 'her') for role, _ in messages):
            self.status.setText('请补充聊天文字，并为本次发送的消息标注“我 / 对方”。')
            return
        if not self.confirm.isChecked():
            self.status.setText('请先核对并勾选消息与资料确认。')
            return
        if s['mode'] and not s['profile']:
            self.status.setText('请先选择军师档案，或取消军师模式。')
            return
        if not settings.has_llm_key():
            self.status.setText('请先在主界面设置中配置模型 API 密钥。聊天与资料仍可编辑保存。')
            return
        profile = deepcopy(s['profile']) if s['mode'] else None
        options = dict(relationship=(profile.get('relationship') if profile else '') or settings.relationship(),
            context=self.context.value(), provider=settings.draft_provider(), model=settings.draft_model() or None,
            base_url=settings.draft_base_url() or None, style=settings.style(), thinking=settings.thinking(),
            single_model=True, advisor_profile=profile)
        token = (self.current, s['rev'])
        self.model_busy = True
        self.status.setText('正在生成；可能包含分析、起草、排序等多次模型请求…')
        def work():
            try:
                self.jobs.put(('result', token, analyze(messages, **options)))
            except Exception:
                self.jobs.put(('model_error', token, '生成失败，请检查模型和网络后手动重试。已核对文字保留。'))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        while not self.jobs.empty():
            kind, token, data = self.jobs.get_nowait()
            if kind in ('result', 'model_error'):
                self.model_busy = False
            else:
                self.capture_busy = False
            valid = self.current == token[0] and self.sessions[self.current]['rev'] == token[1]
            if len(token) == 3:
                valid = valid and token[2] == self.target_epoch
            if not valid or not self.isVisible():
                self.status.setText('旧任务已结束；会话或内容变化，结果已丢弃。')
                continue
            if kind == 'frame':
                frame, signature = data
                epoch = self.target_epoch
                dialog = RegionDialog(frame, self)
                if dialog.exec() == QDialog.Accepted and epoch == self.target_epoch:
                    self.region, self.signature, self.frame_size = dialog.region, signature, frame.shape[:2]
                    self.status.setText('区域已选定。点击“识别聊天”获取最新画面。')
            elif kind == 'resize':
                self.region = self.signature = self.frame_size = None
                self.status.setText('窗口尺寸或缩放已变化，请重新框选。')
            elif kind == 'ocr':
                merged = merge_messages(self.rows(), data)
                self.replace_rows(merged)
                self.edited()
                self.status.setText('识别完成（最多保留 200 条）。左右归属仅为推测，请检查文字、顺序和对象后生成。')
            elif kind == 'result':
                candidates = data.get('candidates') or []
                result = '\n\n'.join(str(i+1)+'. '+text for i, text in enumerate(candidates))
                if not candidates:
                    result = '本次建议暂不回复。' + str((data.get('advisor') or {}).get('strategy', ''))
                self.sessions[self.current]['result'] = result
                self.output.setPlainText(result)
                self.status.setText('生成完成。请自行核对、输入并发送；软件不会操作目标输入框。')
            else:
                self.status.setText(data)

    def showEvent(self, event):
        super().showEvent(event)
        self.register_hotkey()

    def reject(self):
        if self.hotkey:
            self.hotkey.close()
        self.target_epoch += 1
        for s in self.sessions.values():
            s['rev'] += 1
        self.confirm.setChecked(False)
        super().reject()

    def closeEvent(self, event):
        self.reject()
        event.accept()
