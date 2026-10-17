"""Deterministic item requirements and stat comparisons (3.3.5)."""

STAT_NAMES = {
    0: "Mana", 1: "Health", 3: "Agility", 4: "Strength", 5: "Intellect",
    6: "Spirit", 7: "Stamina", 12: "Defense", 13: "Dodge", 14: "Parry",
    15: "Block", 16: "Melee hit", 17: "Ranged hit", 18: "Spell hit",
    19: "Melee crit", 20: "Ranged crit", 21: "Spell crit", 28: "Melee haste",
    29: "Ranged haste", 30: "Spell haste", 31: "Hit", 32: "Crit",
    35: "Resilience", 36: "Haste", 37: "Expertise", 38: "Attack power",
    39: "Ranged attack power", 43: "Mana per 5", 44: "Armor penetration",
    45: "Spell power", 47: "Spell penetration", 48: "Block value",
}

# Proficiency IDs follow Item::GetSkill / ItemTemplate::GetSkill.
WEAPON_SKILLS = {
    0: 44, 1: 172, 2: 45, 3: 46, 4: 54, 5: 160, 6: 229, 7: 43,
    8: 55, 10: 136, 13: 473, 15: 173, 16: 176, 18: 226, 19: 228,
    20: 356,
}
ARMOR_SKILLS = {1: 415, 2: 414, 3: 413, 4: 293, 6: 433}

DEFAULT_ROLE_STATS = {
    'tank': [4, 7, 12, 13, 14, 15, 48],
    'healer': [5, 6, 43, 45],
    'melee': [3, 4, 37, 38],
    'ranged': [3, 38, 39],
    'caster': [5, 18, 21, 30, 45],
}


def item_stats(item):
    result = {}
    for index in range(1, 11):
        stat = int(item.get(f"stat_type{index}", 0))
        value = int(item.get(f"stat_value{index}", 0))
        if value:
            result[stat] = result.get(stat, 0) + value
    return result


def stat_deltas(current, candidate):
    before, after = item_stats(current), item_stats(candidate)
    changes = []
    for stat in sorted(before.keys() | after.keys()):
        delta = after.get(stat, 0) - before.get(stat, 0)
        if delta:
            changes.append(f"{delta:+d} {STAT_NAMES.get(stat, f'Stat {stat}')}")
    armor = candidate.get('armor', 0) - current.get('armor', 0)
    if armor:
        changes.append(f"{armor:+d} armor")
    def dps(item):
        delay = item.get('delay', 0)
        return (sum(item.get(f'dmg_{bound}{index}', 0)
                    for index in (1, 2) for bound in ('min', 'max'))
                * 500 / delay if delay else 0)
    damage = dps(candidate) - dps(current)
    if damage:
        changes.append(f"{damage:+.1f} weapon DPS")
    return ", ".join(changes) or "No base stat change"


def meets_requirements(item, snapshot):
    """Conservative known requirements; never imply complete equip checks."""
    if snapshot is None:
        return False
    for field, key in (("AllowableClass", "class_mask"),
                       ("AllowableRace", "race_mask")):
        if not (int(item.get(field, -1)) & snapshot[key]):
            return False
    if item.get('RequiredLevel', 0) > snapshot['level']:
        return False
    skills = snapshot['skills']
    proficiency = (WEAPON_SKILLS if item['class'] == 2 else
                   ARMOR_SKILLS if item['class'] == 4 else {}).get(
                       item['subclass'])
    if proficiency and not skills.get(str(proficiency), 0):
        return False
    skill = item.get('RequiredSkill', 0)
    if skill and skills.get(str(skill), 0) < max(
            1, item.get('RequiredSkillRank', 0)):
        return False
    spell = item.get('requiredspell', 0)
    if spell and spell not in snapshot['known_spells']:
        return False
    faction = item.get('RequiredReputationFaction', 0)
    if faction:
        standing = snapshot['reputation'].get(str(faction))
        # Minimum standing for each of the eight reputation ranks.
        thresholds = (-42000, -6000, -3000, 0, 3000, 9000, 21000, 42000)
        rank = item.get('RequiredReputationRank', 0)
        if standing is None or rank not in range(8) or standing < thresholds[rank]:
            return False
    # Holiday and obsolete PvP requirements need runtime checks we lack.
    if any(item.get(key, 0) for key in
           ('HolidayId', 'requiredhonorrank', 'RequiredCityRank')):
        return False
    flags = item.get('FlagsExtra', 0)
    alliance = bool(snapshot['race_mask'] & 1101)
    if (flags & 1 and alliance) or (flags & 2 and not alliance):
        return False
    return True
