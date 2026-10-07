# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
import json
import unittest
from unittest.mock import patch, Mock
from core import jev_client, llm, llm_judge, engine
from core.questions import JUDGE_QUESTIONS, build_rank_question
from core.providers import DRAFT_PROVIDERS

def response(questions):
    answers = {}
    for name, q in questions.items():
        if q['type'] == 'choice':
            answers[name] = {'choice': next(iter(q['criteria']))}
        elif q['type'] == 'noul':
            answers[name] = {'value': True}
        else:
            answers[name] = {'score': 2}
    return {'answers': answers}

class JudgeTests(unittest.TestCase):
    def test_all_types_are_validated_without_invented_probabilities(self):
        questions = {**JUDGE_QUESTIONS, **build_rank_question(['甲', '乙'])}
        result = llm_judge.parse_answers(json.dumps(response(questions)), questions)
        self.assertEqual(result['answers']['literal_question']['noul'], 1.0)
        self.assertEqual(result['answers']['best_reply']['choice'], 'reply_a')
        self.assertNotIn('probabilities', result['answers']['best_reply'])

    def test_malformed_missing_wrong_type_and_out_of_range_rejected(self):
        for body in ['secret chat', '[]', '{}', json.dumps({'answers': {}})]:
            with self.assertRaises(jev_client.JevError):
                llm_judge.parse_answers(body, JUDGE_QUESTIONS)
        for name, value in [('true_intent', {'choice': 'made-up'}),
                            ('literal_question', {'value': 'false'}),
                            ('danger_level', {'score': True}),
                            ('danger_level', {'score': 99}),
                            ('danger_level', {'score': float('nan')})]:
            body = response(JUDGE_QUESTIONS)
            body['answers'][name] = value
            with self.assertRaises(jev_client.JevError):
                llm_judge.parse_answers(json.dumps(body), JUDGE_QUESTIONS)

    @patch('core.jev_client._api_key', return_value='test-only')
    @patch('core.jev_client._ask_openrouter')
    @patch('core.llm.chat')
    def test_both_providers_route_directly_not_openrouter(self, chat, router, key):
        chat.return_value = json.dumps(response(JUDGE_QUESTIONS))
        for provider in ('moonshot', 'zhipu', 'deepseek'):
            result = jev_client.ask({'chat': {}}, JUDGE_QUESTIONS, provider=provider, model='test-model')
            self.assertIn('best_action', result['answers'])
            self.assertEqual(chat.call_args.args[1], DRAFT_PROVIDERS[provider].base)
            self.assertEqual(chat.call_args.args[2], 'test-only')
            self.assertIsNone(chat.call_args.kwargs['temperature'])
        router.assert_not_called()

    @patch('core.jev_client._api_key', return_value='test-only')
    @patch('core.llm.chat', side_effect=jev_client.JevError('network failure'))
    @patch('core.jev_client._ask_openrouter')
    def test_failure_does_not_fall_back_to_another_service(self, router, chat, key):
        with self.assertRaises(jev_client.JevError):
            jev_client.ask({}, JUDGE_QUESTIONS, provider='zhipu', model='test')
        router.assert_not_called()

    @patch('core.llm.list_models', return_value=['test-model'])
    def test_model_listing_uses_selected_provider(self, listing):
        for provider in ('moonshot', 'zhipu', 'deepseek'):
            self.assertEqual(jev_client.list_models(provider, 'key'), ['test-model'])
            self.assertEqual(listing.call_args.args[1], DRAFT_PROVIDERS[provider].base)

    @patch('core.jev_client._api_key', return_value='test')
    @patch('core.llm.chat')
    def test_missing_model_fails_without_network(self, chat, key):
        with self.assertRaises(jev_client.JevError):
            jev_client.ask({}, JUDGE_QUESTIONS, provider='moonshot')
        chat.assert_not_called()

    @patch('core.jev_client._api_key', return_value='fake-deepseek-key')
    @patch('core.jev_client._ask_openrouter')
    @patch('core.llm.chat')
    def test_deepseek_default_model_and_non_thinking_request(self, chat, router, key):
        chat.return_value = json.dumps(response(JUDGE_QUESTIONS))
        jev_client.ask({'chat': {}}, JUDGE_QUESTIONS, provider='deepseek')
        self.assertEqual(chat.call_args.args[1], 'https://api.deepseek.com')
        self.assertEqual(chat.call_args.args[3], 'deepseek-flash')
        self.assertEqual(chat.call_args.kwargs['extra_body'], {'thinking': {'type': 'disabled'}})
        router.assert_not_called()

    @patch('openai.OpenAI')
    def test_optional_temperature_is_absent_from_request(self, client):
        client.return_value.chat.completions.create.return_value = Mock(choices=[Mock(message=Mock(content='{}'))])
        llm.chat('openai', 'https://api.moonshot.cn/v1', 'fake', 'test', 'system', ['hello'], temperature=None)
        self.assertNotIn('temperature', client.return_value.chat.completions.create.call_args.kwargs)

    @patch('core.jev_client._api_key', return_value='test')
    @patch('core.engine.draft_candidates', return_value=['甲', '乙', '丙'])
    @patch('core.llm.chat')
    def test_full_engine_uses_text_judge_for_both_rounds(self, chat, draft, key):
        def answer(*args, **kwargs):
            data = json.loads(args[5][0])
            body = response(data['questions'])
            if 'best_reply' in body['answers']:
                body['answers']['best_reply']['choice'] = 'reply_b'
            return json.dumps(body)
        chat.side_effect = answer
        for provider in ('moonshot', 'zhipu', 'deepseek'):
            chat.reset_mock()
            result = engine.analyze([('her', '你好')], 'friends', jev_provider=provider, jev_model='test')
            self.assertEqual(result['best_reply'], '乙')
            self.assertEqual(chat.call_count, 2)
            self.assertEqual(result['scores'], [0.0, 0.0, 0.0])

if __name__ == '__main__':
    unittest.main()
