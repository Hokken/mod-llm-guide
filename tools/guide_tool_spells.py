"""Spell lookup domain for mod-llm-guide."""

from spell_names import SPELL_NAMES, SPELL_DESCRIPTIONS


class GuideToolSpellMixin:
    """Spell lookup and trainer-query behavior."""

    def _search_spell_name_groups(
        self, spell_name: str,
        limit: int = 8
    ) -> list[dict]:
        groups = {}
        for spell_id, display_name in SPELL_NAMES.items():
            score = self._score_name_match(
                spell_name, display_name
            )
            if score <= 0:
                continue
            normalized = self._normalize_lookup_text(
                display_name
            )
            existing = groups.get(normalized)
            if not existing:
                groups[normalized] = {
                    'name': display_name,
                    'normalized_name': normalized,
                    'score': score,
                    'spell_ids': [spell_id],
                }
                continue

            existing['spell_ids'].append(spell_id)
            if score > existing['score']:
                existing['score'] = score
                existing['name'] = display_name

        results = list(groups.values())
        results.sort(
            key=lambda row: (
                -row['score'],
                len(row['name']),
                row['name'],
            )
        )
        return results[:limit]

    def _get_spell_info(self, params: dict) -> str:
        """Get class spell training info from trainer data."""
        spell_name = params.get("spell_name", "").lower()
        player_class = params.get("player_class", "").lower()

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        spell_groups = self._search_spell_name_groups(
            spell_name
        )
        if not spell_groups:
            cursor.close()
            conn.close()
            return (
                f"Spell '{spell_name}' not found in "
                f"database. This might be a talent or "
                f"special ability."
            )

        if self._is_ambiguous_top_match(spell_groups):
            cursor.close()
            conn.close()
            result = (
                f"I found multiple spells matching "
                f"'{spell_name}'. Please clarify "
                f"which one you mean:\n"
            )
            for group in spell_groups[:5]:
                spell_id = min(group['spell_ids'])
                spell_link = (
                    f"[[spell:{spell_id}:"
                    f"{group['name']}]]"
                )
                result += f"- {spell_link}\n"
            result += (
                "\nIMPORTANT: Include the "
                "[[spell:...]] markers exactly "
                "as shown in your response - they "
                "become clickable spell links!"
            )
            return result

        best_group = spell_groups[0]
        spell_ids = best_group['spell_ids'][:20]
        placeholders = ", ".join(
            ["%s"] * len(spell_ids)
        )
        class_id = self.CLASS_IDS.get(player_class)

        query = f"""
            SELECT DISTINCT ts.SpellId, ts.ReqLevel,
                   ts.MoneyCost
            FROM trainer_spell ts
            JOIN trainer t ON t.Id = ts.TrainerId
            WHERE ts.SpellId IN ({placeholders})
              AND t.Type = 0
        """
        sql_params = list(spell_ids)
        if class_id:
            query += " AND t.Requirement = %s"
            sql_params.append(class_id)

        cursor.execute(query, sql_params)
        spell_rows = cursor.fetchall()

        if not spell_rows and class_id:
            cursor.execute(f"""
                SELECT DISTINCT ts.SpellId, ts.ReqLevel,
                       ts.MoneyCost, t.Requirement
                FROM trainer_spell ts
                JOIN trainer t ON t.Id = ts.TrainerId
                WHERE ts.SpellId IN ({placeholders})
                  AND t.Type = 0
            """, spell_ids)
            other_class_rows = cursor.fetchall()
            cursor.close()
            conn.close()

            if other_class_rows:
                return (
                    f"{best_group['name']} is a "
                    f"trainer-taught class spell, but "
                    f"not for {player_class.title()}."
                )
            return (
                f"'{best_group['name']}' appears "
                f"to be a talent, quest ability, or "
                f"automatically learned spell, not "
                f"something taught by a class trainer."
            )

        cursor.close()
        conn.close()

        if not spell_rows:
            return (
                f"'{best_group['name']}' appears to "
                f"be a talent or automatically "
                f"learned ability, not trained "
                f"from a trainer."
            )

        spell_rows.sort(
            key=lambda row: (
                row['ReqLevel'],
                row['MoneyCost'],
                row['SpellId'],
            )
        )
        spell_data = spell_rows[0]
        spell_id = spell_data['SpellId']

        level = spell_data['ReqLevel']
        cost = spell_data['MoneyCost']

        if cost >= 10000:
            cost_str = f"{cost // 10000}g {(cost % 10000) // 100}s" if cost % 10000 >= 100 else f"{cost // 10000}g"
        elif cost >= 100:
            cost_str = f"{cost // 100}s"
        else:
            cost_str = f"{cost}c"

        spell_link = (
            f"[[spell:{spell_id}:"
            f"{best_group['name']}]]"
        )
        desc = SPELL_DESCRIPTIONS.get(spell_id, "")
        result = (
            f"Spell: {spell_link}\n"
            f"Available at level: {level}\n"
            f"Training cost: {cost_str}"
        )
        if player_class:
            result += (
                f"\nClass: "
                f"{player_class.title()}"
            )
        if desc:
            result += f"\nDescription: {desc}"
        result += (
            "\nVisit your class trainer to learn "
            "this spell.\n\nIMPORTANT: Include "
            "the [[spell:...]] marker exactly "
            "as shown in your response - it "
            "becomes a clickable spell link!"
        )
        return result

    def _list_spells_by_level(self, params: dict) -> str:
        """List spells available at a specific level for a class."""
        player_class = params.get("player_class", "").lower()
        level = params.get("level", 1)

        class_id = self.CLASS_IDS.get(player_class)
        if not class_id:
            return f"Unknown class: {player_class}. Try: warrior, paladin, hunter, rogue, priest, shaman, mage, warlock, druid, death knight."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute("""
                SELECT DISTINCT ts.SpellId, ts.ReqLevel, ts.MoneyCost,
                       COALESCE(sd.Name_Lang_enUS, NULL) as spell_name
                FROM trainer t
                JOIN trainer_spell ts ON t.Id = ts.TrainerId
                LEFT JOIN spell_dbc sd ON ts.SpellId = sd.ID
                WHERE t.Type = 0 AND t.Requirement = %s
                  AND ts.ReqLevel = %s
                ORDER BY ts.SpellId
                LIMIT 20
            """, (class_id, level))
            spells = cursor.fetchall()
        except Exception:
            cursor.execute("""
                SELECT DISTINCT ts.SpellId, ts.ReqLevel, ts.MoneyCost
                FROM trainer t
                JOIN trainer_spell ts ON t.Id = ts.TrainerId
                WHERE t.Type = 0 AND t.Requirement = %s
                  AND ts.ReqLevel = %s
                ORDER BY ts.SpellId
                LIMIT 20
            """, (class_id, level))
            spells = [dict(row, spell_name=None) for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        if not spells:
            return f"No new spells available for {player_class} at level {level}. Check nearby levels."

        result = f"Spells available for {player_class.title()} at level {level}:\n"
        for s in spells:
            spell_id = s['SpellId']
            name = s.get('spell_name') or SPELL_NAMES.get(spell_id) or "Spell"
            desc = SPELL_DESCRIPTIONS.get(spell_id, "")
            cost = s['MoneyCost']
            if cost >= 10000:
                cost_str = f"{cost // 10000}g"
            elif cost >= 100:
                cost_str = f"{cost // 100}s"
            else:
                cost_str = f"{cost}c"
            spell_link = f"[[spell:{spell_id}:{name.title()}]]"
            result += f"- {spell_link} ({cost_str})"
            if desc:
                result += f" - {desc}"
            result += "\n"

        result += "\nIMPORTANT: Include the [[spell:...]] markers exactly as shown in your response - they become clickable spell links!"
        return result
