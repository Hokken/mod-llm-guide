"""Item lookup domain for mod-llm-guide."""

from guide_item_comparison import item_stats, stat_deltas, meets_requirements


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
            SELECT *, class as item_class
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
        for i in range(1, 11):
            stat_type = item[f'stat_type{i}']
            stat_val = item[f'stat_value{i}']
            if stat_val:
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
        """Compare attainable requirements and base stats, never simulate DPS."""
        current_item = params.get('current_item', '')
        snapshot = getattr(self, 'snapshot', None)
        if snapshot is None:
            return ("Error executing tool: full character snapshot unavailable. "
                    "Cannot verify personal gear requirements with this server.")
        role = params.get('role')
        preferred = params.get('preferred_stats') or self.role_stats.get(role, [])
        if not role:
            return ("Please specify the intended role/spec before comparing "
                    "gear: tank, healer, melee, ranged or caster.")
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            candidates = self._search_item_candidates(cursor, current_item)
            if not candidates:
                return f"Item '{current_item}' not found."
            # A worn item resolves otherwise ambiguous item names.
            worn = set(snapshot['equipment'].values())
            matches = [item for item in candidates if item['entry'] in worn]
            if len(matches) == 1:
                candidates = matches
            elif self._is_ambiguous_top_match(candidates):
                return self._format_item_clarification(current_item, candidates)
            cursor.execute("SELECT * FROM item_template WHERE entry = %s",
                           (candidates[0]['entry'],))
            current = cursor.fetchone()
            if not current:
                return f"Item '{current_item}' not found."
            # Chest/robe items share a slot. Other hand configurations require
            # a whole-loadout comparison and are deliberately not mixed here.
            slots = (5, 20) if current['InventoryType'] in (5, 20) else (
                current['InventoryType'],)
            cursor.execute(f"""
                SELECT * FROM item_template
                WHERE InventoryType IN ({','.join(['%s'] * len(slots))})
                  AND ItemLevel >= %s AND ItemLevel <= %s
                  AND RequiredLevel <= %s AND entry <> %s
                  AND (AllowableClass & %s) <> 0
                  AND (AllowableRace & %s) <> 0
                ORDER BY ItemLevel ASC, entry ASC
            """, (*slots, current['ItemLevel'],
                  current['ItemLevel'] + self.upgrade_level_range,
                  snapshot['level'], current['entry'],
                  snapshot['class_mask'], snapshot['race_mask']))
            upgrades = [item for item in cursor.fetchall()
                        if meets_requirements(item, snapshot)
                        and (not preferred or
                             set(preferred).intersection(item_stats(item)))]
            upgrades = upgrades[:self.upgrade_limit]
            current_link = (f"[[item:{current['entry']}:{current['name']}:"
                            f"{current['Quality']}]]")
            result = (f"Comparison candidates for {current_link} ({role}). "
                      "These meet known level, race, class, proficiency and "
                      "reputation requirements at request time.\n")
            if not upgrades:
                return result + "No matching candidates in the configured range."
            for item in upgrades:
                marker = (f"[[item:{item['entry']}:{item['name']}:"
                          f"{item['Quality']}]]")
                sources = self._comparison_sources(cursor, item['entry'])
                comparison = (
                    f"{marker} (iLvl {item['ItemLevel']}, requires level "
                    f"{item['RequiredLevel']}), versus {current_link}: "
                    f"{stat_deltas(current, item)}. {sources}")
                result += comparison + '\n'
                self.item_comparisons[marker] = comparison
            return result + (
                "Do not call candidates definite upgrades based on item level. "
                "Consider gains AND losses for the stated spec internally. "
                "Ordinary answers use links, sources and qualitative reasons, "
                "not numeric stat lists; tooltips provide those numbers. Base comparisons "
                "exclude enchants, gems, socket/set bonuses and proc/use effects; "
                "unique-equipped, hand rules and script conditions need in-game "
                "checks. Sources are leads, not proof of access or affordability. "
                "These limitations guide reasoning internally; do not recite "
                "them in ordinary upgrade answers. Mention an excluded effect "
                "only if requested or materially relevant. Preserve the "
                "returned link markers exactly.")
        finally:
            cursor.close()
            conn.close()

    def _comparison_sources(self, cursor, item_id):
        """Source leads without misrepresenting raw loot weights as rates."""
        cursor.execute("""
            SELECT DISTINCT ct.entry, ct.name FROM npc_vendor nv
            JOIN creature_template ct ON nv.entry = ct.entry
            WHERE nv.item = %s ORDER BY ct.entry LIMIT %s
        """, (item_id, self.upgrade_limit))
        sources = [f"Vendor [[npc:{row['entry']}:{row['name']}]]"
                   for row in cursor.fetchall()]
        cursor.execute("""
            SELECT ID, LogTitle, QuestLevel FROM quest_template
            WHERE %s IN (RewardItem1, RewardItem2, RewardItem3, RewardItem4,
                         RewardChoiceItemID1, RewardChoiceItemID2,
                         RewardChoiceItemID3, RewardChoiceItemID4,
                         RewardChoiceItemID5, RewardChoiceItemID6)
            ORDER BY ID LIMIT %s
        """, (item_id, self.upgrade_limit))
        eligible = set(self.snapshot['eligible_quest_ids'])
        for row in cursor.fetchall():
            state = ("eligible to accept" if row['ID'] in eligible else
                     "not currently eligible to accept; may be in quest log")
            sources.append(f"Quest [[quest:{row['ID']}:{row['LogTitle']}:"
                           f"{row['QuestLevel']}]] ({state})")
        cursor.execute("""
            SELECT DISTINCT ct.entry, ct.name FROM creature_loot_template cl
            JOIN creature_template ct ON cl.Entry = ct.lootid
            WHERE cl.Item = %s AND cl.Reference = 0
            ORDER BY ct.entry LIMIT %s
        """, (item_id, self.upgrade_limit))
        sources.extend(f"Loot [[npc:{row['entry']}:{row['name']}]]"
                       for row in cursor.fetchall())
        return ("Source leads: " + "; ".join(sources) if sources else
                "Source not found in direct vendor/quest/creature lookups; "
                "crafting, reference loot and other sources are not covered.")
