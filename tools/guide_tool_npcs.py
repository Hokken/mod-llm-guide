"""NPC and creature lookup domain for mod-llm-guide."""

from zone_coordinates import world_to_map_coords


class GuideToolNpcMixin:
    """NPC, vendor, trainer, and creature lookups.

    Requires the composed executor to provide:
    `default_zone`, `get_connection()`, `_get_zone_filter()`,
    `_distance_order_params()`, and `format_distance_direction()`.
    """

    ITEM_CLASS_MAP = {
        'arrow': (6, 2), 'arrows': (6, 2),
        'bullet': (6, 3), 'bullets': (6, 3),
        'bow': (2, 2), 'bows': (2, 2),
        'gun': (2, 3), 'guns': (2, 3),
        'crossbow': (2, 18), 'crossbows': (2, 18),
        'thrown': (2, 16), 'throwing': (2, 16),
        'food': (0, 5), 'drink': (0, 5),
        'water': (0, 5), 'bread': (0, 5),
        'bandage': (0, 7), 'bandages': (0, 7),
        'potion': (0, 1), 'potions': (0, 1),
        'elixir': (0, 2), 'flask': (0, 3),
        'scroll': (0, 4), 'scrolls': (0, 4),
        'reagent': (5, 0), 'reagents': (5, 0),
        'bag': (1, 0), 'bags': (1, 0),
        'herb': (7, 9), 'herbs': (7, 9),
        'cloth': (7, 5), 'leather': (7, 6),
        'ore': (7, 7), 'metal': (7, 7),
    }

    ITEM_NAME_MAP = {
        'poison': ['Poison'],
        'pet food': ['Pet Food', 'Chunk of Boar Meat'],
        'vial': ['Vial', 'Empty Vial'],
        'thread': ['Thread'],
        'dye': ['Dye'],
        'mining pick': ['Mining Pick'],
        'skinning knife': ['Skinning Knife'],
        'fishing pole': ['Fishing Pole'],
    }

    TRAINER_PATTERNS = {
        'hunter': '%Hunter%', 'warrior': '%Warrior%', 'mage': '%Mage%',
        'priest': '%Priest%', 'rogue': '%Rogue%', 'warlock': '%Warlock%',
        'druid': '%Druid%', 'paladin': '%Paladin%', 'shaman': '%Shaman%',
        'death knight': '%Death Knight%',
        'leatherworking': '%Leatherworking%', 'blacksmithing': '%Blacksmith%',
        'tailoring': '%Tailor%', 'engineering': '%Engineer%',
        'alchemy': '%Alchem%', 'enchanting': '%Enchant%',
        'mining': '%Mining%', 'herbalism': '%Herb%', 'skinning': '%Skinning%',
        'cooking': '%Cook%', 'cook': '%Cook%',
        'fishing': '%Fishing%', 'first aid': '%First Aid%',
        'inscription': '%Inscription%', 'jewelcrafting': '%Jewel%',
        'riding': '%Riding%', 'pet': '%Pet%',
    }

    SERVICE_PATTERNS = {
        'stable master': '%Stable Master%', 'stable': '%Stable Master%',
        'innkeeper': '%Innkeeper%', 'inn': '%Innkeeper%',
        'flight master': '%Flight Master%', 'flight': '%Flight Master%',
        'banker': '%Banker%', 'bank': '%Banker%',
        'auctioneer': '%Auctioneer%', 'auction': '%Auctioneer%',
        'barber': '%Barber%',
        'repair': '%Repair%', 'armorer': '%Armor%',
        'guild master': '%Guild Master%',
    }

    def _find_vendor(self, params: dict) -> str:
        """Find vendors selling specific items."""
        item_type = params.get("item_type", "").lower()
        zone = params.get("zone", "").lower()

        zone_coords, zone_filter = self._get_zone_filter(zone)

        if item_type in ('general', 'supplies', 'any', 'vendor', 'junk', 'sell'):
            dist_cols, order, sel_params, \
                ord_params, dist_active = \
                self._distance_order_params()
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"""
                SELECT DISTINCT ct.entry as vendor_entry, ct.name as vendor_name, ct.subname as title,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                       na.area_name
                       {dist_cols}
                FROM creature_template ct
                JOIN creature c ON ct.entry = c.id1
                LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
                WHERE (ct.subname LIKE '%Supplies%' OR ct.subname LIKE '%Goods%' OR ct.subname LIKE '%Merchant%')
                  AND ct.npcflag & 128 > 0 {zone_filter}
                {order}
                LIMIT 5
            """, (*sel_params, *ord_params))
            vendors = cursor.fetchall()
            cursor.close()
            conn.close()

            if not vendors:
                return f"No general vendor found in {zone or 'the area'}."

            hint = " (closest first)" if dist_active else ""
            result = (
                f"General vendors in "
                f"{zone or 'the area'}{hint}:\n"
            )
            for v in vendors:
                npc_link = f"[[npc:{v['vendor_entry']}:{v['vendor_name']}]]"
                title = f" ({v['title']})" if v['title'] else ""
                dist_info = self.format_distance_direction(v['pos_x'], v['pos_y'], v['map_id'])
                dist_str = f" ({dist_info})" if dist_info else ""
                loc = (f" in {v['area_name']}"
                       if v.get('area_name') else "")
                coords = ""
                coord_zone = zone if zone_coords else self.default_zone
                if coord_zone and v['pos_x'] and v['pos_y']:
                    map_coords = world_to_map_coords(coord_zone, v['pos_x'], v['pos_y'])
                    if map_coords:
                        coords = f" at {map_coords[0]}, {map_coords[1]}"
                result += f"- {npc_link}{title}{loc}{dist_str}{coords}\n"
            result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
            return result

        if "supplies" in item_type:
            return self._find_vendor_by_subname(
                item_type, zone, zone_coords, zone_filter
            )

        class_filters = []
        _, class_info = self._fuzzy_dict_match(
            item_type, self.ITEM_CLASS_MAP
        )
        if class_info is not None:
            if isinstance(class_info, list):
                class_filters = class_info
            else:
                class_filters = [class_info]

        _, name_patterns = self._fuzzy_dict_match(
            item_type, self.ITEM_NAME_MAP
        )
        if not name_patterns:
            name_patterns = []

        if not class_filters and not name_patterns:
            return self._find_vendor_by_subname(
                item_type, zone, zone_coords, zone_filter
            )

        dist_cols, order, sel_params, \
            ord_params, dist_active = \
            self._distance_order_params()

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        vendors = []

        if class_filters:
            conditions = [f"(it.class = {c} AND it.subclass = {s})" for c, s in class_filters]
            cursor.execute(f"""
                SELECT DISTINCT ct.entry as vendor_entry, ct.name as vendor_name, ct.subname as title,
                       GROUP_CONCAT(DISTINCT it.name ORDER BY it.name SEPARATOR ', ') as items,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                       na.area_name
                       {dist_cols}
                FROM npc_vendor nv
                JOIN creature_template ct ON nv.entry = ct.entry
                JOIN creature c ON ct.entry = c.id1
                JOIN item_template it ON nv.item = it.entry
                LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
                WHERE ({' OR '.join(conditions)}) {zone_filter}
                GROUP BY ct.entry, c.position_x, c.position_y, c.map, na.area_name
                {order}
                LIMIT 5
            """, (*sel_params, *ord_params))
            vendors = cursor.fetchall()

        if not vendors and name_patterns:
            placeholders = ' OR '.join(['it.name LIKE %s'] * len(name_patterns))
            cursor.execute(f"""
                SELECT DISTINCT ct.entry as vendor_entry, ct.name as vendor_name, ct.subname as title,
                       GROUP_CONCAT(DISTINCT it.name ORDER BY it.name SEPARATOR ', ') as items,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                       na.area_name
                       {dist_cols}
                FROM npc_vendor nv
                JOIN creature_template ct ON nv.entry = ct.entry
                JOIN creature c ON ct.entry = c.id1
                JOIN item_template it ON nv.item = it.entry
                LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
                WHERE ({placeholders}) {zone_filter}
                GROUP BY ct.entry, c.position_x, c.position_y, c.map, na.area_name
                {order}
                LIMIT 5
            """, (*sel_params, *[f"%{p}%" for p in name_patterns], *ord_params))
            vendors = cursor.fetchall()

        cursor.close()
        conn.close()

        if not vendors:
            return self._find_vendor_by_subname(
                item_type, zone, zone_coords,
                zone_filter
            )

        hint = " (closest first)" if dist_active else ""
        result = f"Vendors selling {item_type} in {zone or 'the world'}{hint}:\n"
        for v in vendors:
            title = f" ({v['title']})" if v['title'] else ""
            items = v['items'][:80] + "..." if len(v['items']) > 80 else v['items']
            npc_link = f"[[npc:{v['vendor_entry']}:{v['vendor_name']}]]"

            dist_info = self.format_distance_direction(v['pos_x'], v['pos_y'], v['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            loc = (f" in {v['area_name']}"
                   if v.get('area_name') else "")
            coords = ""
            coord_zone = zone if zone_coords else self.default_zone
            if coord_zone and v['pos_x'] and v['pos_y']:
                map_coords = world_to_map_coords(
                    coord_zone, v['pos_x'], v['pos_y']
                )
                if map_coords:
                    coords = (
                        f" at {map_coords[0]}, "
                        f"{map_coords[1]}"
                    )
            result += f"- {npc_link}{title}{loc}{dist_str}{coords}: {items}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _find_vendor_by_subname(
        self, item_type, zone, zone_coords, zone_filter
    ):
        """Find vendors by creature_template.subname."""
        dist_cols, order, sel_params, \
            ord_params, dist_active = \
            self._distance_order_params()

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT DISTINCT
                ct.entry as vendor_entry,
                ct.name as vendor_name,
                ct.subname as title,
                c.position_x as pos_x,
                c.position_y as pos_y,
                c.map as map_id,
                na.area_name,
                na.zone_name as npc_zone
                {dist_cols}
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            LEFT JOIN llm_guide_npc_areas na
                ON na.creature_guid = c.guid
            WHERE ct.subname LIKE %s
              AND ct.npcflag & 128 > 0
              {zone_filter}
            {order}
            LIMIT 5
        """, (*sel_params, f"%{item_type}%",
              *ord_params))
        vendors = cursor.fetchall()
        cursor.close()
        conn.close()

        if not vendors:
            return (
                f"No vendors for '{item_type}' "
                f"found in "
                f"{zone or 'the world'}."
            )

        hint = (
            " (closest first)"
            if dist_active else ""
        )
        result = (
            f"Vendors for {item_type} in "
            f"{zone or 'the world'}{hint}:\n"
        )
        for v in vendors:
            npc_link = (
                f"[[npc:{v['vendor_entry']}"
                f":{v['vendor_name']}]]"
            )
            title = (
                f" ({v['title']})"
                if v['title'] else ""
            )
            dist_info = (
                self.format_distance_direction(
                    v['pos_x'], v['pos_y'],
                    v['map_id'])
            )
            dist_str = (
                f" ({dist_info})"
                if dist_info else ""
            )
            loc = (
                f" in {v['area_name']}"
                if v.get('area_name') else ""
            )
            coords = ""
            if v['pos_x'] and v['pos_y']:
                coord_zone = (
                    zone if zone_coords
                    else v.get('npc_zone', '')
                )
                if coord_zone:
                    map_coords = world_to_map_coords(
                        coord_zone,
                        v['pos_x'], v['pos_y']
                    )
                    if map_coords:
                        coords = (
                            f" at {map_coords[0]}"
                            f", {map_coords[1]}"
                        )
            result += (
                f"- {npc_link}{title}"
                f"{loc}{dist_str}{coords}\n"
            )
        result += (
            "\nIMPORTANT: Include the [[npc:...]] "
            "markers exactly as shown - they "
            "become colored NPC links!"
        )
        return result

    def _find_trainer(self, params: dict) -> str:
        """Find class or profession trainers."""
        trainer_type = params.get("trainer_type", "").lower()
        zone = params.get("zone", "").lower()

        _, pattern = self._fuzzy_dict_match(
            trainer_type, self.TRAINER_PATTERNS
        )
        if not pattern:
            return f"Unknown trainer type: {trainer_type}. Try: hunter, warrior, mage, leatherworking, mining, cooking, etc."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        dist_cols, order, sel_params, \
            ord_params, dist_active = \
            self._distance_order_params()

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT DISTINCT ct.entry as trainer_entry, ct.name as trainer_name, ct.subname as title,
                   c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                   na.area_name
                   {dist_cols}
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
            WHERE ct.subname LIKE %s AND ct.npcflag & 16 > 0 {zone_filter}
            {order}
            LIMIT 5
        """, (*sel_params, pattern, *ord_params))

        trainers = cursor.fetchall()
        cursor.close()
        conn.close()

        if not trainers:
            return f"No {trainer_type} trainer found in {zone or 'the world'}."

        hint = " (closest first)" if dist_active else ""
        result = f"{trainer_type.title()} trainers in {zone or 'the world'}{hint}:\n"
        for t in trainers:
            npc_link = f"[[npc:{t['trainer_entry']}:{t['trainer_name']}]]"

            dist_info = self.format_distance_direction(t['pos_x'], t['pos_y'], t['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            loc = (f" in {t['area_name']}"
                   if t.get('area_name') else "")
            coords = ""
            coord_zone = zone if zone_coords else self.default_zone
            if coord_zone and t['pos_x'] and t['pos_y']:
                map_coords = world_to_map_coords(coord_zone, round(t['pos_x'], 1), round(t['pos_y'], 1))
                if map_coords:
                    coords = f" at {map_coords[0]}, {map_coords[1]}"
            result += f"- {npc_link} ({t['title']}){loc}{dist_str}{coords}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _find_service_npc(self, params: dict) -> str:
        """Find service NPCs."""
        service_type = params.get("service_type", "").lower()
        zone = params.get("zone", "").lower()

        _, pattern = self._fuzzy_dict_match(
            service_type, self.SERVICE_PATTERNS
        )
        if not pattern:
            return f"Unknown service: {service_type}. Try: stable master, innkeeper, flight master, banker, auctioneer."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        dist_cols, order, sel_params, \
            ord_params, dist_active = \
            self._distance_order_params()

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT DISTINCT ct.entry as npc_entry, ct.name as npc_name, ct.subname as title,
                   c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                   na.area_name
                   {dist_cols}
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
            WHERE ct.subname LIKE %s {zone_filter}
            {order}
            LIMIT 5
        """, (*sel_params, pattern, *ord_params))

        npcs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not npcs:
            return f"No {service_type} found in {zone or 'the world'}."

        hint = " (closest first)" if dist_active else ""
        result = f"{service_type.title()} in {zone or 'the world'}{hint}:\n"
        for n in npcs:

            dist_info = self.format_distance_direction(n['pos_x'], n['pos_y'], n['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            loc = (f" in {n['area_name']}"
                   if n.get('area_name') else "")
            coords = ""
            coord_zone = zone if zone_coords else self.default_zone
            if coord_zone and n['pos_x'] and n['pos_y']:
                map_coords = world_to_map_coords(coord_zone, round(n['pos_x'], 1), round(n['pos_y'], 1))
                if map_coords:
                    coords = f" at {map_coords[0]}, {map_coords[1]}"
            npc_link = f"[[npc:{n['npc_entry']}:{n['npc_name']}]]"
            result += f"- {npc_link}{loc}{dist_str}{coords}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _find_npc(self, params: dict) -> str:
        """Find a specific NPC by name."""
        npc_name = params.get("npc_name", "")
        zone = params.get("zone", "").lower() if params.get("zone") else None

        if not npc_name:
            return "Please specify an NPC name to search for."

        zone_coords, zone_filter = self._get_zone_filter(zone) if zone else (None, "")
        dist_cols, order, sel_params, \
            ord_params, dist_active = \
            self._distance_order_params()

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT DISTINCT ct.entry as npc_entry, ct.name as npc_name, ct.subname as title,
                   c.position_x as pos_x, c.position_y as pos_y, c.map as map_id,
                   na.area_name
                   {dist_cols}
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            LEFT JOIN llm_guide_npc_areas na ON na.creature_guid = c.guid
            WHERE ct.name LIKE %s {zone_filter}
            {order}
            LIMIT 5
        """, (*sel_params, f"%{npc_name}%", *ord_params))

        npcs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not npcs:
            return f"No NPC named '{npc_name}' found{' in ' + zone if zone else ''}."

        hint = " (closest first)" if dist_active else ""
        result = f"Found NPC(s) matching '{npc_name}'{hint}:\n"
        for n in npcs:
            title = f" ({n['title']})" if n['title'] else ""

            dist_info = self.format_distance_direction(n['pos_x'], n['pos_y'], n['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            loc = (f" in {n['area_name']}"
                   if n.get('area_name') else "")
            coords = ""
            coord_zone = zone if zone_coords else self.default_zone
            if coord_zone and n['pos_x'] and n['pos_y']:
                map_coords = world_to_map_coords(coord_zone, round(n['pos_x'], 1), round(n['pos_y'], 1))
                if map_coords:
                    coords = f" at {map_coords[0]}, {map_coords[1]}"
            npc_link = f"[[npc:{n['npc_entry']}:{n['npc_name']}]]"
            result += f"- {npc_link}{title}{loc}{dist_str}{coords}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _find_creature(self, params: dict) -> str:
        """Find creatures/mobs."""
        creature_name = params.get("creature_name", "")
        zone = params.get("zone", "").lower() if params.get("zone") else None

        if not creature_name:
            return "Please specify a creature name to search for."

        zone_coords, zone_filter = self._get_zone_filter(zone) if zone else (None, "")

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT DISTINCT ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.`rank`
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE ct.name LIKE %s {zone_filter}
            LIMIT 10
        """, (f"%{creature_name}%",))

        creatures = cursor.fetchall()
        cursor.close()
        conn.close()

        if not creatures:
            return f"No creatures named '{creature_name}' found{' in ' + zone if zone else ''}."

        rank_names = {0: '', 1: ' (Elite)', 2: ' (Rare Elite)', 3: ' (Boss)', 4: ' (Rare)'}

        result = f"Creatures matching '{creature_name}':\n"
        for c in creatures:
            lvl = f"Level {c['minlevel']}" if c['minlevel'] == c['maxlevel'] else f"Level {c['minlevel']}-{c['maxlevel']}"
            rank = rank_names.get(c['rank'], '')
            npc_link = f"[[npc:{c['entry']}:{c['name']}]]"
            result += f"- {npc_link} - {lvl}{rank}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored links!"
        return result
