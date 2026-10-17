"""Regression coverage for request recovery and factual guide contracts."""

import json
import os
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_tools import GAME_TOOLS, GameToolExecutor
from guide_item_comparison import item_stats, meets_requirements, stat_deltas
from guide_reliability import (
    EvidenceLedger, decode_snapshot, requires_evidence, validate_arguments,
)
from llm_guide_bridge import LLMBridge


def snapshot(**changes):
    data = dict(version='1', level='40', race_mask='1', class_mask='1',
                captured_at='1', skills={'293': '1', '43': '100'},
                reputation={}, equipment={'0': '100'},
                eligible_quest_ids=['1', '2'], known_spells=['200'])
    data.update(changes)
    return decode_snapshot(json.dumps(data))


class SnapshotTests(unittest.TestCase):
    def test_full_context_and_empty_collections(self):
        data = snapshot(summary='equipment ' * 100, skills='', equipment='',
                        eligible_quest_ids='', known_spells='')
        self.assertGreater(len(data['summary']), 500)
        self.assertEqual(data['skills'], {})
        self.assertEqual(data['eligible_quest_ids'], [])
        self.assertEqual(data['level'], 40)

    def test_legacy_and_invalid_contracts(self):
        self.assertIsNone(decode_snapshot(None))
        for raw in ('{', '[]', '{"version": 2}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                decode_snapshot(raw)


class EvidenceTests(unittest.TestCase):
    def test_verified_link_presentation_is_canonicalized(self):
        executor = GameToolExecutor({})
        quest = "[[quest:12:Sven's Revenge:25]]"
        item = '[[item:13:Known Blade:3]]'
        executor.evidence.record(quest + ' ' + item)
        for variant in ("[[quest:12:sven’s revenge]]",
                        "[[quest:12: Sven's  Revenge :99]]"):
            self.assertEqual(executor.finalize_answer(variant, True), quest)
        self.assertEqual(executor.finalize_answer(
            '[[item:13:Known Blade:4]]', True), item)

    def test_link_repair_never_changes_identity_or_guesses(self):
        executor = GameToolExecutor({})
        executor.evidence.record('[[quest:12:Known:25]]')
        for variant in ('[[quest:13:Known:25]]', '[[quest:12:Wrong:25]]',
                        '[[npc:12:Known]]', '|Hquest:12|h[Known]|h',
                        '[[quest:12:Known'):
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                executor.finalize_answer(variant, True)
        executor.evidence.record('[[quest:12:Known:26]]')
        with self.assertRaises(ValueError):
            executor.finalize_answer('[[quest:12:known]]', True)

    def test_flight_lookup_no_longer_receives_zone(self):
        executor = GameToolExecutor({})
        executor.set_player_zone('duskwood')
        executor.default_faction = 'alliance'
        executor._get_flight_paths = MagicMock(return_value='Route found')
        arguments = dict(from_location='Darkshire',
                         to_location='Redridge Mountains')
        result = executor.execute_tool('get_flight_paths', arguments)
        self.assertEqual(result, 'Route found')
        executor._get_flight_paths.assert_called_once_with(
            dict(arguments, faction='alliance'))
        self.assertNotIn('faction', arguments)
        result = executor.execute_tool('get_flight_paths',
                                       dict(arguments, zone='duskwood'))
        self.assertIn('Unknown argument: zone', result)
        self.assertEqual(executor._get_flight_paths.call_count, 1)

    def test_injected_defaults_match_every_tool_schema(self):
        executor = GameToolExecutor({})
        executor.set_player_zone('duskwood')
        executor.set_player_defaults(24, 'hunter', 'alliance')
        executor.active_quest_ids = [1]
        for tool in GAME_TOOLS:
            with self.subTest(tool=tool['name']):
                with patch('game_tools.validate_arguments',
                           return_value='inspection complete') as validate:
                    executor.execute_tool(tool['name'], {})
                schema, arguments = validate.call_args.args
                self.assertFalse(set(arguments) - set(schema['properties']))

    def test_item_mentions_linked_without_nested_or_partial_links(self):
        ledger = EvidenceLedger()
        ring = "[[item:1:Silverlaine's Family Seal:3]]"
        cloak = "[[item:2:Fenrus' Hide:3]]"
        ledger.record(ring + ' ' + cloak)
        answer = ("Ring: Silverlaine's Family Seal. Back: [Fenrus' Hide]. "
                  + ring + ' Fenrus\' Hidebound')
        linked = ledger.link_item_mentions(answer)
        self.assertEqual(linked, 'Ring: ' + ring + '. Back: ' + cloak +
                         '. ' + ring + " Fenrus' Hidebound")
        ledger.validate(linked, True)

    def test_ambiguous_and_unverified_names_not_linked(self):
        ledger = EvidenceLedger()
        ledger.record('[[item:1:Shared Name:2]] [[item:2:Shared Name:3]]')
        self.assertEqual(ledger.link_item_mentions('Shared Name or Unknown'),
                         'Shared Name or Unknown')

    def test_other_entity_markers_are_not_modified(self):
        ledger = EvidenceLedger()
        ledger.record('[[item:1:Known:2]] [[quest:2:Known:10]]')
        self.assertEqual(ledger.link_item_mentions('[[quest:2:Known:10]]'),
                         '[[quest:2:Known:10]]')

    def test_sources_preserved_for_mentioned_candidates_only(self):
        executor = GameToolExecutor({})
        executor.append_comparison_details = True
        marker = '[[item:1:Candidate:2]]'
        note = marker + ': +5 Agility. Source not found.'
        executor.evidence.record(note)
        executor.item_comparisons[marker] = note
        self.assertEqual(executor.finalize_answer('No recommendation.', True),
                         'No recommendation.')
        answer = executor.finalize_answer('Consider Candidate.', True)
        self.assertIn('Source not found.', answer)
        self.assertIn('access and affordability unverified', answer)
        self.assertNotIn('pet scaling are not evaluated', answer)
        executor.begin_request(snapshot())
        self.assertEqual(executor.item_comparisons, {})

    def test_finalization_does_not_repair_unverified_markers(self):
        executor = GameToolExecutor({})
        executor.evidence.record('[[item:1:Known:2]]')
        with self.assertRaises(ValueError):
            executor.finalize_answer('[[item:99:Known:2]]', True)

    def test_failed_tools_do_not_count_as_evidence(self):
        ledger = EvidenceLedger()
        ledger.record('Error executing tool: database unavailable')
        ledger.record('Invalid tool arguments: missing item')
        with self.assertRaises(ValueError):
            ledger.validate('Hogger drops it.', True)

    def test_no_match_is_evidence_but_invented_links_are_rejected(self):
        ledger = EvidenceLedger()
        ledger.record('No matching items found.')
        ledger.validate('No matching items were found.', True)
        with self.assertRaises(ValueError):
            ledger.validate('Try [[item:99:Invented:4]].', True)

    def test_exact_returned_names_and_quality_are_required(self):
        ledger = EvidenceLedger()
        ledger.record('[[item:12:Known:2]]')
        ledger.validate('Try [[item:12:Known:2]].', True)
        for response in ('[[item:12:Fake:2]]', '[[item:12:Known:4]]',
                         '|Hitem:12|h[Known]|h', ''):
            with self.subTest(response=response), self.assertRaises(ValueError):
                ledger.validate(response, True)

    def test_social_exception_is_narrow(self):
        self.assertFalse(requires_evidence('Thanks!'))
        self.assertTrue(requires_evidence('Thanks, where is the trainer?'))

    def test_malformed_input_never_runs_a_lookup(self):
        executor = GameToolExecutor({})
        executor._find_npc = MagicMock()
        for args in (None, [], {'npc_name': 123}, {'npc_name': 'A', 'sql': 'x'}):
            result = executor.execute_tool('find_npc', args)
            self.assertTrue(result.startswith('Invalid tool arguments:'))
        executor._find_npc.assert_not_called()

    def test_array_members_and_booleans_are_checked(self):
        schema = dict(properties={'ids': dict(type='array',
                                              items=dict(type='integer'))})
        self.assertIsNone(validate_arguments(schema, {'ids': [1, 2]}))
        self.assertIsNotNone(validate_arguments(schema, {'ids': [True]}))
        self.assertIsNotNone(validate_arguments(schema, {'ids': [{}]}))

    def test_player_evidence_is_reset_between_requests(self):
        executor = GameToolExecutor({})
        executor.evidence.record('[[item:1:Private:2]]')
        executor.begin_request(snapshot())
        self.assertFalse(executor.evidence.results)


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.bridge = LLMBridge({})
        self.cursor = MagicMock(rowcount=1)

    def test_claim_is_conditional_and_has_unique_lease(self):
        self.assertTrue(self.bridge.mark_processing(self.cursor, 10))
        first = self.bridge.lease_token
        self.bridge.mark_processing(self.cursor, 11)
        self.assertNotEqual(first, self.bridge.lease_token)
        query, args = self.cursor.execute.call_args.args
        self.assertIn("status = 'pending'", query)
        self.assertEqual(args[-1], 11)

    def test_cancelled_or_expired_completion_is_not_published(self):
        self.bridge.lease_token = 'owned-lease'
        self.cursor.rowcount = 0
        self.assertFalse(self.bridge.save_response(self.cursor, 10, 'answer'))
        query, args = self.cursor.execute.call_args.args
        self.assertIn("status = 'processing'", query)
        self.assertIn('lease_until >= NOW()', query)
        self.assertEqual(args[-1], 'owned-lease')

    def test_no_memory_after_lost_claim(self):
        bridge = self.bridge
        bridge.mark_processing = MagicMock(return_value=False)
        bridge.call_llm = MagicMock()
        bridge.store_memory = MagicMock()
        bridge.process_request(self.cursor,
                               (1, 2, 'Name', '', 'hello', 0, 0, 0, '', None))
        bridge.call_llm.assert_not_called()
        bridge.store_memory.assert_not_called()

    def test_deadline_bounds_calls(self):
        self.bridge.deadline = time.monotonic() + 2
        self.assertLessEqual(self.bridge.remaining_timeout(), 2)
        self.bridge.deadline = time.monotonic() - 1
        with self.assertRaises(TimeoutError):
            self.bridge.remaining_timeout()

    def test_abandoned_leases_have_bounded_recovery(self):
        self.bridge.fetch_pending_requests(self.cursor)
        query, args = self.cursor.execute.call_args_list[0].args
        self.assertIn("IF(attempts < %s, 'pending', 'error')", query)
        self.assertIn('lease_until < NOW()', query)
        self.assertEqual(args, (self.bridge.max_attempts,))

    def test_transient_retry_and_permanent_error(self):
        self.bridge.deadline = time.monotonic() + 60
        transient = RuntimeError('busy')
        transient.status_code = 429
        call = MagicMock(side_effect=[transient, 'answer'])
        with patch('llm_guide_bridge.time.sleep') as sleep:
            self.assertEqual(self.bridge.provider_call(call), 'answer')
            sleep.assert_called_once()
        permanent = RuntimeError('bad credentials')
        permanent.status_code = 401
        call = MagicMock(side_effect=permanent)
        with self.assertRaises(RuntimeError):
            self.bridge.provider_call(call)
        self.assertEqual(call.call_count, 1)

    def test_anthropic_final_round_has_no_tools(self):
        bridge = self.bridge
        bridge.deadline = time.monotonic() + 60
        bridge.max_tool_rounds = 1
        usage = SimpleNamespace(input_tokens=1, output_tokens=1)
        client = MagicMock()
        client.messages.create.side_effect = [
            SimpleNamespace(usage=usage, stop_reason='tool_use', content=[
                SimpleNamespace(type='tool_use', name='get_character_context',
                                input={}, id='tool-1')]),
            SimpleNamespace(usage=usage, stop_reason='end_turn', content=[
                SimpleNamespace(text='You are a warrior.')]),
        ]
        module = SimpleNamespace(Anthropic=MagicMock(return_value=client))
        bridge.tool_executor.execute_tool = MagicMock(return_value='warrior')
        with patch.dict(sys.modules, anthropic=module):
            text, _, used = bridge.call_anthropic('What class am I?')
        self.assertTrue(used)
        self.assertIn('warrior', text)
        calls = client.messages.create.call_args_list
        self.assertEqual(calls[0].kwargs['tool_choice'], {'type': 'any'})
        self.assertNotIn('tools', calls[1].kwargs)

    def test_provider_forces_lookup_then_final_answer(self):
        bridge = self.bridge
        bridge.max_tool_rounds = 1
        bridge.deadline = time.monotonic() + 60
        call = SimpleNamespace(id='x', function=SimpleNamespace(
            name='find_npc', arguments='{"npc_name":"A"}'))
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(tool_calls=[call]))]),
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(tool_calls=None, content='Found A'))]),
        ]
        module = SimpleNamespace(OpenAI=MagicMock(return_value=client))
        bridge.tool_executor.execute_tool = MagicMock(return_value='NPC A')
        with patch.dict(sys.modules, openai=module):
            answer, _, used = bridge.call_openai('Where is A?')
        self.assertEqual(answer, 'Found A')
        self.assertTrue(used)
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(calls[0].kwargs['tool_choice'], 'required')
        self.assertEqual(calls[1].kwargs['tool_choice'], 'none')


