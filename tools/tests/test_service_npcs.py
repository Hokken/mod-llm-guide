"""Flight-master discovery must not depend on an NPC's title."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_tools import GameToolExecutor


class ServiceNpcTests(unittest.TestCase):
    def setUp(self):
        self.executor = GameToolExecutor({})
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value
        self.executor.get_connection = MagicMock(return_value=self.connection)
        self.executor._creature_entry_column = MagicMock(return_value='id')
        self.executor.set_player_zone('duskwood')
        self.executor.set_player_position(-10500, -1250, 0)
        self.cursor.fetchall.return_value = [dict(
            npc_entry=2409, npc_name='Felicia Maline', title='Gryphon Master',
            pos_x=-10513.8, pos_y=-1258.79, map_id=0, area_name='Darkshire')]

    def test_flight_titles_and_aliases_use_service_flag(self):
        for alias in self.executor.FLIGHT_MASTER_ALIASES:
            with self.subTest(alias=alias):
                result = self.executor.execute_tool('find_service_npc',
                    dict(service_type=alias, zone='duskwood'))
                query, args = self.cursor.execute.call_args.args
                self.assertIn('(ct.npcflag & %s) <> 0', query)
                self.assertNotIn('ct.subname LIKE', query)
                self.assertIn(8192, args)
                self.assertIn('ORDER BY', query)
                self.assertIn('[[npc:2409:Felicia Maline]]', result)
                self.assertIn('Darkshire', result)
                self.assertIn('closest first', result)

    def test_other_services_retain_title_lookup(self):
        self.executor.execute_tool('find_service_npc',
                                   dict(service_type='innkeeper', zone='duskwood'))
        query, args = self.cursor.execute.call_args.args
        self.assertIn('ct.subname LIKE %s', query)
        self.assertIn('%Innkeeper%', args)
        self.assertNotIn(8192, args)

    def test_empty_results_do_not_claim_service_is_absent(self):
        self.cursor.fetchall.return_value = []
        result = self.executor.execute_tool('find_service_npc',
            dict(service_type='flight master', zone='duskwood'))
        self.assertIn('not proof', result)
        self.assertIn('Do not invent', result)
        self.cursor.close.assert_called_once()
        self.connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
