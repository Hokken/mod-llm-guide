"""Shared routing safety and provider contract regressions."""

import json
import os
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_tools import GAME_TOOLS
from guide_routing import CLARIFY_FALLBACK, exact_plan, validate_plan
from llm_guide_bridge import LLMBridge


def call(name, **arguments):
    return {'tool_name': name, 'tool_input': arguments}


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.bridge = LLMBridge({})
        self.bridge.deadline = time.monotonic() + 60
        self.bridge.tool_executor.set_player_zone('duskwood')

    def test_exact_services_and_personal_context(self):
        for alias in ('griphon', 'gryphon master', 'taxi', 'flight master'):
            self.assertEqual(exact_plan('Where is the closest ' + alias + '?',
                                        'duskwood'), [call('find_service_npc',
                service_type='flight_master', zone='duskwood')])
        self.assertEqual(exact_plan('Describe my equipment', None),
                         [call('get_character_context')])

    def test_destinations_compound_and_ambiguous_need_triage(self):
        for question in ('Where is the closest gryphon in Stormwind?',
                         'Where is the closest gryphon and inn?',
                         'What is the quickest transport to Redridge?',
                         'Where is the closest strange service?'):
            self.assertIsNone(exact_plan(question, 'duskwood'))
        self.assertIsNone(exact_plan('Where is the closest gryphon?', None))

    def test_plan_validation_and_canonical_services(self):
        plan = validate_plan([call('find_service_npc',
            service_type='griphon', zone='duskwood')], GAME_TOOLS, 3)
        self.assertEqual(plan[0]['tool_input']['service_type'], 'flight_master')
        self.assertEqual(validate_plan(json.dumps([call('get_character_context')]),
                                       GAME_TOOLS, 3),
                         [call('get_character_context')])

    def test_reject_invalid_plans(self):
        for plan in ('{', {}, [], [call('unknown')],
                     [call('get_character_context', invented=1)],
                     [call('find_npc', npc_name=123)],
                     [call('find_service_npc', service_type='gryphonn',
                           zone='duskwood')],
                     [call('get_character_context')] * 4,
                     [call('ask_clarification', question=' ')],
                     [call('ask_clarification', question='|Hitem:1')],
                     [call('ask_clarification', question='Where?'),
                      call('get_character_context')]):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                validate_plan(plan, GAME_TOOLS, 3)

    def test_fast_path_records_evidence_without_classifier(self):
        bridge = self.bridge
        bridge.call_llm = MagicMock()
        bridge.tool_executor.begin_request(
            None, 'Equipped [[item:1:Test:2]]')
        context, clarification, tokens = bridge.route_question(
            'Describe my equipment', '', [])
        self.assertIn('[[item:1:Test:2]]', context)
        self.assertIsNone(clarification)
        self.assertEqual(tokens, 0)
        self.assertTrue(bridge.tool_executor.evidence.results)
        bridge.call_llm.assert_not_called()

    def test_invalid_batch_executes_nothing(self):
        bridge = self.bridge
        bridge.call_llm = MagicMock(return_value=(json.dumps([
            call('get_character_context'), call('unknown')]), 12, False))
        bridge.tool_executor.execute_tool = MagicMock()
        self.assertEqual(bridge.route_question('Find me a weapon', '', []),
                         ('', CLARIFY_FALLBACK, 12))
        bridge.tool_executor.execute_tool.assert_not_called()
        self.assertTrue(bridge.call_llm.call_args.kwargs['routing'])

    def test_ollama_empty_routing_falls_back_to_normal_loop(self):
        bridge = self.bridge
        bridge.provider = 'ollama'
        bridge.call_llm = MagicMock(return_value=('[]', 12, False))
        bridge.tool_executor.execute_tool = MagicMock()
        self.assertEqual(
            bridge.route_question('Find me a weapon', '', []),
            ('', None, 12),
        )
        bridge.tool_executor.execute_tool.assert_not_called()

    def test_ollama_empty_context_keeps_deterministic_lookup(self):
        bridge = self.bridge
        bridge.provider = 'ollama'
        bridge.call_llm = MagicMock(return_value=('[]', 7, False))
        bridge.tool_executor.execute_tool = MagicMock(
            return_value='warrior'
        )
        recent = [{
            'question': 'What sword?',
            'response': 'A sword.',
        }]
        context, clarification, tokens = bridge.route_question(
            'Describe my equipment', '', recent
        )
        self.assertIn('warrior', context)
        self.assertIsNone(clarification)
        self.assertEqual(tokens, 7)
        self.assertEqual(bridge.call_llm.call_count, 1)
        bridge.tool_executor.execute_tool.assert_called_once_with(
            'get_character_context', {}
        )

    def test_clarification_and_disabled_routing(self):
        bridge = self.bridge
        bridge.call_llm = MagicMock(return_value=(json.dumps([
            call('ask_clarification', question='Where do you want to go?')]),
            10, False))
        bridge.tool_executor.execute_tool = MagicMock()
        self.assertEqual(bridge.route_question('How do I travel?', '', []),
                         ('', 'Where do you want to go?', 10))
        bridge.tool_executor.execute_tool.assert_not_called()
        bridge.routing_enabled = False
        self.assertEqual(bridge.route_question('Find a weapon', '', []),
                         ('', None, 0))

    def test_openai_triage_never_executes_tools(self):
        bridge = self.bridge
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            usage=None, choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(
                    name='get_character_context', arguments='{}'))]))])
        bridge.tool_executor.execute_tool = MagicMock()
        with patch.dict(sys.modules, openai=SimpleNamespace(
                OpenAI=MagicMock(return_value=client))):
            raw, _, used = bridge.call_openai('My gear?', routing=True)
        self.assertEqual(json.loads(raw), [call('get_character_context')])
        self.assertFalse(used)
        bridge.tool_executor.execute_tool.assert_not_called()
        self.assertEqual(client.chat.completions.create.call_count, 1)
        self.assertEqual(client.chat.completions.create.call_args.kwargs[
            'tool_choice'], 'required')

    def test_non_reasoning_openai_effort_allows_temperature(self):
        bridge = LLMBridge({
            'LLMGuide.OpenAI.Model': 'gpt-5.6-luna',
            'LLMGuide.OpenAI.ReasoningEffort': 'none',
        })
        bridge.deadline = time.monotonic() + 60
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            usage=None, choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(
                    name='get_character_context', arguments='{}'))]))])
        with patch.dict(sys.modules, openai=SimpleNamespace(
                OpenAI=MagicMock(return_value=client))):
            bridge.call_openai('My gear?', routing=True)
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request['temperature'], 0)
        self.assertEqual(request['max_completion_tokens'], 600)
        self.assertEqual(request['reasoning_effort'], 'none')

    def test_anthropic_triage_never_executes_tools(self):
        bridge = self.bridge
        client = MagicMock()
        client.messages.create.return_value = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1, output_tokens=2),
            stop_reason='tool_use', content=[SimpleNamespace(
                type='tool_use', name='get_character_context', input={})])
        bridge.tool_executor.execute_tool = MagicMock()
        with patch.dict(sys.modules, anthropic=SimpleNamespace(
                Anthropic=MagicMock(return_value=client))):
            raw, tokens, used = bridge.call_anthropic('My gear?', routing=True)
        self.assertEqual(json.loads(raw), [call('get_character_context')])
        self.assertEqual(tokens, 3)
        self.assertFalse(used)
        bridge.tool_executor.execute_tool.assert_not_called()
        self.assertEqual(client.messages.create.call_count, 1)

    def test_compatible_providers_forward_routing(self):
        bridge = self.bridge
        bridge.call_openai = MagicMock(return_value=('[]', 0, False))
        for method in (
            bridge.call_google,
            bridge.call_openrouter,
            bridge.call_ollama,
        ):
            method('My gear?', routing=True)
            self.assertTrue(bridge.call_openai.call_args.kwargs['routing'])

    def test_ollama_uses_local_compatible_endpoint(self):
        bridge = LLMBridge({
            'LLMGuide.Ollama.Model': 'qwen3:8b',
            'LLMGuide.Ollama.BaseUrl': 'http://ollama:11434',
            'LLMGuide.Ollama.DisableThinking': '1',
        })
        bridge.deadline = time.monotonic() + 60
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            usage=None, choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(
                    name='get_character_context', arguments='{}'))]))])
        openai_factory = MagicMock(return_value=client)
        with patch.dict(sys.modules, openai=SimpleNamespace(
                OpenAI=openai_factory)):
            bridge.call_ollama('My gear?', routing=True)
        self.assertEqual(
            openai_factory.call_args.kwargs['base_url'],
            'http://ollama:11434/v1',
        )
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request['max_tokens'], 600)
        self.assertEqual(request['reasoning_effort'], 'none')
        self.assertIn('tools', request)
        self.assertNotIn('tool_choice', request)

    def test_ollama_final_round_omits_tools(self):
        bridge = LLMBridge({
            'LLMGuide.Ollama.Model': 'qwen3:8b',
            'LLMGuide.Ollama.BaseUrl': 'http://ollama:11434',
            'LLMGuide.Ollama.DisableThinking': '1',
            'LLMGuide.MaxToolRounds': '0',
        })
        bridge.deadline = time.monotonic() + 60
        bridge.max_tool_rounds = 0
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            usage=None, choices=[SimpleNamespace(
                finish_reason='stop',
                message=SimpleNamespace(
                    tool_calls=None, content='Hello.'
                ),
            )],
        )
        with patch.dict(sys.modules, openai=SimpleNamespace(
                OpenAI=MagicMock(return_value=client))):
            text, _, _ = bridge.call_ollama('Hello')
        self.assertEqual(text, 'Hello.')
        request = client.chat.completions.create.call_args.kwargs
        self.assertNotIn('tools', request)
        self.assertNotIn('tool_choice', request)

    def test_openai_reasoning_uses_budget_multiplier(self):
        bridge = LLMBridge({
            'LLMGuide.OpenAI.Model': 'gpt-5.6-luna',
            'LLMGuide.OpenAI.ReasoningEffort': 'medium',
            'LLMGuide.OpenAI.MaxTokensMultiplier': '4',
        })
        bridge.deadline = time.monotonic() + 60
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            usage=None, choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=[SimpleNamespace(function=SimpleNamespace(
                    name='get_character_context', arguments='{}'))]))])
        with patch.dict(sys.modules, openai=SimpleNamespace(
                OpenAI=MagicMock(return_value=client))):
            bridge.call_openai('My gear?', routing=True)
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request['max_completion_tokens'], 2400)
        self.assertEqual(request['reasoning_effort'], 'medium')
        self.assertNotIn('temperature', request)

    def test_seeded_evidence_does_not_force_duplicate_lookup(self):
        bridge = self.bridge
        bridge.tool_executor.evidence.record('Known equipment')
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            usage=None, choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=None, content='Known equipment'))])
        with patch.dict(sys.modules, openai=SimpleNamespace(
                OpenAI=MagicMock(return_value=client))):
            bridge.call_openai('My gear?')
        self.assertEqual(client.chat.completions.create.call_args.kwargs[
            'tool_choice'], 'auto')


if __name__ == '__main__':
    unittest.main()
