# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Synthetic profiles in temporary directories; no capture, model calls or real user data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication, QMessageBox
from app.advisor_store import ProfileStore, StoreError
from app.advisor_dialog import AdvisorDialog
from core.advisor import payload

class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'profiles.dat'
        self.store = ProfileStore(self.path)

    def seed(self):
        return self.store.save(None, '测试对象', {'goal': '邀约', 'background': '测试背景'},
                               {'name': '测试自己', 'boundaries': '不催促'}, 'wechat:测试对象')

    def test_restart_encryption_and_delete_isolation(self):
        ident = self.seed()
        self.assertNotIn('测试背景'.encode(), self.path.read_bytes())
        self.assertNotIn(b'personal', self.path.read_bytes())
        loaded = ProfileStore(self.path)
        self.assertEqual(loaded.candidate('wechat:测试对象'), ident)
        self.assertEqual(loaded.data['profiles'][ident]['goal'], '邀约')
        other = loaded.save(None, '其他对象', {}, loaded.data['personal'], 'wechat:其他对象')
        loaded.delete(ident)
        after = ProfileStore(self.path)
        self.assertIsNone(after.candidate('wechat:测试对象'))
        self.assertIn(other, after.data['profiles'])
        self.assertEqual(after.data['personal']['name'], '测试自己')

    def test_corrupt_file_not_replaced(self):
        self.path.write_bytes(b'corrupt')
        with self.assertRaises(StoreError):
            ProfileStore(self.path)
        self.assertEqual(self.path.read_bytes(), b'corrupt')

    def test_failed_write_and_stale_editor_preserve_original(self):
        ident = self.seed()
        stale = ProfileStore(self.path)
        original = self.path.read_bytes()
        with patch('app.advisor_store.os.replace', side_effect=OSError('test')):
            with self.assertRaises(StoreError):
                self.store.save(ident, '未保存', {}, {})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.data['profiles'][ident]['name'], '测试对象')
        self.store.save(ident, '新版', {}, {})
        with self.assertRaises(StoreError):
            stale.save(ident, '旧窗口', {}, {})
        self.assertEqual(ProfileStore(self.path).data['profiles'][ident]['name'], '新版')

    def test_same_name_separate_ids_and_explicit_link(self):
        a = self.seed()
        b = self.store.save(None, '测试对象', {}, {}, 'soul:测试对象')
        self.assertNotEqual(a, b)
        self.assertEqual(self.store.candidate('wechat:测试对象'), a)
        self.assertEqual(self.store.candidate('soul:测试对象'), b)
        self.store.save(a, '测试对象', {}, {}, 'wechat:测试对象', False)
        self.assertIsNone(self.store.candidate('wechat:测试对象'))

    def dialog(self, profile=None, confirmed=False):
        d = AdvisorDialog('测试对象', [('her', '测试消息')], profile or {}, Mock(return_value=True),
                          Mock(), store=self.store, link='wechat:测试对象', confirmed=confirmed)
        self.addCleanup(d.deleteLater)
        return d

    def test_prefill_requires_confirmation_and_save_no_model(self):
        ident = self.seed()
        d = self.dialog()
        self.assertEqual(d.selected, ident)
        self.assertEqual(d.fields['background'].text(), '测试背景')
        self.assertFalse(d.confirm.isChecked())
        with patch.object(QMessageBox, 'information'):
            d.submit(False)
        d.apply_profile.assert_not_called()
        d.fields['background'].setText('新的背景')
        self.assertTrue(d.save_profile())
        d.apply_profile.assert_not_called()
        self.assertEqual(ProfileStore(self.path).data['profiles'][ident]['background'], '新的背景')
        d.confirm.setChecked(True)
        d.submit(False)
        d.apply_profile.assert_called_once()

    def test_active_confirmation_and_edit_invalidation(self):
        ident = self.seed()
        profile = dict(self.store.data['profiles'][ident], personal=self.store.data['personal'], profile_id=ident)
        d = self.dialog(profile, True)
        self.assertTrue(d.confirm.isChecked())
        d.fields['goal'].setCurrentText('修复')
        self.assertFalse(d.confirm.isChecked())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Cancel):
            self.assertFalse(d.resolve_changes())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Save):
            self.assertTrue(d.resolve_changes())
        self.assertEqual(ProfileStore(self.path).data['profiles'][ident]['goal'], '修复')

    def test_new_profile_keeps_common_data_but_not_other_background(self):
        self.seed()
        d = self.dialog()
        d.new_profile()
        self.assertIsNone(d.selected)
        self.assertEqual(d.fields['background'].text(), '')
        self.assertEqual(d.personal_fields['name'].text(), '测试自己')
        self.assertFalse(d.confirm.isChecked())

    def test_newer_saved_facts_win_over_old_activation(self):
        ident = self.seed()
        old = dict(self.store.data['profiles'][ident], personal=self.store.data['personal'], profile_id=ident)
        self.store.save(ident, '测试对象', {'background': '另一个窗口保存的新背景'}, self.store.data['personal'])
        d = self.dialog(old, True)
        self.assertEqual(d.fields['background'].text(), '另一个窗口保存的新背景')
        self.assertFalse(d.confirm.isChecked())

    def test_payload_no_id_or_other_profiles(self):
        data = payload([], {'profile_id': 'do not send', 'profiles': {'other': 'private'},
                           'experiences': '共同经历', 'personal': {'name': '我', 'unknown': 'private'}})
        self.assertEqual(data['profile']['experiences'], '共同经历')
        self.assertEqual(data['profile']['personal']['name'], '我')
        self.assertNotIn('private', str(data))
        self.assertNotIn('profile_id', data['profile'])

if __name__ == '__main__':
    unittest.main()
