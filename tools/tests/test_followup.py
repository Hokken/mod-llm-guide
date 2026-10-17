"""Shared historical reference verification, isolated from factual evidence."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_tools import GameToolExecutor
from guide_followup import lookup_identity, reverify_followup, UNRESOLVED


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.executor = GameToolExecutor({})
        self.deadline = MagicMock()

    def verify(self, answer, history, limit=8):
        return reverify_followup(answer, [{'response': history}], self.executor,
                                 self.deadline, limit)

    def test_all_kinds_reverified_and_metadata_canonicalized(self):
        for old, new in (
                ('[[npc:931:Ariena Stormfeather]]',
                 '[[npc:931:Ariena Stormfeather]]'),
                ('[[item:1:Blade:4]]', '[[item:1:Blade:2]]'),
                ('[[quest:2:Quest:99]]', '[[quest:2:Quest:12]]'),
                ('[[spell:3:Spell]]', '[[spell:3:Spell]]')):
            with self.subTest(old=old):
                self.executor.begin_request(None)
                with patch('guide_followup.lookup_identity', return_value=new):
                    answer, clarification = self.verify(old, old)
                self.assertEqual(answer, new)
                self.assertFalse(clarification)
                self.assertEqual(self.executor.evidence.results, [])
                with self.assertRaises(ValueError):
                    self.executor.evidence.validate(answer, True)

    def test_actual_flight_followup_keeps_facts_and_reverifies_npc(self):
        self.executor.evidence.record('Travel from Lakeshire: limited routes')
        marker = '[[npc:931:Ariena Stormfeather]]'
        with patch('guide_followup.lookup_identity', return_value=marker) as lookup:
            answer, _ = self.verify('From ' + marker, marker)
        lookup.assert_called_once_with(self.executor, 'npc', 931)
        self.executor.finalize_answer(answer, True)

    def test_duplicates_checked_once_and_current_evidence_skipped(self):
        marker = '[[npc:931:Ariena Stormfeather]]'
        with patch('guide_followup.lookup_identity', return_value=marker) as lookup:
            self.verify(marker + marker, marker)
            self.assertEqual(lookup.call_count, 1)
            self.verify(marker, marker)
            self.assertEqual(lookup.call_count, 1)

    def test_missing_renamed_or_failed_lookup_clarifies(self):
        marker = '[[npc:1:Old Name]]'
        for result in (None, '[[npc:1:New Name]]', '[[npc:2:Old Name]]'):
            with patch('guide_followup.lookup_identity', return_value=result):
                self.assertEqual(self.verify(marker, marker), (UNRESOLVED, True))
        with patch('guide_followup.lookup_identity', side_effect=RuntimeError(
                'private backend details')):
            answer, clarification = self.verify(marker, marker)
        self.assertTrue(clarification)
        self.assertNotIn('private', answer)
        self.assertEqual(self.executor.evidence.markers, set())

    def test_unknown_or_wrong_identity_is_not_accepted(self):
        for answer in ('[[npc:99:Invented]]', '[[item:1:Old Name:2]]',
                       '[[npc:1:Wrong Name]]'):
            with patch('guide_followup.lookup_identity', return_value=None) as lookup:
                response, clarification = self.verify(answer, '[[npc:1:Old Name]]')
            lookup.assert_called_once()
            self.assertTrue(clarification)
            self.assertEqual(response, UNRESOLVED)

    def test_plain_text_stage_reference_is_verified(self):
        marker = '[[quest:141:The Defias Brotherhood:18]]'
        with patch('guide_followup.lookup_identity', return_value=marker):
            answer, clarification = self.verify(marker, 'Quest 141 is a stage.')
        self.assertFalse(clarification)
        self.assertEqual(answer, marker)
        self.assertFalse(self.executor.evidence.results)

    def test_budget_and_deadline(self):
        marker = '[[npc:1:A]]'
        with patch('guide_followup.lookup_identity') as lookup:
            self.assertEqual(self.verify(marker, marker, limit=0),
                             (UNRESOLVED, True))
            lookup.assert_not_called()
        self.deadline.side_effect = TimeoutError('deadline')
        with self.assertRaises(TimeoutError):
            self.verify(marker, marker)

    def test_state_does_not_leak_between_requests(self):
        marker = '[[npc:1:A]]'
        with patch('guide_followup.lookup_identity', return_value=marker):
            self.verify(marker, marker)
        self.executor.begin_request(None)
        self.assertEqual(self.executor.evidence.markers, set())

    def test_exact_database_queries_and_cleanup(self):
        connection, cursor = MagicMock(), MagicMock()
        connection.cursor.return_value = cursor
        self.executor.get_connection = MagicMock(return_value=connection)
        for kind, row, expected in (
                ('npc', {'name': 'A'}, '[[npc:1:A]]'),
                ('item', {'name': 'A', 'Quality': 3}, '[[item:1:A:3]]'),
                ('quest', {'name': 'A', 'QuestLevel': 20}, '[[quest:1:A:20]]')):
            cursor.fetchone.return_value = row
            self.assertEqual(lookup_identity(self.executor, kind, 1), expected)
            query, arguments = cursor.execute.call_args.args
            self.assertNotIn('LIKE', query)
            self.assertEqual(arguments, (1,))
        self.assertEqual(cursor.close.call_count, 3)
        self.assertEqual(connection.close.call_count, 3)
        cursor.execute.side_effect = RuntimeError('database unavailable')
        with self.assertRaises(RuntimeError):
            lookup_identity(self.executor, 'npc', 1)
        self.assertEqual(cursor.close.call_count, 4)
        self.assertEqual(connection.close.call_count, 4)

    def test_spell_catalog_does_not_guess_unknown_ids(self):
        with patch('guide_followup.SPELL_NAMES', {123: 'Known Spell'}):
            self.assertEqual(lookup_identity(self.executor, 'spell', 123),
                             '[[spell:123:Known Spell]]')
            self.assertIsNone(lookup_identity(self.executor, 'spell', 999))


if __name__ == '__main__':
    unittest.main()
