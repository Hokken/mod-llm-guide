"""Provider-independent conversation state and export contracts."""
import json
import os
import sys
import time
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_tools import GAME_TOOLS
from guide_conversation import encode_context, decode_context, parse_context
from guide_reliability import validate_arguments
from llm_guide_bridge import (
    LLMBridge, GAME_TOOLS_PROVIDER, ROUTING_TOOLS, CONTEXT_TOOLS,
    GAME_TOOLS_OPENAI,
)


class ConversationTests(unittest.TestCase):
    def test_compact_answers_do_not_append_comparison_dump(self):
        bridge = LLMBridge({})
        executor = bridge.tool_executor
        marker = '[[item:1:Bow:2]]'
        executor.evidence.record(marker)
        executor.item_comparisons[marker] = marker + ' Full diagnostic details.'
        answer = executor.finalize_answer('Consider ' + marker + '.', True)
        self.assertNotIn('Full diagnostic', answer)
        self.assertNotIn('Comparison checks', answer)
        self.assertNotIn('Base-stat', answer)
        self.assertEqual(answer, 'Consider ' + marker + '.')
        self.assertIn('60 words', bridge.build_system_prompt('', {}))

    def test_compact_source_warning_is_not_repeated(self):
        bridge = LLMBridge({})
        executor = bridge.tool_executor
        executor.readiness.checks['test'] = (True, ['Acquisition sources are unverified.'])
        answer = 'Ranger Bow is an option; source unknown.'
        self.assertEqual(executor.readiness.finalize(answer), answer)

    def test_all_exports_are_portable_without_weakening_local_checks(self):
        for tool in GAME_TOOLS_PROVIDER + ROUTING_TOOLS + CONTEXT_TOOLS:
            self.assertEqual(tool['input_schema']['type'], 'object')
            self.assertFalse({'anyOf', 'oneOf', 'allOf'} &
                             set(tool['input_schema']))
        for tool in GAME_TOOLS_OPENAI:
            self.assertNotIn('anyOf', tool['function']['parameters'])
        schema = next(t['input_schema'] for t in GAME_TOOLS
                      if t['name'] == 'get_quest_info')
        self.assertIsNotNone(validate_arguments(schema, {}))
        self.assertIsNone(validate_arguments(schema, {'quest_id': 141}))

    def test_context_round_trip_and_oversize_fallback(self):
        state = dict(request='Which crafted bows could improve my gear?',
                     topic='upgrades', constraints='crafted only',
                     status='ready', question='')
        self.assertEqual(decode_context(encode_context(state, 'legacy')), state)
        self.assertIsNone(decode_context('Q: older question | A: answer'))
        state['request'] = 'x' * 1000
        self.assertEqual(encode_context(state, 'legacy'), 'legacy')

    def test_resolved_question_reaches_router_and_answer_context(self):
        bridge = LLMBridge({})
        bridge.deadline = time.monotonic() + 60
        state = dict(request='Where do I turn in quest 141?', topic='quest',
                     constraints='', status='ready', question='')
        bridge.call_llm = MagicMock(side_effect=[
            (json.dumps([dict(tool_name='resolve_request', tool_input=state)]), 4, False),
            (json.dumps([dict(tool_name='get_quest_info', tool_input={'quest_id': 141})]), 5, False)])
        bridge.tool_executor.execute_tool = MagicMock(return_value='Quest details')
        context, clarification, tokens = bridge.route_question('Where do I turn it in?', '',
            [{'question': 'My quest?', 'response': '[[quest:141:Quest:18]]'}])
        self.assertEqual(bridge.call_llm.call_args_list[1].args[0], state['request'])
        self.assertIn(state['request'], context)
        self.assertEqual(tokens, 9)
        self.assertIsNone(clarification)

    def test_unsupported_or_ambiguous_never_executes_game_tools(self):
        for status in ('unsupported', 'clarify'):
            bridge = LLMBridge({})
            state = dict(request='Crafted bows', topic='upgrades',
                         constraints='crafted', status=status,
                         question='Crafted-item discovery is unavailable.')
            bridge.call_llm = MagicMock(return_value=(json.dumps([
                dict(tool_name='resolve_request', tool_input=state)]), 3, False))
            bridge.tool_executor.execute_tool = MagicMock()
            _, message, _ = bridge.route_question('What about crafted ones?', '',
                [{'question': 'Bow upgrades?', 'response': 'A bow.'}])
            self.assertEqual(message, state['question'])
            bridge.tool_executor.execute_tool.assert_not_called()

    def test_malformed_context_is_rejected(self):
        for raw in ('[]', '{}', '[{"tool_name":"find_npc"}]'):
            with self.assertRaises(ValueError):
                parse_context(raw)


if __name__ == '__main__':
    unittest.main()
