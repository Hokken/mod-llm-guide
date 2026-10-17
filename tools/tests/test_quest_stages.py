"""Exact quest stages and trusted active-log IDs, independent of titles."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_tools import GAME_TOOLS, GameToolExecutor
from guide_reliability import validate_arguments


class QuestStageTests(unittest.TestCase):
    def setUp(self):
        self.executor = GameToolExecutor({})
        self.executor.set_active_quest_ids([141])
        self.connection, self.cursor = MagicMock(), MagicMock()
        self.connection.cursor.return_value = self.cursor
        self.executor.get_connection = MagicMock(return_value=self.connection)
        self.executor._creature_entry_column = MagicMock(return_value='id')

    def test_exact_id_and_name_are_alternatives(self):
        for name in ('get_quest_info', 'get_quest_chain'):
            schema = next(t['input_schema'] for t in GAME_TOOLS if t['name'] == name)
            for arguments in ({'quest_id': 141}, {'quest_name': 'The Defias Brotherhood'}):
                self.assertIsNone(validate_arguments(schema, arguments))
            for arguments in ({}, {'quest_id': -1}, {'quest_id': True},
                              {'quest_id': '141'}, {'active_quest_ids': [141]}):
                self.assertIsNotNone(validate_arguments(schema, arguments))

    def test_info_uses_exact_id_and_prioritizes_active_before_limit(self):
        self.cursor.fetchall.return_value = []
        self.executor._get_quest_info({'quest_id': 141, 'quest_name': 'ignored'})
        query, arguments = self.cursor.execute.call_args.args
        self.assertIn('WHERE qt.ID = %s', query)
        self.assertNotIn('LIKE', query)
        self.assertEqual(arguments, (141, 141))
        self.assertLess(query.index('ORDER BY qt.ID IN'), query.index('LIMIT 5'))

    def test_chain_selects_active_stage_even_if_not_in_forward_chain(self):
        stage = dict(ID=141, LogTitle='The Defias Brotherhood', QuestLevel=18,
                     MinLevel=14, RewardNextQuest=0, PrevQuestID=0)
        self.cursor.fetchall.return_value = [stage]
        self.cursor.fetchone.side_effect = [stage, stage, dict(stage, QuestGiver='Gryan')]
        result = self.executor._get_quest_chain({'quest_name': 'The Defias Brotherhood'})
        first_query, args = self.cursor.execute.call_args_list[0].args
        self.assertIn('ID IN', first_query)
        self.assertEqual(args, (141, 'the defias brotherhood'))
        self.assertIn('Selected stage: [[quest:141:', result)
        self.assertIn('ACTIVE in your quest log', result)
        self.assertIn('not proof', result)
        self.cursor.close.assert_called_once()
        self.connection.close.assert_called_once()

    def test_multiple_active_same_title_asks_instead_of_choosing(self):
        self.executor.set_active_quest_ids([141, 142])
        self.cursor.fetchall.return_value = [dict(
            ID=i, LogTitle='Shared', QuestLevel=18, MinLevel=14, AllowableRaces=0)
            for i in (141, 142)]
        result = self.executor._get_quest_chain({'quest_name': 'Shared'})
        self.assertIn('Please clarify', result)
        self.cursor.fetchone.assert_not_called()

    def test_context_exposes_server_ids_not_model_supplied_ids(self):
        self.executor.begin_request({'version': 1, 'summary': 'Quest names'})
        context = json.loads(self.executor.execute_tool('get_character_context', {}))
        self.assertEqual(context['active_quest_ids'], [141])
        self.assertIn('server-owned', self.executor.execute_tool(
            'get_character_context', {'active_quest_ids': [999]}))


if __name__ == '__main__':
    unittest.main()
