"""Quest lookup domain for mod-llm-guide."""

from zone_coordinates import world_to_map_coords


class GuideToolQuestMixin:
    """Quest lookup, availability, and chain behavior."""

    @staticmethod
    def _get_faction_tag_from_races(
        races: int
    ) -> str:
        alliance_mask = 0x4F1
        horde_mask = 0x2B2
        if races == 0:
            return "Both factions"
        alliance = bool(races & alliance_mask)
        horde = bool(races & horde_mask)
        if alliance and horde:
            return "Both factions"
        if alliance:
            return "Alliance only"
        if horde:
            return "Horde only"
        return "Unknown faction"

    def _search_quest_candidates(
        self, cursor, quest_name: str,
        limit: int = 10
    ) -> list[dict]:
        cursor.execute("""
            SELECT qt.ID, qt.LogTitle, qt.QuestLevel,
                   qt.MinLevel, qt.AllowableRaces
            FROM quest_template qt
            WHERE LOWER(qt.LogTitle) LIKE %s
            LIMIT 40
        """, (f"%{quest_name.lower()}%",))

        candidates = []
        for row in cursor.fetchall():
            score = self._score_name_match(
                quest_name, row['LogTitle']
            )
            if score <= 0:
                continue
            row['score'] = score
            row['name'] = row['LogTitle']
            candidates.append(row)

        candidates.sort(
            key=lambda row: (
                -row['score'],
                row['MinLevel'],
                row['QuestLevel'],
                row['LogTitle'],
            )
        )
        return candidates[:limit]

    def _format_quest_clarification(
        self, quest_name: str, candidates: list[dict]
    ) -> str:
        result = (
            f"I found multiple quests matching "
            f"'{quest_name}'. Please clarify "
            f"which one you mean:\n"
        )
        for quest in candidates[:5]:
            faction = self._get_faction_tag_from_races(
                quest['AllowableRaces']
            )
            quest_link = (
                f"[[quest:{quest['ID']}:"
                f"{quest['LogTitle']}:"
                f"{quest['QuestLevel']}]]"
            )
            lvl = (
                quest['QuestLevel']
                if quest['QuestLevel'] > 0
                else quest['MinLevel']
            )
            result += (
                f"- {quest_link} "
                f"(Level {lvl}, {faction})\n"
            )
        result += (
            "\nIMPORTANT: Include the "
            "[[quest:...]] markers exactly "
            "as shown - they become "
            "clickable links!"
        )
        return result

    def _find_quest_giver(self, params: dict) -> str:
        """Find quest givers in a zone."""
        zone = params.get("zone", "").lower() if params.get("zone") else None
        quest_name = params.get("quest_name")

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        if quest_name:
            dist_cols, order, sel_params, \
                ord_params, dist_active = \
                self._distance_order_params()
            cursor.execute(f"""
                SELECT ct.entry as npc_entry, ct.name as npc_name, qt.ID as quest_id,
                       qt.LogTitle as quest_title, qt.QuestLevel,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                       na.area_name
                       {dist_cols}
                FROM quest_template qt
                JOIN creature_queststarter cq ON qt.ID = cq.quest
                JOIN creature_template ct ON cq.id = ct.entry
                JOIN creature c ON ct.entry = c.id1
                LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
                WHERE qt.LogTitle LIKE %s
                {order}
                LIMIT 5
            """, (*sel_params, f"%{quest_name}%", *ord_params))
        else:
            dist_cols, order, sel_params, \
                ord_params, dist_active = \
                self._distance_order_params(
                    fallback="ORDER BY quest_count DESC"
                )
            zone_coords, zone_filter = self._get_zone_filter(zone) if zone else (None, "")
            cursor.execute(f"""
                SELECT ct.entry as npc_entry, ct.name as npc_name, COUNT(DISTINCT cq.quest) as quest_count,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                       na.area_name
                       {dist_cols}
                FROM creature_template ct
                JOIN creature c ON ct.entry = c.id1
                JOIN creature_queststarter cq ON ct.entry = cq.id
                LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
                WHERE 1=1 {zone_filter}
                GROUP BY ct.entry, c.position_x, c.position_y, c.map, na.area_name
                {order}
                LIMIT 10
            """, (*sel_params, *ord_params))

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if not results:
            return f"No quest givers found{' for ' + quest_name if quest_name else ' in ' + zone if zone else ''}."

        hint = " (closest first)" if dist_active else ""
        if quest_name:
            result = f"Quest '{quest_name}' is given by{hint}:\n"
            for r in results:
                npc_link = f"[[npc:{r['npc_entry']}:{r['npc_name']}]]"
                quest_link = f"[[quest:{r['quest_id']}:{r['quest_title']}:{r['QuestLevel']}]]"
                dist_info = self.format_distance_direction(r['pos_x'], r['pos_y'], r['map_id'])
                dist_str = f" ({dist_info})" if dist_info else ""
                loc = (f" in {r['area_name']}"
                       if r.get('area_name') else "")
                coords = ""
                coord_zone = (
                    zone or self.default_zone
                )
                if (coord_zone and r['pos_x']
                        and r['pos_y']):
                    map_coords = world_to_map_coords(
                        coord_zone, r['pos_x'],
                        r['pos_y']
                    )
                    if map_coords:
                        coords = (
                            f" at {map_coords[0]}"
                            f", {map_coords[1]}"
                        )
                result += f"- {npc_link}{loc}{dist_str}{coords} (Quest: {quest_link})\n"
            result += "\nIMPORTANT: Include all [[...]] markers exactly as shown - they become clickable links!"
        else:
            result = f"Quest givers in {zone or 'the world'}{hint}:\n"
            for r in results:
                npc_link = f"[[npc:{r['npc_entry']}:{r['npc_name']}]]"
                dist_info = self.format_distance_direction(r['pos_x'], r['pos_y'], r['map_id'])
                dist_str = f" ({dist_info})" if dist_info else ""
                loc = (f" in {r['area_name']}"
                       if r.get('area_name') else "")
                coords = ""
                coord_zone = (
                    zone if zone_coords
                    else self.default_zone
                )
                if (coord_zone and r['pos_x']
                        and r['pos_y']):
                    map_coords = world_to_map_coords(
                        coord_zone, r['pos_x'],
                        r['pos_y']
                    )
                    if map_coords:
                        coords = (
                            f" at {map_coords[0]}"
                            f", {map_coords[1]}"
                        )
                result += f"- {npc_link}{loc}{dist_str}{coords} ({r['quest_count']} quests)\n"
        return result

    def _get_available_quests(self, params: dict) -> str:
        """Find quests available to a player at their current level in a zone."""
        zone = params.get("zone", "").lower() if params.get("zone") else None
        player_level = params.get("player_level", 1)
        player_class = params.get("player_class", "").lower()
        faction = params.get("faction", "").lower()
        active_quest_ids = params.get(
            "active_quest_ids", []
        )

        if not zone:
            return "Please specify a zone to search for available quests."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        if not zone_coords:
            return f"Zone '{zone}' not found. Try a different zone name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        faction_filter = ""
        if faction == "alliance":
            faction_filter = "AND (qt.AllowableRaces = 0 OR (qt.AllowableRaces & 1101) > 0)"
        elif faction == "horde":
            faction_filter = "AND (qt.AllowableRaces = 0 OR (qt.AllowableRaces & 690) > 0)"

        class_mask = {
            'warrior': 1, 'paladin': 2, 'hunter': 4, 'rogue': 8,
            'priest': 16, 'death knight': 32, 'shaman': 64, 'mage': 128,
            'warlock': 256, 'druid': 1024
        }
        class_bit = class_mask.get(player_class, 0)
        class_filter = ""
        if class_bit:
            class_filter = f"AND (qta.AllowableClasses IS NULL OR qta.AllowableClasses = 0 OR (qta.AllowableClasses & {class_bit}) > 0)"

        active_ids = []
        if isinstance(active_quest_ids, str):
            for part in active_quest_ids.split(','):
                part = part.strip()
                if part.isdigit():
                    active_ids.append(int(part))
        elif isinstance(active_quest_ids, list):
            for quest_id in active_quest_ids:
                try:
                    active_ids.append(int(quest_id))
                except (TypeError, ValueError):
                    continue
        active_ids = sorted(set(active_ids))
        active_filter = ""
        active_params = []
        if active_ids:
            placeholders = ", ".join(
                ["%s"] * len(active_ids)
            )
            active_filter = (
                f"AND qt.ID NOT IN "
                f"({placeholders})"
            )
            active_params.extend(active_ids)

        cursor.execute(f"""
            SELECT DISTINCT qt.ID, qt.LogTitle, qt.QuestLevel, qt.MinLevel,
                   ct.entry as npc_entry, ct.name as npc_name
            FROM quest_template qt
            LEFT JOIN quest_template_addon qta ON qt.ID = qta.ID
            JOIN creature_queststarter cq ON qt.ID = cq.quest
            JOIN creature_template ct ON cq.id = ct.entry
            JOIN creature c ON ct.entry = c.id1
            WHERE qt.MinLevel <= %s
              AND qt.QuestLevel >= %s
              AND qt.QuestLevel <= %s
              {faction_filter}
              {class_filter}
              {active_filter}
              {zone_filter}
            ORDER BY qt.QuestLevel ASC, qt.LogTitle
            LIMIT 20
        """, (
            player_level,
            max(1, player_level - 5),
            player_level + 10,
            *active_params,
        ))

        quests = cursor.fetchall()
        cursor.close()
        conn.close()

        if not quests:
            return f"No quests available at level {player_level} in {zone}. You may need to level up or check a different zone."

        npc_quests = {}
        for q in quests:
            npc_key = (q['npc_entry'], q['npc_name'])
            if npc_key not in npc_quests:
                npc_quests[npc_key] = []
            npc_quests[npc_key].append(q)

        result = f"Quests available at level {player_level} in {zone.title()}:\n\n"

        for (npc_entry, npc_name), quest_list in npc_quests.items():
            npc_link = f"[[npc:{npc_entry}:{npc_name}]]"
            result += f"{npc_link}:\n"
            for q in quest_list[:3]:
                quest_link = f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]"
                level_note = f" (Lvl {q['QuestLevel']}, requires {q['MinLevel']})"
                result += f"  - {quest_link}{level_note}\n"
            if len(quest_list) > 3:
                result += f"  - ... and {len(quest_list) - 3} more quests\n"
            result += "\n"

        result += "IMPORTANT: Include the [[quest:...]] and [[npc:...]] markers exactly as shown - they become clickable links!"
        return result

    def _get_quest_info(self, params: dict) -> str:
        """Get detailed quest information."""
        quest_name = params.get("quest_name", "")

        if not quest_name:
            return (
                "Please specify a quest name "
                "to look up."
            )

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT qt.ID, qt.LogTitle,
                   qt.QuestLevel, qt.MinLevel,
                   qt.AllowableRaces,
                   qt.LogDescription,
                   qt.QuestDescription,
                   qt.RequiredNpcOrGo1,
                   qt.RequiredNpcOrGo2,
                   qt.RequiredNpcOrGo3,
                   qt.RequiredNpcOrGo4,
                   qt.RequiredNpcOrGoCount1,
                   qt.RequiredNpcOrGoCount2,
                   qt.RequiredNpcOrGoCount3,
                   qt.RequiredNpcOrGoCount4,
                   qt.RequiredItemId1,
                   qt.RequiredItemId2,
                   qt.RequiredItemId3,
                   qt.RequiredItemCount1,
                   qt.RequiredItemCount2,
                   qt.RequiredItemCount3,
                   qt.ObjectiveText1,
                   qt.ObjectiveText2,
                   qt.ObjectiveText3,
                   qt.RewardMoney,
                   qt.RewardItem1,
                   qt.RewardItem2,
                   qt.RewardAmount1,
                   qt.RewardAmount2,
                   qt.RewardNextQuest
            FROM quest_template qt
            WHERE qt.LogTitle LIKE %s
            LIMIT 5
        """, (f"%{quest_name}%",))

        quests = cursor.fetchall()

        if not quests:
            cursor.close()
            conn.close()
            return f"Quest '{quest_name}' not found."

        all_results = []

        for quest in quests:
            faction = self._get_faction_tag_from_races(
                quest['AllowableRaces']
            )
            quest_link = (
                f"[[quest:{quest['ID']}:"
                f"{quest['LogTitle']}:"
                f"{quest['QuestLevel']}]]"
            )
            lvl = quest['QuestLevel']
            lvl_str = (
                "scales to player level"
                if lvl == -1
                else f"Level {lvl}"
            )
            out = (
                f"Quest: {quest_link} "
                f"({lvl_str}, requires level "
                f"{quest['MinLevel']}) "
                f"[{faction}]\n\n"
            )

            if quest['LogDescription']:
                desc = (
                    quest['LogDescription']
                    .replace('$b$b', ' ')
                    .replace('$b', ' ')[:200]
                )
                out += f"Description: {desc}...\n\n"

            objectives = []
            for i in range(1, 5):
                npc_or_go = (
                    quest[f'RequiredNpcOrGo{i}']
                )
                count = (
                    quest[f'RequiredNpcOrGoCount{i}']
                )
                if npc_or_go and count > 0:
                    if npc_or_go > 0:
                        cursor.execute(
                            "SELECT name FROM "
                            "creature_template "
                            "WHERE entry = %s",
                            (npc_or_go,)
                        )
                        row = cursor.fetchone()
                        if row:
                            objectives.append(
                                f"Kill/Interact "
                                f"with {count}x "
                                f"{row['name']}"
                            )
                    else:
                        go_id = abs(npc_or_go)
                        cursor.execute(
                            "SELECT name FROM "
                            "gameobject_template "
                            "WHERE entry = %s",
                            (go_id,)
                        )
                        row = cursor.fetchone()
                        if row:
                            objectives.append(
                                f"Interact with "
                                f"{count}x "
                                f"{row['name']}"
                            )

            for i in range(1, 4):
                item_id = (
                    quest[f'RequiredItemId{i}']
                )
                count = (
                    quest[f'RequiredItemCount{i}']
                )
                if item_id and count > 0:
                    cursor.execute(
                        "SELECT name FROM "
                        "item_template "
                        "WHERE entry = %s",
                        (item_id,)
                    )
                    item_row = cursor.fetchone()
                    if item_row:
                        objectives.append(
                            f"Collect {count}x "
                            f"{item_row['name']}"
                        )

            for i in range(1, 4):
                obj_text = (
                    quest[f'ObjectiveText{i}']
                )
                if obj_text:
                    objectives.append(obj_text)

            if objectives:
                out += "Objectives:\n"
                for obj in objectives:
                    out += f"- {obj}\n"
                out += "\n"

            cursor.execute("""
                SELECT ct.name, ct.entry,
                    c.map, c.areaId
                FROM creature_queststarter cq
                JOIN creature_template ct
                    ON cq.id = ct.entry
                LEFT JOIN creature c
                    ON c.id1 = ct.entry
                WHERE cq.quest = %s
                LIMIT 1
            """, (quest['ID'],))
            giver = cursor.fetchone()
            if giver:
                giver_str = f"Quest giver: " \
                    f"{giver['name']}"
                if giver['areaId']:
                    area_id = giver['areaId']
                    cursor.execute(
                        "SELECT ID FROM "
                        "acore_world"
                        ".areatable_dbc "
                        "WHERE ID = %s",
                        (area_id,)
                    )
                    giver_str += (
                        f" (area {area_id})"
                    )
                out += giver_str + "\n"

            cursor.execute("""
                SELECT ct.name
                FROM creature_questender cq
                JOIN creature_template ct
                    ON cq.id = ct.entry
                WHERE cq.quest = %s LIMIT 1
            """, (quest['ID'],))
            ender = cursor.fetchone()
            if ender:
                out += (
                    f"Turn in to: "
                    f"{ender['name']}\n"
                )

            rewards = []
            if quest['RewardMoney'] > 0:
                money = quest['RewardMoney']
                if money >= 10000:
                    rewards.append(
                        f"{money // 10000}g"
                    )
                elif money >= 100:
                    rewards.append(
                        f"{money // 100}s"
                    )

            for i in range(1, 3):
                item_id = quest[f'RewardItem{i}']
                amount = quest[f'RewardAmount{i}']
                if item_id:
                    cursor.execute(
                        "SELECT name, Quality "
                        "FROM item_template "
                        "WHERE entry = %s",
                        (item_id,)
                    )
                    item_row = cursor.fetchone()
                    if item_row:
                        item_link = (
                            f"[[item:{item_id}:"
                            f"{item_row['name']}:"
                            f"{item_row['Quality']}"
                            f"]]"
                        )
                        if amount > 1:
                            rewards.append(
                                f"{amount}x "
                                f"{item_link}"
                            )
                        else:
                            rewards.append(
                                item_link
                            )

            if rewards:
                out += (
                    f"Rewards: "
                    f"{', '.join(rewards)}\n"
                )

            if quest['RewardNextQuest']:
                cursor.execute(
                    "SELECT ID, LogTitle, "
                    "QuestLevel FROM "
                    "quest_template "
                    "WHERE ID = %s",
                    (quest['RewardNextQuest'],)
                )
                next_q = cursor.fetchone()
                if next_q:
                    nql = (
                        f"[[quest:{next_q['ID']}:"
                        f"{next_q['LogTitle']}:"
                        f"{next_q['QuestLevel']}]]"
                    )
                    out += f"Leads to: {nql}\n"

            all_results.append(out)

        cursor.close()
        conn.close()

        if len(all_results) > 1:
            header = (
                f"Found {len(all_results)} "
                f"versions of this quest "
                f"(check faction tags):\n\n"
            )
            result = header + (
                "\n---\n\n".join(all_results)
            )
        else:
            result = all_results[0]

        result += (
            "\nIMPORTANT: Include the "
            "[[quest:...]] and [[item:...]] "
            "markers exactly as shown - they "
            "become clickable links!"
        )
        return result

    def _get_class_quests(self, params: dict) -> str:
        """Find class-specific quest chains."""
        player_class = params.get("player_class", "").lower()
        level = params.get("level")

        if not player_class:
            return "Please specify a class (warrior, paladin, hunter, rogue, priest, shaman, mage, warlock, druid, death knight)."

        class_id = self.CLASS_IDS.get(player_class)
        if not class_id:
            return f"Unknown class '{player_class}'. Valid classes: warrior, paladin, hunter, rogue, priest, shaman, mage, warlock, druid, death knight."

        class_mask = 1 << (class_id - 1)

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        level_filter = ""
        if level:
            min_lvl = max(1, int(level) - 10)
            max_lvl = int(level) + 5
            level_filter = f"AND qt.QuestLevel BETWEEN {min_lvl} AND {max_lvl}"

        cursor.execute(f"""
            SELECT
                qt.ID,
                qt.LogTitle,
                qt.QuestLevel,
                qt.MinLevel,
                qt.RewardXPDifficulty
            FROM quest_template qt
            JOIN quest_template_addon qta ON qt.ID = qta.ID
            WHERE qta.AllowableClasses = %s
              AND qt.LogTitle IS NOT NULL
              AND qt.LogTitle != ''
              {level_filter}
            ORDER BY qt.MinLevel, qt.QuestLevel
            LIMIT 30
        """, (class_mask,))

        quests = cursor.fetchall()
        cursor.close()
        conn.close()

        if not quests:
            return f"No class quests found for {player_class}. This may be a data limitation."

        result = f"**{player_class.title()} Class Quests:**\n\n"

        for q in quests:
            lvl_str = f"Level {q['QuestLevel']}" if q['QuestLevel'] > 0 else f"Req. {q['MinLevel']}"
            quest_link = f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]"
            result += f"- {quest_link} ({lvl_str})\n"

        notable_quests = {
            "hunter": "\n**Notable:** Tame Beast quest at 10 to get your first pet. Beast Mastery spec (51+ talent) can tame exotic pets.",
            "warlock": "\n**Notable:** Imp from early quest (level 1-4). Voidwalker at 10, Succubus at 20, Felhunter at 30. Demons are now mostly trainable.",
            "druid": "\n**Notable:** Bear Form at 10, Aquatic Form at 16, Cat Form at 20, Travel Form at 30 (quest-based).",
            "paladin": "\n**Notable:** Redemption (resurrect) at 12. Summon Warhorse trainable at 20, Summon Charger at 40 (no quest in WotLK).",
            "shaman": "\n**Notable:** Totem quests for each element. Call of Earth/Fire/Water/Air at various levels.",
            "warrior": "\n**Notable:** Defensive Stance at 10, Berserker Stance at 30. Whirlwind Axe quest at 30.",
            "rogue": "\n**Notable:** Poisons trainable at 20. Thistle Tea recipe quest available.",
            "priest": "\n**Notable:** Racial priest quests for unique spells at various levels.",
            "mage": "\n**Notable:** Teleport spells from trainers, Portal spells at higher levels.",
            "death knight": "\n**Notable:** Start at 55 in Acherus. Complete the starting zone to unlock talents and mount."
        }

        if player_class in notable_quests:
            result += notable_quests[player_class]

        result += "\n\nIMPORTANT: Include the [[quest:...]] markers exactly as shown - they become clickable links!"
        return result

    def _get_quest_chain(self, params: dict) -> str:
        """Get the full quest chain for a quest."""
        quest_name = params.get("quest_name", "")

        if not quest_name:
            return "Please specify a quest name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        candidates = self._search_quest_candidates(
            cursor, quest_name
        )
        if not candidates:
            cursor.close()
            conn.close()
            return f"Quest '{quest_name}' not found."

        if self._is_ambiguous_top_match(candidates):
            result = self._format_quest_clarification(
                quest_name, candidates
            )
            cursor.close()
            conn.close()
            return result

        cursor.execute("""
            SELECT qt.ID, qt.LogTitle, qt.QuestLevel,
                   qt.MinLevel, qt.RewardNextQuest,
                   COALESCE(qta.PrevQuestID, 0)
                   AS PrevQuestID
            FROM quest_template qt
            LEFT JOIN quest_template_addon qta
                ON qt.ID = qta.ID
            WHERE qt.ID = %s
            LIMIT 1
        """, (candidates[0]['ID'],))

        quest = cursor.fetchone()

        if not quest:
            cursor.close()
            conn.close()
            return f"Quest '{quest_name}' not found."

        chain_start_id = quest['ID']
        visited = {chain_start_id}

        while True:
            cursor.execute("""
                SELECT qt.ID, qt.LogTitle, qt.QuestLevel, qt.RewardNextQuest,
                       COALESCE(qta.PrevQuestID, 0) AS PrevQuestID
                FROM quest_template qt
                LEFT JOIN quest_template_addon qta ON qt.ID = qta.ID
                WHERE qt.ID = %s
            """, (chain_start_id,))

            prev_quest = cursor.fetchone()
            if not prev_quest or prev_quest['PrevQuestID'] <= 0:
                break

            if prev_quest['PrevQuestID'] in visited:
                break

            chain_start_id = prev_quest['PrevQuestID']
            visited.add(chain_start_id)

            if len(visited) > 30:
                break

        chain = []
        current_id = chain_start_id
        visited_forward = set()

        while current_id and current_id not in visited_forward:
            visited_forward.add(current_id)

            cursor.execute("""
                SELECT qt.ID, qt.LogTitle, qt.QuestLevel, qt.MinLevel, qt.RewardNextQuest,
                       ct.name AS QuestGiver
                FROM quest_template qt
                LEFT JOIN creature_queststarter cqs ON qt.ID = cqs.quest
                LEFT JOIN creature_template ct ON cqs.id = ct.entry
                WHERE qt.ID = %s
                LIMIT 1
            """, (current_id,))

            chain_quest = cursor.fetchone()
            if not chain_quest:
                break

            chain.append(chain_quest)
            current_id = chain_quest['RewardNextQuest']

            if len(chain) > 30:
                break

        cursor.close()
        conn.close()

        if not chain:
            return f"Could not build quest chain for '{quest_name}'."

        search_position = -1
        for i, q in enumerate(chain):
            if q['ID'] == quest['ID']:
                search_position = i
                break

        result = f"**Quest Chain** ({len(chain)} quests):\n\n"

        for i, q in enumerate(chain):
            lvl = q['QuestLevel'] if q['QuestLevel'] > 0 else q['MinLevel']
            quest_link = f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]"

            marker = " <- (this quest)" if i == search_position else ""
            giver = f" from {q['QuestGiver']}" if q['QuestGiver'] else ""

            result += f"{i+1}. {quest_link} (Level {lvl}){giver}{marker}\n"

        if len(chain) == 1:
            result += "\nThis quest is not part of a chain (standalone quest)."
        else:
            result += f"\nChain has {len(chain)} quests total."

        result += "\n\nIMPORTANT: Include the [[quest:...]] markers exactly as shown - they become clickable links!"
        return result
