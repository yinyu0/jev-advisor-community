# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
import json
import unittest
from unittest.mock import patch

from core import advisor, engine
from core.jev_client import JevError
from app.advisor_state import AdvisorSessions

PROFILE = {'relationship': '暧昧', 'goal': '邀约', 'background': '认识两周', 'boundaries': '不催促'}
ADVICE = {'strategy': '提出一个具体时间', 'facts': ['对方愿意见面'],
          'unknowns': ['可用时间'], 'stop_condition': '对方明确拒绝则停止', 'should_reply': True}

class AdvisorTests(unittest.TestCase):
    def test_context_and_profile_are_bounded(self):
        data = advisor.payload([('her', str(i)) for i in range(40)], {**PROFILE, 'secret': 'omit'}, 3)
        self.assertEqual(len(data['messages']), 3)
        self.assertNotIn('secret', data['profile'])

    def test_no_background_shared_after_switch(self):
        sessions = AdvisorSessions()
        sessions.activate('A', PROFILE)
        sessions.get('A')['goal'] = '退出'
        self.assertEqual(sessions.get('A')['goal'], '邀约')
        self.assertIsNone(sessions.get('B'))
        sessions.leave()
        self.assertIsNone(sessions.get('A'))
        sessions.forget('A')
        self.assertNotIn('A', sessions.profiles)

    @patch('core.advisor._api_key', return_value='test')
    @patch('core.advisor.chat')
    def test_structured_response_and_knowledge(self, call, key):
        call.return_value = json.dumps(ADVICE, ensure_ascii=False)
        self.assertEqual(advisor.strategy([('her', '可以见面')], PROFILE), ADVICE)
        self.assertIn('参考资料', call.call_args.args[4])
        self.assertIn('认识两周', call.call_args.args[5][0])

    @patch('core.advisor._api_key', return_value='test')
    @patch('core.advisor.chat')
    def test_bad_output_does_not_leak_content(self, call, key):
        for raw in ('private chat text', '[]', json.dumps({**ADVICE, 'should_reply': 'false'})):
            call.return_value = raw
            with self.assertRaises(JevError) as ctx:
                advisor.strategy([], PROFILE)
            self.assertNotIn(raw, str(ctx.exception))

    @patch('core.engine.draft_candidates')
    @patch('core.engine.ask')
    @patch('core.advisor.strategy', return_value={**ADVICE, 'should_reply': False})
    def test_wait_advice_does_not_create_messages(self, strat, ask, draft):
        result = engine.analyze([('her', '不要联系了')], '暧昧', advisor_profile=PROFILE)
        self.assertEqual(result['candidates'], [])
        ask.assert_not_called()
        draft.assert_not_called()

    @patch('core.engine.draft_candidates')
    @patch('core.engine.ask')
    @patch('core.advisor.strategy', return_value=ADVICE)
    def test_deep_analysis_is_not_sendable(self, strat, ask, draft):
        self.assertEqual(engine.analyze([('her', '好')], '暧昧', advisor_profile=PROFILE, deep=True)['best_reply'], '')
        draft.assert_not_called()

    @patch('core.engine.draft_candidates', return_value=['周六喝咖啡吗', '周日有空吗', '这周哪天方便'])
    @patch('core.engine.ask', return_value={'answers': {}})
    @patch('core.advisor.strategy', return_value=ADVICE)
    def test_drafting_and_ranking_share_strategy(self, strat, ask, draft):
        result = engine.analyze([('her', '好')], '暧昧', advisor_profile=PROFILE)
        self.assertIn('提出一个具体时间', draft.call_args.kwargs['guidance'])
        self.assertEqual(ask.call_args.args[0]['advisor']['profile']['goal'], '邀约')
        self.assertEqual(result['advisor'], ADVICE)

    @patch('core.advisor.strategy')
    def test_groups_fail_before_network(self, strat):
        with self.assertRaises(JevError):
            engine.analyze([('her', '好', '小明')], '朋友', advisor_profile=PROFILE)
        strat.assert_not_called()

    @patch('core.engine.draft_candidates', return_value=['好'])
    @patch('core.engine.ask', return_value={'answers': {}})
    @patch('core.advisor.strategy')
    def test_original_mode_unchanged(self, strat, ask, draft):
        self.assertEqual(engine.analyze([('her', '好')], '朋友')['best_reply'], '好')
        strat.assert_not_called()

if __name__ == '__main__':
    unittest.main()
