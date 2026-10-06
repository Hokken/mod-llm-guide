"""Readiness guards must not turn missing evidence into confident answers."""

import os
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_tools import GameToolExecutor
from llm_guide_bridge import LLMBridge


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.executor = GameToolExecutor({})

    def lookup(self, name, result, **arguments):
        with patch.object(self.executor, '_execute_tool', return_value=result):
            return self.executor.execute_tool(name, arguments)

    def test_failed_only_answer_is_safe_and_has_no_backend_details(self):
        self.lookup('find_npc', 'Error executing tool: private-db-password')
        answer = self.executor.finalize_answer('Invented confident answer', True)
        self.assertIn('could not verify', answer)
        self.assertNotIn('Invented', answer)
        self.assertNotIn('private-db-password', answer)

    def test_empty_or_ambiguous_result_blocks(self):
        for result in ('', 'No matching NPC returned',
                       'I found multiple items matching a name',
                       "Item 'Missing' not found."):
            self.executor.begin_request(None)
            self.lookup('find_npc', result)
            self.assertTrue(self.executor.readiness.blocked())

    def test_same_search_retry_clears_failure_not_other_searches(self):
        self.lookup('find_npc', 'No NPC found', npc_name='A')
        self.lookup('find_npc', 'Found [[npc:2:B]]', npc_name='B')
        self.assertTrue(self.executor.readiness.notes())
        self.lookup('find_npc', 'Found [[npc:1:A]]', npc_name='A')
        self.assertFalse(self.executor.readiness.notes())
        self.assertEqual(self.executor.finalize_answer('Found A.', True),
                         'Found A.')

    def test_travel_limitations_survive_success_and_other_lookups(self):
        self.lookup('get_flight_paths', 'Flight paths to: Stormwind')
        self.lookup('find_npc', 'Found [[npc:1:A]]')
        answer = self.executor.finalize_answer('A route option.', True)
        self.assertIn('cannot establish the fastest', answer)
        self.assertIn('unlocked', answer)
        self.assertIn('another relevant lookup', self.executor.readiness_prompt())

    def test_service_distance_gap_and_valid_distance(self):
        self.lookup('find_service_npc', 'Found [[npc:1:A]] in Darkshire')
        self.assertIn('closest', self.executor.readiness_prompt())
        self.lookup('find_service_npc', 'Found [[npc:1:A]] (~85 m north)')
        self.assertFalse(self.executor.readiness.notes())

    def test_stale_comparison_does_not_complete_another_lookup(self):
        self.executor.item_comparisons['old'] = 'Old weapon comparison'
        self.lookup('find_item_upgrades', 'Comparison candidates: none')
        self.assertTrue(self.executor.readiness.blocked())
        comparison = 'New weapon comparison. Source not found'
        self.executor.item_comparisons['new'] = comparison
        self.lookup('find_item_upgrades', comparison)
        self.assertFalse(self.executor.readiness.blocked())
        self.assertIn('Acquisition', self.executor.readiness_prompt())

    def test_state_reset_and_feature_switch(self):
        self.lookup('get_flight_paths', 'Travel options')
        self.executor.begin_request(None)
        self.assertEqual(self.executor.readiness_prompt(), '')
        bridge = LLMBridge({'LLMGuide.Readiness.Enable': '0'})
        self.assertFalse(bridge.tool_executor.readiness_enabled)
        self.executor = bridge.tool_executor
        self.lookup('get_flight_paths', 'Travel options')
        self.assertEqual(self.executor.finalize_answer('Options', True), 'Options')

    def test_invalid_arguments_are_tracked_without_execution(self):
        with patch.object(self.executor, '_execute_tool') as execute:
            self.executor.execute_tool('find_npc', None)
            execute.assert_not_called()
        self.assertTrue(self.executor.readiness.blocked())

    def test_partial_answer_still_rejects_fabricated_links(self):
        self.lookup('find_npc', 'Found [[npc:1:A]]')
        self.lookup('get_flight_paths', 'Travel options')
        with self.assertRaises(ValueError):
            self.executor.finalize_answer('[[npc:999:Invented]]', True)

    def test_openai_rechecks_before_next_answer_round(self):
        bridge = LLMBridge({})
        bridge.deadline = time.monotonic() + 60
        self.executor = bridge.tool_executor
        self.lookup('get_flight_paths', 'Travel options')
        client = MagicMock()
        client.chat.completions.create.return_value = SimpleNamespace(
            usage=None, choices=[SimpleNamespace(message=SimpleNamespace(
                tool_calls=None, content='An option'))])
        with patch.dict(sys.modules, openai=SimpleNamespace(
                OpenAI=MagicMock(return_value=client))):
            bridge.call_openai('How do I travel?')
        prompt = client.chat.completions.create.call_args.kwargs[
            'messages'][0]['content']
        self.assertIn('Answer-readiness checks', prompt)

    def test_anthropic_gets_same_readiness_checks(self):
        bridge = LLMBridge({})
        bridge.deadline = time.monotonic() + 60
        self.executor = bridge.tool_executor
        self.lookup('get_flight_paths', 'Travel options')
        client = MagicMock()
        client.messages.create.return_value = SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason='end_turn', content=[SimpleNamespace(text='An option')])
        with patch.dict(sys.modules, anthropic=SimpleNamespace(
                Anthropic=MagicMock(return_value=client))):
            bridge.call_anthropic(
                'How do I travel?', bridge.build_system_prompt('Hunter', {}))
        system = client.messages.create.call_args.kwargs['system']
        self.assertEqual(system[0]['text'], bridge.static_system_prompt())
        self.assertEqual(system[0]['cache_control'], {'type': 'ephemeral'})
        self.assertNotIn('cache_control', system[1])
        self.assertIn('Hunter', system[1]['text'])
        self.assertIn('Answer-readiness checks', system[1]['text'])

    def test_static_prompt_prefix_excludes_player_data(self):
        bridge = LLMBridge({})
        prompt = bridge.build_system_prompt(
            'Karaez. Gold: 12g', {'older_topics': ['vendor lookup']})
        static = bridge.static_system_prompt()
        self.assertTrue(prompt.startswith(static))
        self.assertIn('ACTUAL game database', static)
        self.assertNotIn('Karaez', static)
        self.assertNotIn('vendor lookup', static)

    def test_unsold_exact_item_is_a_usable_negative_answer(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [], [dict(entry=2842, name='Silver Bar', Quality=1, sold=0)]]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        self.executor.get_connection = MagicMock(return_value=connection)
        self.executor._creature_entry_col = 'id1'
        result = self.executor.execute_tool(
            'find_vendor', {'item_type': 'Silver Bar', 'zone': 'Ironforge'})
        self.assertIn('no NPC vendor sells [[item:2842:Silver Bar:1]]',
                      result)
        self.assertFalse(self.executor.readiness.blocked())

    def test_item_sold_elsewhere_keeps_unresolved_vendor_result(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [], [dict(entry=2840, name='Copper Bar', Quality=1, sold=1)]]
        connection = MagicMock()
        connection.cursor.return_value = cursor
        self.executor.get_connection = MagicMock(return_value=connection)
        self.executor._creature_entry_col = 'id1'
        result = self.executor.execute_tool(
            'find_vendor', {'item_type': 'Copper Bar', 'zone': 'Ironforge'})
        self.assertTrue(result.startswith('No vendors'))
        self.assertTrue(self.executor.readiness.blocked())


if __name__ == '__main__':
    unittest.main()
