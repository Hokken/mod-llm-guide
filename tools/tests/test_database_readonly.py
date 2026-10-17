"""Opt-in real MySQL query checks; no schema changes or provider calls.

Set GUIDE_TEST_CONFIG to a guide config and optionally GUIDE_TEST_DB_HOST
when the database is published on a different host than its Docker name.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_tools import GameToolExecutor
from llm_guide_bridge import LLMBridge, parse_conf_file


@unittest.skipUnless(os.environ.get('GUIDE_TEST_CONFIG'), 'Opt-in database check')
class DatabaseReadOnlyTests(unittest.TestCase):
    def setUp(self):
        config = parse_conf_file(os.environ['GUIDE_TEST_CONFIG'])
        if os.environ.get('GUIDE_TEST_DB_HOST'):
            config['LLMGuide.Database.Host'] = os.environ['GUIDE_TEST_DB_HOST']
        self.executor = GameToolExecutor(LLMBridge(config).db_config)
        connect = self.executor.get_connection
        def readonly_connection():
            connection = connect()
            connection.start_transaction(readonly=True)
            return connection
        self.executor.get_connection = readonly_connection
        self.executor.begin_request(dict(
            level=80, race_mask=1, class_mask=1, summary='Synthetic test character',
            skills={str(key): 450 for key in range(1000)}, reputation={},
            equipment={}, known_spells=[], eligible_quest_ids=[]))

    def test_quest_union_and_server_filter(self):
        conn = self.executor.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT ID FROM quest_template ORDER BY ID')
            ids = [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()
        self.executor.snapshot['eligible_quest_ids'] = ids
        result = self.executor.execute_tool('get_available_quests', dict(
            zone='elwynn forest', player_level=10, faction='alliance',
            player_class='warrior'))
        self.assertNotIn('Error executing tool:', result)
        self.assertIn('[[quest:', result)
        self.assertIn('Server-eligible', result)

    def test_full_item_comparison_and_source_queries(self):
        conn = self.executor.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute('''
                SELECT entry, name FROM item_template
                WHERE class = 4 AND subclass = 4 AND InventoryType = 1
                  AND ItemLevel BETWEEN 40 AND 60
                  AND (AllowableClass & 1) <> 0 AND (AllowableRace & 1) <> 0
                ORDER BY entry LIMIT 1
            ''')
            current = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()
        self.assertIsNotNone(current)
        self.executor.snapshot['equipment'] = {'0': current['entry']}
        result = self.executor.execute_tool('find_item_upgrades', dict(
            current_item=current['name'], role='tank'))
        self.assertNotIn('Error executing tool:', result)
        self.assertIn('[[item:', result)
        self.assertIn('Source', result)


if __name__ == '__main__':
    unittest.main()
