"""Item lookup domain for mod-llm-guide."""


class GuideToolItemMixin:
    """Item details and upgrade behavior."""

    def _search_item_candidates(
        self, cursor, item_name: str, limit: int = 12
    ) -> list[dict]:
        cursor.execute("""
            SELECT entry, name, Quality, ItemLevel,
                   RequiredLevel, InventoryType,
                   class AS item_class, subclass
            FROM item_template
            WHERE LOWER(name) LIKE %s
            LIMIT 50
        """, (f"%{item_name.lower()}%",))

        candidates = []
        seen = set()
        for row in cursor.fetchall():
            if row['entry'] in seen:
                continue
            seen.add(row['entry'])
            score = self._score_name_match(
                item_name, row['name']
            )
            if score <= 0:
                continue
            row['score'] = score
            candidates.append(row)

        candidates.sort(
            key=lambda row: (
                -row['score'],
                row['RequiredLevel'],
                row['ItemLevel'],
                row['name'],
            )
        )
        return candidates[:limit]

    def _format_item_clarification(
        self, item_name: str, candidates: list[dict]
    ) -> str:
        result = (
            f"I found multiple items matching "
            f"'{item_name}'. Please clarify "
            f"which one you mean:\n"
        )
        for item in candidates[:5]:
            item_link = (
                f"[[item:{item['entry']}:"
                f"{item['name']}:{item['Quality']}]]"
            )
            result += (
                f"- {item_link} "
                f"(iLvl {item['ItemLevel']}, "
                f"req {item['RequiredLevel']})\n"
            )
        result += (
            "\nIMPORTANT: Include the "
            "[[item:...]] markers exactly "
            "as shown - they become "
            "clickable item links!"
        )
        return result

    def _get_item_info(self, params: dict) -> str:
        """Get detailed item information."""
        item_name = params.get("item_name", "")

        if not item_name:
            return "Please specify an item name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        candidates = self._search_item_candidates(
            cursor, item_name
        )
        if not candidates:
            cursor.close()
            conn.close()
            return f"Item '{item_name}' not found."

        if self._is_ambiguous_top_match(candidates):
            result = self._format_item_clarification(
                item_name, candidates
            )
            cursor.close()
            conn.close()
            return result

        cursor.execute("""
            SELECT entry, name, Quality, ItemLevel,
                   RequiredLevel, class as item_class,
                   subclass, InventoryType, dmg_min1,
                   dmg_max1, armor, stat_type1,
                   stat_value1, stat_type2, stat_value2,
                   stat_type3, stat_value3
            FROM item_template
            WHERE entry = %s
            LIMIT 1
        """, (candidates[0]['entry'],))

        item = cursor.fetchone()

        if not item:
            cursor.close()
            conn.close()
            return f"Item '{item_name}' not found."

        quality_names = {0: 'Poor/Gray', 1: 'Common/White', 2: 'Uncommon/Green', 3: 'Rare/Blue', 4: 'Epic/Purple', 5: 'Legendary/Orange'}
        slot_names = {
            1: 'Head', 2: 'Neck', 3: 'Shoulder', 4: 'Shirt', 5: 'Chest',
            6: 'Waist', 7: 'Legs', 8: 'Feet', 9: 'Wrists', 10: 'Hands',
            11: 'Finger', 12: 'Trinket', 13: 'One-Hand', 14: 'Shield',
            15: 'Ranged', 16: 'Back', 17: 'Two-Hand', 21: 'Main Hand', 22: 'Off Hand'
        }
        stat_names = {
            3: 'Agility', 4: 'Strength', 5: 'Intellect', 6: 'Spirit', 7: 'Stamina',
            12: 'Defense', 13: 'Dodge', 14: 'Parry', 31: 'Hit', 32: 'Crit',
            36: 'Haste', 37: 'Expertise', 38: 'Attack Power', 45: 'Spell Power'
        }

        quality = quality_names.get(item['Quality'], 'Unknown')
        slot = slot_names.get(item['InventoryType'], '')

        item_link = f"[[item:{item['entry']}:{item['name']}:{item['Quality']}]]"
        result = f"Item: {item_link} ({quality})\n"
        result += f"Item Level: {item['ItemLevel']}, Requires Level: {item['RequiredLevel']}\n"
        if slot:
            result += f"Slot: {slot}\n"

        if item['dmg_min1'] > 0:
            result += f"Damage: {int(item['dmg_min1'])} - {int(item['dmg_max1'])}\n"

        if item['armor'] > 0:
            result += f"Armor: {item['armor']}\n"

        stats = []
        for i in range(1, 4):
            stat_type = item[f'stat_type{i}']
            stat_val = item[f'stat_value{i}']
            if stat_type and stat_val:
                stat_name = stat_names.get(stat_type, f'Stat{stat_type}')
                stats.append(f"+{stat_val} {stat_name}")
        if stats:
            result += f"Stats: {', '.join(stats)}\n"

        cursor.execute("""
            SELECT ct.name, cl.Chance
            FROM creature_loot_template cl
            JOIN creature_template ct ON cl.Entry = ct.lootid
            WHERE cl.Item = %s AND cl.Chance > 0
            ORDER BY cl.Chance DESC
            LIMIT 5
        """, (item['entry'],))
        drops = cursor.fetchall()
        if drops:
            drop_list = [f"{d['name']} ({d['Chance']:.1f}%)" for d in drops]
            result += f"Drops from: {', '.join(drop_list)}\n"

        cursor.execute("""
            SELECT ct.name FROM npc_vendor nv
            JOIN creature_template ct ON nv.entry = ct.entry
            WHERE nv.item = %s LIMIT 3
        """, (item['entry'],))
        vendors = cursor.fetchall()
        if vendors:
            vendor_list = [v['name'] for v in vendors]
            result += f"Sold by: {', '.join(vendor_list)}\n"

        cursor.execute("""
            SELECT ID, LogTitle, QuestLevel FROM quest_template
            WHERE RewardItem1 = %s OR RewardItem2 = %s OR RewardItem3 = %s OR RewardItem4 = %s
            LIMIT 3
        """, (item['entry'], item['entry'], item['entry'], item['entry']))
        quests = cursor.fetchall()
        if quests:
            quest_links = [f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]" for q in quests]
            result += f"Quest reward from: {', '.join(quest_links)}\n"

        cursor.close()
        conn.close()

        result += "\nIMPORTANT: Include the [[item:...]] and [[quest:...]] markers exactly as shown - they become clickable links!"
        return result

    def _find_item_upgrades(self, params: dict) -> str:
        """Find item upgrades for a specific item."""
        current_item = params.get("current_item", "")
        player_level = params.get("player_level", 80)
        player_class = params.get("player_class", "").lower()

        if not current_item:
            return "Please specify the current item name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        candidates = self._search_item_candidates(
            cursor, current_item
        )
        if not candidates:
            cursor.close()
            conn.close()
            return f"Item '{current_item}' not found."

        if self._is_ambiguous_top_match(candidates):
            result = self._format_item_clarification(
                current_item, candidates
            )
            cursor.close()
            conn.close()
            return result

        cursor.execute("""
            SELECT entry, name, ItemLevel,
                   InventoryType, class as item_class,
                   subclass
            FROM item_template
            WHERE entry = %s
            LIMIT 1
        """, (candidates[0]['entry'],))

        current = cursor.fetchone()

        if not current:
            cursor.close()
            conn.close()
            return f"Item '{current_item}' not found."

        class_mask = {
            'warrior': 1, 'paladin': 2, 'hunter': 4, 'rogue': 8,
            'priest': 16, 'death knight': 32, 'shaman': 64, 'mage': 128,
            'warlock': 256, 'druid': 1024
        }
        class_bit = class_mask.get(player_class, 0)

        class_preferred_stats = {
            'hunter': [3, 7, 31, 32, 38],
            'rogue': [3, 7, 31, 32, 38],
            'warrior': [4, 7, 31, 32, 38],
            'death knight': [4, 7, 31, 32, 38],
            'paladin': [4, 7, 5, 31, 45],
            'shaman': [5, 7, 31, 45, 3],
            'druid': [3, 5, 7, 31, 45],
            'mage': [5, 7, 31, 32, 45],
            'warlock': [5, 7, 31, 32, 45],
            'priest': [5, 6, 7, 31, 45],
        }
        preferred_stats = class_preferred_stats.get(player_class, [])

        stat_filter = ""
        if preferred_stats:
            stat_conditions = []
            for stat in preferred_stats:
                stat_conditions.append(f"stat_type1 = {stat} OR stat_type2 = {stat} OR stat_type3 = {stat}")
            stat_filter = f"AND ({' OR '.join(stat_conditions)})"

        cursor.execute(f"""
            SELECT entry, name, ItemLevel, Quality, RequiredLevel,
                   stat_type1, stat_value1, stat_type2, stat_value2
            FROM item_template
            WHERE InventoryType = %s
              AND ItemLevel > %s
              AND ItemLevel <= %s
              AND RequiredLevel <= %s
              AND (AllowableClass = -1 OR AllowableClass = 0 OR (AllowableClass & %s) > 0)
              {stat_filter}
            ORDER BY ItemLevel ASC
            LIMIT 10
        """, (current['InventoryType'], current['ItemLevel'], current['ItemLevel'] + 30, player_level, class_bit if class_bit else 2047))

        upgrades = cursor.fetchall()
        cursor.close()
        conn.close()

        if not upgrades:
            return f"No suitable upgrades found for {current['name']} (iLvl {current['ItemLevel']}) with {player_class}-appropriate stats within your level range."

        stat_names = {3: 'Agi', 4: 'Str', 5: 'Int', 6: 'Spi', 7: 'Stam', 31: 'Hit', 32: 'Crit', 38: 'AP', 45: 'SP'}

        result = f"Upgrades for {current['name']} (iLvl {current['ItemLevel']}) for {player_class}:\n"
        for u in upgrades:
            stats = []
            if u['stat_type1'] and u['stat_value1']:
                stats.append(f"+{u['stat_value1']} {stat_names.get(u['stat_type1'], '?')}")
            if u['stat_type2'] and u['stat_value2']:
                stats.append(f"+{u['stat_value2']} {stat_names.get(u['stat_type2'], '?')}")
            stat_str = f" [{', '.join(stats)}]" if stats else ""
            item_link = f"[[item:{u['entry']}:{u['name']}:{u['Quality']}]]"
            result += f"- {item_link} (iLvl {u['ItemLevel']}, req {u['RequiredLevel']}){stat_str}\n"

        result += "\nIMPORTANT: Include the [[item:...]] markers exactly as shown - they become clickable item links!"
        return result
