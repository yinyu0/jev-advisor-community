# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Pure synthetic/manual assistant tests. No real capture, profiles, or network."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
from app.screenshot_assistant import ScreenshotAssistant, RegionCanvas
from app.manual_capture import merge_messages, read_region
from app.advisor_store import ProfileStore
from app.advisor_dialog import AdvisorDialog


class ManualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patches = [patch('app.screenshot_assistant.list_windows', return_value=[(1, '测试窗口', 10)]),
                        patch('app.screenshot_assistant.CaptureHotkey'),
                        patch('app.screenshot_assistant.settings.has_llm_key', return_value=True),
                        patch('app.screenshot_assistant.settings.relationship', return_value='朋友'),
                        patch('app.screenshot_assistant.settings.draft_provider', return_value='deepseek'),
                        patch('app.screenshot_assistant.settings.draft_model', return_value='test'),
                        patch('app.screenshot_assistant.settings.draft_base_url', return_value=''),
                        patch('app.screenshot_assistant.settings.style', return_value=''),
                        patch('app.screenshot_assistant.settings.thinking', return_value=False)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.w = ScreenshotAssistant()
        self.w.show()
        self.app.processEvents()
        self.addCleanup(self.w.deleteLater)
        self.addCleanup(self.w.close)

    def populate(self, messages=None):
        self.w.replace_rows(messages or [('her', '测试消息')])
        self.w.edited()

    @patch('app.screenshot_assistant.analyze')
    def test_no_generation_on_edit_or_ocr(self, analyze):
        self.populate()
        token = (self.w.current, self.w.sessions[self.w.current]['rev'], self.w.target_epoch)
        self.w.jobs.put(('ocr', token, [('her', '测试消息'), ('me', '回复')]))
        self.w.poll()
        self.assertEqual(len(self.w.rows()), 2)
        analyze.assert_not_called()
        self.assertFalse(self.w.confirm.isChecked())

    @patch('app.screenshot_assistant.threading.Thread')
    def test_missing_confirmation_or_speaker_prevents_request(self, thread):
        self.populate()
        self.w.generate()
        thread.assert_not_called()
        self.populate([('', '需要归属')])
        self.w.confirm.setChecked(True)
        self.w.generate()
        thread.assert_not_called()

    @patch('app.screenshot_assistant.analyze', return_value={'candidates': ['示例一', '示例二', '示例三']})
    @patch('app.screenshot_assistant.threading.Thread')
    def test_explicit_generate_bounds_context_and_ordinary_mode_excludes_profile(self, thread, analyze):
        thread.side_effect = lambda target, **kw: Mock(start=target)
        self.populate([('her', str(i)) for i in range(20)])
        self.w.sessions[self.w.current]['profile'] = {'background': '不得发送'}
        self.w.confirm.setChecked(True)
        self.w.generate()
        self.w.poll()
        self.assertEqual(len(analyze.call_args.args[0]), 10)
        self.assertIsNone(analyze.call_args.kwargs['advisor_profile'])
        self.assertIn('示例三', self.w.output.toPlainText())

    def test_session_switch_and_edit_discard_late_results(self):
        self.populate()
        old = self.w.current
        token = (old, self.w.sessions[old]['rev'])
        self.w.add_session('另一个对象')
        self.w.jobs.put(('result', token, {'candidates': ['错误对象结果']}))
        self.w.poll()
        self.assertNotIn('错误对象结果', self.w.output.toPlainText())
        self.w.session_box.setCurrentIndex(self.w.session_box.findData(old))
        self.assertEqual(self.w.rows(), [('her', '测试消息')])
        token = (old, self.w.sessions[old]['rev'])
        self.w.table.item(0, 1).setText('修改后')
        self.w.jobs.put(('result', token, {'candidates': ['旧文字结果']}))
        self.w.poll()
        self.assertNotIn('旧文字结果', self.w.output.toPlainText())

    def test_close_invalidates_work_and_releases_hotkey(self):
        self.populate()
        rev = self.w.sessions[self.w.current]['rev']
        self.w.close()
        self.assertGreater(self.w.sessions[self.w.current]['rev'], rev)
        self.w.hotkey.close.assert_called()

    def test_resize_requires_reselection(self):
        self.w.region = (1, 2, 30, 40)
        token = (self.w.current, self.w.sessions[self.w.current]['rev'], self.w.target_epoch)
        self.w.jobs.put(('resize', token, None))
        self.w.poll()
        self.assertIsNone(self.w.region)
        self.assertIn('重新框选', self.w.status.text())

    @patch('app.screenshot_assistant.threading.Thread')
    def test_no_model_retry_while_busy(self, thread):
        self.populate()
        self.w.confirm.setChecked(True)
        self.w.model_busy = True
        self.w.generate()
        thread.assert_not_called()

    def test_model_failure_keeps_editor(self):
        self.populate()
        token = (self.w.current, self.w.sessions[self.w.current]['rev'])
        self.w.jobs.put(('model_error', token, '请求失败'))
        self.w.poll()
        self.assertEqual(self.w.rows(), [('her', '测试消息')])
        self.assertFalse(self.w.model_busy)

    def test_region_mapping_handles_letterbox(self):
        canvas = RegionCanvas(np.zeros((200, 400, 3), dtype=np.uint8))
        canvas.resize(800, 600)
        canvas.selection = QRect(200, 200, 400, 200)
        self.assertEqual(canvas.region(), (100, 50, 200, 100))

    def test_overlap_preserves_repeated_messages_within_frame(self):
        a, b, c = ('her', 'a'), ('me', 'b'), ('her', 'c')
        self.assertEqual(merge_messages([a, b], [b, c]), [a, b, c])
        self.assertEqual(merge_messages([], [a, a]), [a, a])
        self.assertEqual(merge_messages([a, b, c], [a, b, c]), [a, b, c])

    def test_blank_crop_rejected_without_ocr(self):
        with patch('app.ocr._engine') as engine:
            with self.assertRaises(ValueError):
                read_region(np.zeros((200, 400, 3), dtype=np.uint8), (0, 0, 100, 100))
            engine.assert_not_called()

    def test_unknown_center_speaker_requires_manual_annotation(self):
        frame = np.indices((100, 100))[0].astype(np.uint8)
        frame = np.stack([frame]*3, axis=-1)
        engine = Mock(return_value=([([[40, 0], [60, 0], [60, 20], [40, 20]], '测试', .9)], None))
        with patch('app.ocr._engine', return_value=engine):
            self.assertEqual(read_region(frame, (0, 0, 100, 100)), [('', '测试')])

    def test_reorder_invalidates_confirmed_messages(self):
        self.populate([('her', '一'), ('me', '二')])
        self.w.confirm.setChecked(True)
        self.w.table.selectRow(1)
        self.w.move_row(-1)
        self.assertEqual(self.w.rows()[0], ('me', '二'))
        self.assertFalse(self.w.confirm.isChecked())

    @patch('app.screenshot_assistant.analyze')
    def test_profiles_save_and_select_without_messages_or_model(self, analyze):
        with tempfile.TemporaryDirectory() as folder:
            store = ProfileStore(Path(folder)/'profiles.dat')
            def edit(d):
                d.name.setText('虚构档案')
                d.fields['background'].setText('虚构背景')
                self.assertTrue(d.save_profile())
                d.confirm.setChecked(True)
                d.submit(False)
                return 1
            with patch('app.screenshot_assistant.ProfileStore', return_value=store), \
                 patch.object(AdvisorDialog, 'exec', new=edit):
                self.w.open_profiles()
            self.assertEqual(self.w.sessions[self.w.current]['profile']['background'], '虚构背景')
            self.assertTrue(self.w.advisor_mode.isChecked())
            self.assertIn('虚构档案', self.w.profile_label.text())
            self.assertFalse(self.w.confirm.isChecked())
            self.assertTrue(ProfileStore(store.path).data['profiles'])
            analyze.assert_not_called()

    @patch('app.screenshot_assistant.threading.Thread')
    def test_generation_waits_for_capture(self, thread):
        self.populate()
        self.w.confirm.setChecked(True)
        self.w.capture_busy = True
        self.w.generate()
        thread.assert_not_called()

    def test_refresh_keeps_selected_target(self):
        self.w.windows.setCurrentIndex(1)
        selected = self.w.windows.currentData()
        self.w.region = (10, 20, 30, 40)
        self.w.refresh_windows()
        self.assertEqual(selected, self.w.windows.currentData())
        self.assertEqual(self.w.region, (10, 20, 30, 40))

if __name__ == '__main__':
    unittest.main()
