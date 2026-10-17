"""Opt-in real-provider contracts; synthetic history, no database writes.

Set GUIDE_TEST_PROVIDER_CONFIG to an existing bridge config. Uses real API
requests which may incur cloud charges. Never runs by default or prints
credentials.
"""
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_guide_bridge import LLMBridge, load_config
from guide_conversation import CONTEXT_PROMPT, parse_context, conversation_view
from guide_routing import ROUTING_PROMPT, validate_plan
from game_tools import GAME_TOOLS


@unittest.skipUnless(os.getenv('GUIDE_TEST_PROVIDER_CONFIG'), 'Opt-in paid provider tests')
class LiveProviderTests(unittest.TestCase):
    def setUp(self):
        self.bridge = LLMBridge(load_config(os.environ['GUIDE_TEST_PROVIDER_CONFIG']))
        self.bridge.deadline = time.monotonic() + self.bridge.request_timeout

    def tearDown(self):
        for client in self.bridge.api_clients:
            client.close()

    def resolve(self, question, previous_question, previous_answer):
        history = [{'question': previous_question, 'response': previous_answer}]
        raw, _, _ = self.bridge.call_llm(question, CONTEXT_PROMPT + '\nData:\n' +
            json.dumps(conversation_view(history)) +
            '\nCurrent player: level 24 hunter in Redridge Mountains. Alliance.',
            routing='context')
        return parse_context(raw)

    def test_full_tool_catalog_is_accepted(self):
        raw, _, _ = self.bridge.call_llm('Show details for quest ID 141.',
                                       ROUTING_PROMPT, routing=True)
        plan = validate_plan(raw, GAME_TOOLS, self.bridge.routing_max_calls)
        self.assertTrue(any(c['tool_name'] == 'get_quest_info' for c in plan))

    def test_compact_answers_across_topics(self):
        cases = [
            ('Where is the flight master?',
             '[[npc:931:Ariena Stormfeather]] in Redridge Mountains, '
             '~182 m southeast at 30.6, 59.4.'),
            ('Where do I turn in my quest?',
             'Turn in [[quest:141:The Defias Brotherhood:18]] to '
             '[[npc:234:Gryan Stoutmantle]] in Westfall.'),
            ('Any bow upgrade for me?',
             '[[item:1:Test Bow:2]] versus Hunting Bow: +1 Agility, '
             '+2 weapon DPS. Source unknown. Base-stat comparison only.'),
        ]
        for question, result in cases:
            with self.subTest(question=question):
                self.bridge.tool_executor.begin_request(None)
                self.bridge.tool_executor.evidence.record(result)
                prompt = self.bridge.build_system_prompt('', {}) + '\nTool evidence: ' + result
                with patch.object(self.bridge.tool_executor, '_execute_tool', return_value=result):
                    answer, _, _ = self.bridge.call_llm(question, prompt)
                answer = self.bridge.tool_executor.finalize_answer(answer, True)
                self.assertLessEqual(len(answer.split()), 100)
                self.assertNotIn('Comparison checks', answer)

    def test_upgrade_omits_internal_caveat_boilerplate(self):
        self.bridge.tool_executor.begin_request({'summary': 'A hunter with a bow.'})
        result = ('The player is a level 24 hunter using Hunting Bow. '
                  'Verified comparison: [[item:1:Test Bow:2]] meets equip '
                  'requirements and gives +1 Agility and +2 weapon DPS '
                  'versus Hunting Bow. No measured stat losses. Source unknown. Internal limits: '
                  'enchants, gems, procs and pet scaling are not evaluated.')
        self.bridge.tool_executor.evidence.record(result)
        prompt = self.bridge.build_system_prompt('', {}) + '\nTool data: ' + result
        with patch.object(self.bridge.tool_executor, '_execute_tool', return_value=result):
            answer, _, _ = self.bridge.call_llm('Summarize this bow upgrade option.', prompt,
                memories_recent=[{'question': 'Any bow upgrades?', 'response':
                    '[[item:1:Test Bow:2]] (+1 Agility, +2 weapon DPS) is an option. '
                    'Base stats only; enchants, gems and pet scaling not evaluated. '
                    'Some acquisition sources are unverified.'}])
        answer = self.bridge.tool_executor.finalize_answer(answer, True)
        for phrase in ('enchants', 'gems', 'pet scaling', 'not evaluated', 'base stats only'):
            self.assertNotIn(phrase, answer.lower())
        self.assertIn('source', answer.lower())

    def test_crafting_constraint_is_not_silently_replaced(self):
        state = self.resolve('What about crafted bows?',
                             'Which bows would upgrade my Hunting Bow?',
                             'We compared bow upgrades.')
        self.assertEqual(state['status'], 'unsupported')
        self.assertIn('craft', (state['request'] + state['constraints']).lower())

    def test_quest_followup_preserves_stage(self):
        state = self.resolve('Where do I turn it in?', 'Which stage am I on?',
                            'You are on [[quest:141:The Defias Brotherhood:18]].')
        self.assertEqual(state['status'], 'ready')
        self.assertIn('141', state['request'])

    def test_clarification_reply_preserves_goal(self):
        state = self.resolve('Stormwind', 'Where can I find a banker?',
                            'Which city do you mean?')
        self.assertEqual(state['status'], 'ready')
        self.assertIn('bank', state['request'].lower())
        self.assertIn('stormwind', state['request'].lower())

    def test_topic_switch_drops_old_goal(self):
        state = self.resolve('Where is the nearest innkeeper?',
                            'Which crafted bows can I use?', 'Crafting is not covered.')
        self.assertEqual(state['status'], 'ready')
        self.assertNotIn('bow', state['request'].lower())

    def test_full_quest_followup_answer_path(self):
        bridge = self.bridge
        history = [{'question': 'Which stage am I on?',
                    'response': '[[quest:141:The Defias Brotherhood:18]] is active.'}]
        result = ('Quest [[quest:141:The Defias Brotherhood:18]] is active. '
                  'Turn in to [[npc:234:Gryan Stoutmantle]] in Westfall. '
                  'This fixture contains no coordinates or distance.')
        bridge.tool_executor.set_active_quest_ids([141])
        bridge.tool_executor.set_player_zone('westfall')
        with patch.object(bridge.tool_executor, '_execute_tool', return_value=result):
            context, clarification, _ = bridge.route_question(
                'Where do I turn it in?', 'Level 24 hunter in Westfall.', history)
            self.assertIsNone(clarification)
            answer, _, _ = bridge.call_llm('Where do I turn it in?',
                'Answer using only the supplied tool results. ' + context,
                memories_recent=history)
        answer = bridge.tool_executor.finalize_answer(answer, True)
        self.assertIn('Gryan', answer)


if __name__ == '__main__':
    unittest.main()
