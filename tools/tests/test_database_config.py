"""Custom world database routing without live connections or provider calls."""

import os
import sys
import unittest
from collections import defaultdict
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_tools import GameToolExecutor
from llm_guide_bridge import LLMBridge


class DatabaseConfigTests(unittest.TestCase):
    def test_default_world_name_preserves_existing_callers(self):
        executor = GameToolExecutor({'database': 'custom_characters'})
        with patch('mysql.connector.connect') as connect:
            executor.get_connection()
        self.assertEqual(connect.call_args.kwargs['database'], 'acore_world')
        self.assertEqual(executor.db_config['database'], 'custom_characters')

    def test_bridge_routes_world_and_character_connections_independently(self):
        for world in ('custom_world', 'world-with-dashes'):
            with self.subTest(world=world):
                bridge = LLMBridge({
                    'LLMGuide.Database.Name': 'custom_characters',
                    'LLMGuide.Database.WorldName': world,
                    'LLMGuide.Database.Host': 'database-host',
                })
                with patch('mysql.connector.connect') as connect:
                    bridge.tool_executor.get_connection()
                    world_args = connect.call_args.kwargs
                    bridge.get_db_connection()
                    character_args = connect.call_args.kwargs
                self.assertEqual(world_args['database'], world)
                self.assertEqual(character_args['database'], 'custom_characters')
                self.assertEqual(world_args['host'], character_args['host'])
                self.assertNotIn('world_database', world_args)
                self.assertEqual(bridge.db_config['database'], 'custom_characters')

    def test_bridge_defaults_world_name_when_setting_is_absent(self):
        self.assertEqual(LLMBridge({}).tool_executor.world_database, 'acore_world')

    def test_creature_schema_detection_uses_connected_database_and_caches(self):
        for column in ('id', 'id1'):
            with self.subTest(column=column):
                executor = GameToolExecutor({}, world_database='custom_world')
                connection = MagicMock()
                cursor = connection.cursor.return_value
                cursor.fetchone.return_value = (column,)
                self.assertEqual(executor._creature_entry_column(connection), column)
                self.assertEqual(executor._creature_entry_column(connection), column)
                query = cursor.execute.call_args.args[0]
                self.assertIn('TABLE_SCHEMA = DATABASE()', query)
                self.assertNotIn('acore_world', query)
                cursor.execute.assert_called_once()

    def test_quest_area_lookup_uses_connected_world_database(self):
        executor = GameToolExecutor({}, world_database='custom_world')
        connection = MagicMock()
        cursor = connection.cursor.return_value
        executor.get_connection = MagicMock(return_value=connection)
        executor._creature_entry_column = MagicMock(return_value='id')
        quest = defaultdict(int, ID=1, LogTitle='Test Quest', QuestLevel=10,
                            MinLevel=1)
        cursor.fetchall.return_value = [quest]
        cursor.fetchone.side_effect = [
            {'name': 'Test Giver', 'areaId': 12}, None,
        ]
        result = executor._get_quest_info({'quest_id': 1})
        queries = [call.args[0] for call in cursor.execute.call_args_list]
        area_query = next(query for query in queries if 'areatable_dbc' in query)
        self.assertIn('FROM areatable_dbc ', area_query)
        self.assertFalse(any('acore_world' in query for query in queries))
        self.assertIn('Test Giver', result)
        cursor.close.assert_called_once()
        connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
