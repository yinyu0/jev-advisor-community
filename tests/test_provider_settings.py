# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from app import settings
from app.overlay import Overlay

class SettingsTests(unittest.TestCase):
    def test_select_and_save_kimi_or_zhipu_without_touching_real_credentials(self):
        with TemporaryDirectory() as folder, \
             patch.object(settings, '_CONFIG', str(Path(folder) / 'config.json')), \
             patch.object(settings, '_read_env', return_value=''), \
             patch.object(settings, '_set_key') as store, \
             patch.object(settings, '_notify_env'):
            ov = Overlay(on_fill=lambda text: None)
            try:
                for provider in ('moonshot', 'zhipu', 'deepseek'):
                    ov.open_settings()
                    self.assertFalse(hasattr(ov, 'jev'))
                    for group in (ov.draft,):
                        group.providerBox.setCurrentIndex(group.ids.index(provider))
                        group.keyEdit.setText('fake-local-test')
                        group.modelBox.setText('test-model')
                    ov._save()
                    self.assertEqual(settings.draft_provider(), provider)
                    self.assertEqual(settings.draft_model(), 'test-model')
                    saved = Path(settings._CONFIG).read_text(encoding='utf-8')
                    self.assertNotIn('fake-local-test', saved)
                    self.assertEqual(json.loads(saved)['draft_provider'], provider)
                self.assertEqual(store.call_count, 3)
                self.assertTrue(all(c.args[0] == 'LLM_API_KEY' for c in store.call_args_list))
            finally:
                ov.win.close()

    def test_switching_provider_cannot_reuse_previous_providers_key(self):
        with patch.object(settings, '_read_env', return_value='old-key'), \
             patch.object(settings, '_read', side_effect=lambda name, default=None: default), \
             patch.object(settings, 'save') as save:
            ov = Overlay(on_fill=lambda text: None)
            try:
                ov.open_settings()
                ov.draft.providerBox.setCurrentIndex(ov.draft.ids.index('moonshot'))
                ov.draft.modelBox.setText('test-model')
                ov._save()
                save.assert_not_called()
                self.assertIn('切换服务商', ov.settingsFeedback.text())
            finally:
                ov.win.close()

if __name__ == '__main__':
    unittest.main()