class ItemTests(unittest.TestCase):
    def test_comparison_carries_baseline_requirements_and_sources(self):
        executor = GameToolExecutor({})
        executor.append_comparison_details = True
        executor.begin_request(snapshot())
        current = dict(entry=100, name='Old Sword', Quality=2, ItemLevel=40,
                       InventoryType=13, RequiredLevel=30)
        candidate = dict(entry=101, name='New Sword', Quality=3, ItemLevel=45,
                         InventoryType=13, RequiredLevel=35, subclass=7,
                         stat_type1=4, stat_value1=5, **{'class': 2})
        connection, cursor = MagicMock(), MagicMock()
        connection.cursor.return_value = cursor
        cursor.fetchone.return_value = current
        cursor.fetchall.return_value = [candidate]
        executor.get_connection = MagicMock(return_value=connection)
        executor._search_item_candidates = MagicMock(return_value=[current])
        executor._comparison_sources = MagicMock(
            return_value='Source leads: Loot [[npc:99:Boss]]')
        result = executor.execute_tool('find_item_upgrades', dict(
            current_item='Old Sword', role='melee'))
        self.assertIn('requires level 35', result)
        self.assertIn('versus [[item:100:Old Sword:2]]', result)
        answer = executor.finalize_answer('Consider New Sword.', True)
        self.assertIn('Loot [[npc:99:Boss]]', answer)
        self.assertIn('+5 Strength', answer)
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_answer_rules_apply_with_custom_system_prompt(self):
        bridge = LLMBridge({})
        bridge.system_prompt = 'Custom persona.'
        prompt = bridge.build_system_prompt('Hunter', {})
        self.assertIn('Custom persona.', prompt)
        self.assertIn('rings are not trinkets', prompt)
        self.assertIn('riding is a travel skill', prompt)
        self.assertIn('acquisition', prompt)
        self.assertIn('infer pet scaling', prompt)

    def test_all_stats_including_mana_and_losses(self):
        current = dict(stat_type1=4, stat_value1=10)
        candidate = dict(stat_type10=5, stat_value10=20,
                         stat_type1=0, stat_value1=50)
        self.assertEqual(item_stats(candidate), {5: 20, 0: 50})
        delta = stat_deltas(current, candidate)
        self.assertIn('-10 Strength', delta)
        self.assertIn('+20 Intellect', delta)
        self.assertIn('+50 Mana', delta)

    def test_proficiency_race_spell_and_reputation(self):
        item = {'class': 4, 'subclass': 4, 'RequiredLevel': 40}
        self.assertTrue(meets_requirements(item, snapshot()))
        for fields in ({'AllowableRace': 2}, {'RequiredLevel': 41},
                       {'requiredspell': 999}, {'RequiredSkill': 999},
                       {'FlagsExtra': 1}, {'HolidayId': 1},
                       {'RequiredReputationFaction': 99,
                        'RequiredReputationRank': 5}):
            with self.subTest(fields=fields):
                self.assertFalse(meets_requirements(dict(item, **fields), snapshot()))
        self.assertFalse(meets_requirements(item, snapshot(skills={})))


class QuestTests(unittest.TestCase):
    def test_server_eligibility_is_applied_before_limit_and_objects_supported(self):
        executor = GameToolExecutor({})
        executor.begin_request(snapshot())
        connection, cursor = MagicMock(), MagicMock()
        connection.cursor.return_value = cursor
        cursor.fetchall.return_value = [dict(ID=1, LogTitle='Test', QuestLevel=1,
            MinLevel=1, npc_entry=3, npc_name='Tablet', source_type='object')]
        executor.get_connection = MagicMock(return_value=connection)
        executor._creature_entry_column = MagicMock(return_value='id')
        result = executor._get_available_quests(dict(zone='elwynn forest',
                                                   player_level=40))
        query, args = cursor.execute.call_args.args
        self.assertIn('gameobject_queststarter', query)
        self.assertLess(query.index('qt.ID IN ('), query.index('LIMIT 20'))
        self.assertEqual(args[-2:], (1, 2))
        self.assertIn('Tablet (object)', result)
        self.assertNotIn('[[npc:3:', result)


if __name__ == '__main__':
    unittest.main()
