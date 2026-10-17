"""Player-facing item summaries preserve links, sources and real warnings."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from guide_presentation import compact_equipment_answer
from game_tools import GameToolExecutor


class PresentationTests(unittest.TestCase):
    def test_stats_and_caveats_removed_sources_preserved(self):
        text = ('[[item:1:Blade:2]] (+1 Agility, +1.1 weapon DPS from '
                '[[npc:2:Boss]]) is an option. [[item:3:Other:2]] '
                '(+5 Agility, +2 Stamina, -1.1 weapon DPS, source unknown). '
                'Base stats only; enchants and gems not evaluated. '
                'Some acquisition sources are unverified.')
        result = compact_equipment_answer(text)
        self.assertIn('from [[npc:2:Boss]]', result)
        self.assertIn('(source unknown)', result)
        for unwanted in ('+1', '-1.1', 'Base stats', 'not evaluated',
                         'Some acquisition'):
            self.assertNotIn(unwanted, result)
        self.assertEqual(compact_equipment_answer(result), result)

    def test_links_and_non_stat_details_are_untouched(self):
        text = ('[[item:1:Odd (+5 Agility) Name:2]] (requires level 24) '
                'from [[npc:2:Boss]] at 30.6, 59.4. Cannot equip yet.')
        self.assertEqual(compact_equipment_answer(text), text)

    def test_explicit_detail_bypasses_compaction(self):
        executor = GameToolExecutor({})
        marker = '[[item:1:Blade:2]]'
        executor.evidence.record(marker)
        text = marker + ' (+5 Agility).'
        self.assertEqual(executor.finalize_answer(text, True, detailed=True), text)
        self.assertNotIn('+5', executor.finalize_answer(text, True))


if __name__ == '__main__':
    unittest.main()
