# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
import json
import os
import queue
import unittest
from unittest.mock import patch

from core import engine
from app import settings

class SingleModelTests(unittest.TestCase):
    def test_every_phase_uses_one_key_provider_and_model(self):
        calls = []
        def completion(protocol, url, key, model, system, turns, **kwargs):
            calls.append((url, key, model))
            if '你是沟通分析器' in system:
                data = json.loads(turns[0])
                answers = {}
                for name, q in data['questions'].items():
                    if q['type'] == 'choice':
                        answers[name] = {'choice': next(iter(q['criteria']))}
                    elif q['type'] == 'noul':
                        answers[name] = {'value': True}
                    else:
                        answers[name] = {'score': 1}
                return json.dumps({'answers': answers})
            if '本次执行规则' in system:
                return json.dumps({'strategy': '轻松回应', 'facts': ['对方问候'],
                                   'unknowns': [], 'stop_condition': '不欢迎则停止', 'should_reply': True})
            return json.dumps(['最近怎么样', '今天忙吗', '周末有什么计划'])
        from core.providers import DRAFT_PROVIDERS
        with patch.dict(os.environ, {'LLM_API_KEY': 'one-key'}, clear=True), \
             patch('core.llm.chat', side_effect=completion), \
             patch('core.advisor.chat', side_effect=completion), \
             patch('core.draft.chat', side_effect=completion), \
             patch('core.engine.ask') as old_judge:
            for provider in ('deepseek', 'moonshot', 'zhipu', 'custom_openai'):
                calls.clear()
                custom = 'https://example.invalid/v1' if provider == 'custom_openai' else None
                result = engine.analyze([('her', '你好')], '朋友', provider=provider,
                                        model='same-model', base_url=custom, single_model=True,
                                        advisor_profile={'goal': '自然接话'})
                self.assertEqual(len(calls), 4)
                self.assertEqual(set(calls), {(custom or DRAFT_PROVIDERS[provider].base, 'one-key', 'same-model')})
                self.assertTrue(result['candidates'])
            old_judge.assert_not_called()

    def test_existing_reply_config_is_used_and_old_judge_key_is_ignored(self):
        config = {'draft_provider': 'zhipu', 'draft_model': 'my-glm',
                  'jev_provider': 'openrouter', 'jev_model': 'old-jev'}
        queried = []
        def env(name):
            queried.append(name)
            return 'reply-key' if name == 'LLM_API_KEY' else ''
        with patch.object(settings, '_read', side_effect=lambda name, default=None: config.get(name, default)), \
             patch.object(settings, '_read_env', side_effect=env):
            self.assertEqual(settings.draft_provider(), 'zhipu')
            self.assertEqual(settings.draft_model(), 'my-glm')
            self.assertTrue(settings.has_key())
            self.assertNotIn('JEV_API_KEY', queried)

    def test_jev_only_credentials_do_not_mark_single_model_ready(self):
        with patch.object(settings, '_read_env', side_effect=lambda name: 'old' if name == 'JEV_API_KEY' else ''):
            self.assertFalse(settings.has_key())

    def test_desktop_passes_only_shared_configuration(self):
        import main
        with patch.object(main, 'results', queue.Queue()), \
             patch('main.analyze', return_value={}) as analyze, \
             patch.object(settings, '_read', side_effect=lambda name, default=None: default):
            main.analyze_bg([('her', '你好')], 'sample', 0)
            self.assertTrue(analyze.call_args.kwargs['single_model'])
            self.assertNotIn('jev_provider', analyze.call_args.kwargs)
            self.assertNotIn('jev_model', analyze.call_args.kwargs)

if __name__ == '__main__':
    unittest.main()
