# Modified/added 2026-10-08 for this unofficial GPL-3.0-only application.
# Upstream MIT notices are preserved in LICENSES/.
"""Desktop integration checks with fake UI/queues; never capture or call an API."""
import queue
import threading
import unittest
from unittest.mock import Mock, patch

import main
from app.advisor_state import AdvisorSessions

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        main.chats.clear()
        main.state.update(area=(0, 0, 1, 1), busy=False, rerun=None, hwnd=1, chat='A')
        main.ov = Mock()
        main.ov.current_chat.return_value = 'A'
        main.capture_on = threading.Event()
        main.capture_on.set()
        main.child = Mock()
        main.q = queue.Queue()
        main.results = queue.Queue()
        main.update_result = queue.Queue()
        main.advisor_sessions = AdvisorSessions()
        main.advisor_sessions.activate('A', {'goal': '邀约'})

    @patch('main.fill')
    def test_wrong_conversation_never_fills(self, fill):
        main.state['chat'] = 'B'
        with self.assertRaises(RuntimeError):
            main.fill_reply('hello')
        fill.assert_not_called()

    @patch('main.start_analyze')
    @patch('main.AdvisorDialog')
    @patch('main.ProfileStore')
    def test_save_invalidation_still_allows_confirmed_generation(self, store, dialog, analyze):
        main.chat_of('A')['history'].append(('her', '测试', None))
        main.open_advisor()
        apply, forget = dialog.call_args.args[3:5]
        forget()
        self.assertTrue(apply({'goal': '邀约'}, False))
        analyze.assert_called_once()

    @patch('main.start_analyze')
    @patch('main.AdvisorDialog')
    @patch('main.ProfileStore')
    def test_save_does_not_bypass_changed_messages(self, store, dialog, analyze):
        main.chat_of('A')['history'].append(('her', '测试', None))
        main.open_advisor()
        apply, forget = dialog.call_args.args[3:5]
        main.chat_of('A')['rev'] += 1
        forget()
        self.assertFalse(apply({'goal': '邀约'}, False))
        analyze.assert_not_called()

    @patch('main.fill')
    def test_paused_never_fills(self, fill):
        main.capture_on.clear()
        with self.assertRaises(RuntimeError):
            main.fill_reply('hello')
        fill.assert_not_called()

    def test_switch_discards_inflight_results_and_profile(self):
        main.chat_of('A')['result'] = {'candidates': ['old']}
        main.q.put(('chat', 'B'))
        main.results.put(('ok', {'candidates': ['stale']}, 'A', 0))
        main.tick()
        main.ov.show.assert_not_called()
        self.assertIsNone(main.chat_of('A')['result'])
        self.assertIsNone(main.advisor_sessions.get('A'))

    def test_pause_invalidates_inflight_work(self):
        main.chat_of('A')
        main.state['rerun'] = ('A', [('her', 'hello')])
        main.on_toggle_capture(False)
        main.results.put(('ok', {'candidates': ['stale']}, 'A', 0))
        main.tick()
        main.ov.show.assert_not_called()
        self.assertIsNone(main.state['rerun'])

    def test_newer_message_discards_older_result(self):
        main.chat_of('A')['rev'] = 2
        main.results.put(('ok', {'candidates': ['stale']}, 'A', 1))
        main.tick()
        main.ov.show.assert_not_called()

    def test_hotkey_toggles_and_ignores_delayed_worker_ack(self):
        main.toggle_capture_hotkey()
        self.assertFalse(main.capture_on.is_set())
        main.ov.set_capture.assert_called_with(False)
        main.q.put(('resumed',))
        main.drain()
        main.ov.set_capture.assert_called_with(False)
        main.toggle_capture_hotkey()
        self.assertTrue(main.capture_on.is_set())
        main.ov.set_capture.assert_called_with(True)
        main.q.put(('paused',))
        main.drain()
        main.ov.set_capture.assert_called_with(True)

    @patch('main.find_chat_hwnd', side_effect=RuntimeError('missing'))
    def test_hotkey_without_chat_stays_paused(self, find):
        main.child = None
        main.capture_on.clear()
        main.toggle_capture_hotkey()
        self.assertFalse(main.capture_on.is_set())
        self.assertFalse(main.ov.set_capture.call_args.args[0])

    def test_dead_worker_resets_hotkey_state(self):
        main.q.put(('dead', '聊天窗口关闭'))
        main.drain()
        self.assertFalse(main.capture_on.is_set())
        self.assertIsNone(main.child)

if __name__ == '__main__':
    unittest.main()
