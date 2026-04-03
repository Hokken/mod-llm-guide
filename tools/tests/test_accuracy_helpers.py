#!/usr/bin/env python3
"""Focused regression tests for accuracy helper logic."""

import os
import sys
import unittest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS_DIR = os.path.dirname(_TEST_DIR)
sys.path.insert(0, _TOOLS_DIR)

from game_tools import GameToolExecutor
from guide_tool_items import GuideToolItemMixin
from guide_tool_npcs import GuideToolNpcMixin
from guide_tool_quests import GuideToolQuestMixin
from guide_tool_shared import GuideToolSharedMixin
from guide_tool_spells import GuideToolSpellMixin
from llm_guide_bridge import extract_player_defaults_from_context


class ContextParserTests(unittest.TestCase):
    def test_extract_defaults_with_zone(self):
        context = (
            "Karaez is a level 19 Night Elf Hunter in Darkshore. "
            "Alliance. Gold: 10 silver."
        )

        defaults = extract_player_defaults_from_context(context)

        self.assertEqual(defaults["level"], 19)
        self.assertEqual(defaults["player_class"], "hunter")
        self.assertEqual(defaults["faction"], "alliance")

    def test_extract_defaults_without_zone(self):
        context = (
            "Karaez is a level 19 Night Elf Hunter. "
            "Alliance. Gold: 10 silver."
        )

        defaults = extract_player_defaults_from_context(context)

        self.assertEqual(defaults["level"], 19)
        self.assertEqual(defaults["player_class"], "hunter")
        self.assertEqual(defaults["faction"], "alliance")

    def test_extract_defaults_empty_context(self):
        defaults = extract_player_defaults_from_context("")

        self.assertEqual(
            defaults,
            {
                "level": None,
                "player_class": None,
                "faction": None,
            },
        )


class NameMatchingTests(unittest.TestCase):
    def test_normalize_lookup_text(self):
        normalized = GameToolExecutor._normalize_lookup_text(
            "  The-Band of  Something! "
        )

        self.assertEqual(normalized, "the band of something")

    def test_exact_name_scores_higher_than_fuzzy(self):
        exact = GameToolExecutor._score_name_match(
            "charge", "Charge"
        )
        fuzzy = GameToolExecutor._score_name_match(
            "charge", "Charging"
        )

        self.assertGreater(exact, fuzzy)

    def test_weak_but_clear_top_match_is_not_ambiguous(self):
        matches = [
            {"name": "Arcnae Blast", "score": 600},
            {"name": "Fireball", "score": 100},
        ]

        self.assertFalse(
            GameToolExecutor._is_ambiguous_top_match(matches)
        )

    def test_duplicate_same_name_is_ambiguous(self):
        matches = [
            {"name": "Defender", "score": 850},
            {"name": "Defender", "score": 845},
        ]

        self.assertTrue(
            GameToolExecutor._is_ambiguous_top_match(matches)
        )


class ExecutorCompositionTests(unittest.TestCase):
    def test_split_domain_methods_resolve_from_mixins(self):
        expected_owners = {
            "_find_vendor": GuideToolNpcMixin,
            "_get_spell_info": GuideToolSpellMixin,
            "_get_quest_info": GuideToolQuestMixin,
            "_get_item_info": GuideToolItemMixin,
            "_normalize_lookup_text": GuideToolSharedMixin,
        }

        for method_name, owner in expected_owners.items():
            self.assertNotIn(method_name, GameToolExecutor.__dict__)
            executor_attr = getattr(
                GameToolExecutor, method_name
            )
            owner_attr = getattr(owner, method_name)
            executor_func = getattr(
                executor_attr, "__func__", executor_attr
            )
            owner_func = getattr(
                owner_attr, "__func__", owner_attr
            )
            self.assertIs(executor_func, owner_func)

    def test_executor_mro_keeps_split_mixins_ahead_of_object(self):
        mro = GameToolExecutor.__mro__

        self.assertLess(
            mro.index(GuideToolNpcMixin),
            mro.index(object),
        )
        self.assertLess(
            mro.index(GuideToolSpellMixin),
            mro.index(object),
        )
        self.assertLess(
            mro.index(GuideToolQuestMixin),
            mro.index(object),
        )
        self.assertLess(
            mro.index(GuideToolItemMixin),
            mro.index(object),
        )
        self.assertLess(
            mro.index(GuideToolSharedMixin),
            mro.index(object),
        )

    def test_close_high_confidence_matches_are_ambiguous(self):
        matches = [
            {"name": "Band of the Unicorn", "score": 840},
            {"name": "Band of the Falcon", "score": 830},
        ]

        self.assertTrue(
            GameToolExecutor._is_ambiguous_top_match(matches)
        )


if __name__ == "__main__":
    unittest.main()
