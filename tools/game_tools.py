"""
Game data tools for Claude tool use.
Defines tools that Claude can call to query the WoW database.
"""

import logging
from typing import Any
from zone_coordinates import get_zone_coordinates, get_zone_id, world_to_map_coords, ZONE_COORDINATES
from spell_names import SPELL_NAMES, SPELL_DESCRIPTIONS

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL DEFINITIONS (Anthropic format)
# =============================================================================

GAME_TOOLS = [
    {
        "name": "find_vendor",
        "description": "Find vendors selling specific items in a zone. Returns NPC names with [[npc:ID:Name]] markers that become colored links in-game. IMPORTANT: Include these [[npc:...]] markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_type": {
                    "type": "string",
                    "description": "Type of item to find (e.g., 'arrows', 'food', 'drink', 'reagents', 'bags', 'ammo', 'bandages', 'potions', 'poison', 'pet food')"
                },
                "zone": {
                    "type": "string",
                    "description": "Zone name to search in (e.g., 'darkshore', 'stormwind', 'orgrimmar')"
                }
            },
            "required": ["item_type", "zone"]
        }
    },
    {
        "name": "find_trainer",
        "description": "Find class or profession trainers in a zone. Returns NPC names with [[npc:ID:Name]] markers. IMPORTANT: Include these [[npc:...]] markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trainer_type": {
                    "type": "string",
                    "description": "Type of trainer (e.g., 'hunter', 'warrior', 'mage', 'leatherworking', 'mining', 'cooking', 'first aid', 'riding')"
                },
                "zone": {
                    "type": "string",
                    "description": "Zone name to search in"
                }
            },
            "required": ["trainer_type", "zone"]
        }
    },
    {
        "name": "find_service_npc",
        "description": "Find service NPCs like stable masters, innkeepers, flight masters, bankers, auctioneers. Returns [[npc:ID:Name]] markers. IMPORTANT: Include these markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "description": "Type of service (e.g., 'stable master', 'innkeeper', 'flight master', 'banker', 'auctioneer', 'barber', 'repair')"
                },
                "zone": {
                    "type": "string",
                    "description": "Zone name to search in"
                }
            },
            "required": ["service_type", "zone"]
        }
    },
    {
        "name": "find_npc",
        "description": "Find a specific NPC by name and get their exact map coordinates. Returns [[npc:ID:Name]] markers with coordinates like '45.2, 67.8'. Use this when players ask WHERE an NPC is or want coordinates/location. IMPORTANT: Include these markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "npc_name": {
                    "type": "string",
                    "description": "Name or partial name of the NPC to find"
                },
                "zone": {
                    "type": "string",
                    "description": "Zone name to search in (optional, but helps narrow results)"
                }
            },
            "required": ["npc_name"]
        }
    },
    {
        "name": "get_spell_info",
        "description": "Get information about when a spell/ability is learned and its training cost. Use this when the player asks about learning spells, what level they get an ability, or training costs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spell_name": {
                    "type": "string",
                    "description": "Name of the spell or ability (e.g., 'charge', 'fireball', 'stealth', 'feign death')"
                },
                "player_class": {
                    "type": "string",
                    "description": "Player's class to help identify the correct spell (e.g., 'hunter', 'warrior', 'mage')"
                }
            },
            "required": ["spell_name"]
        }
    },
    {
        "name": "list_spells_by_level",
        "description": "List spells available at a specific level for a class. Use this when the player asks what spells they can learn at their level or what abilities are available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_class": {
                    "type": "string",
                    "description": "The player's class (e.g., 'hunter', 'warrior', 'mage', 'priest')"
                },
                "level": {
                    "type": "integer",
                    "description": "The level to check for available spells"
                }
            },
            "required": ["player_class", "level"]
        }
    },
    {
        "name": "find_quest_giver",
        "description": "Find quest givers in a zone or find who gives a specific quest. Use this when the player asks about quests or quest givers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to search for quest givers"
                },
                "quest_name": {
                    "type": "string",
                    "description": "Optional: specific quest name to find the giver for"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_available_quests",
        "description": "Find quests available to a player at their current level in a specific zone. Use this when the player asks what quests they can do, what's available at their level, or what new quests are in an area. This filters to quests the player can actually pick up NOW based on their level and class.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to search for available quests (e.g., 'darnassus', 'darkshore', 'stormwind')"
                },
                "player_level": {
                    "type": "integer",
                    "description": "The player's current level - only quests with MinLevel <= this will be shown"
                },
                "player_class": {
                    "type": "string",
                    "description": "The player's class (e.g., 'hunter', 'warrior', 'rogue') to filter class-specific quests"
                },
                "faction": {
                    "type": "string",
                    "description": "Player faction: 'alliance' or 'horde' to filter faction-specific quests"
                }
            },
            "required": ["zone", "player_level"]
        }
    },
    {
        "name": "find_creature",
        "description": "Find creatures/mobs in a zone. Returns [[npc:ID:Name]] markers. IMPORTANT: Include these markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "creature_name": {
                    "type": "string",
                    "description": "Name or partial name of the creature"
                },
                "zone": {
                    "type": "string",
                    "description": "Zone name to search in"
                }
            },
            "required": ["creature_name"]
        }
    },
    {
        "name": "get_quest_info",
        "description": "Get detailed information about a quest including objectives, rewards, and who gives/accepts it. Use this when the player asks about a specific quest, what they need to do for a quest, quest rewards, or where to turn in a quest.",
        "input_schema": {
            "type": "object",
            "properties": {
                "quest_name": {
                    "type": "string",
                    "description": "Name or partial name of the quest"
                }
            },
            "required": ["quest_name"]
        }
    },
    {
        "name": "find_item_upgrades",
        "description": "Find better items/gear upgrades for a specific slot or item. Use this when the player asks about upgrades, better gear, or what's an improvement over their current item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "current_item": {
                    "type": "string",
                    "description": "Name of the current item to find upgrades for"
                },
                "item_slot": {
                    "type": "string",
                    "description": "Item slot type (e.g., 'weapon', 'chest', 'head', 'legs', 'hands', 'feet', 'shoulders', 'back', 'wrist', 'waist', 'trinket', 'ring', 'neck')"
                },
                "player_level": {
                    "type": "integer",
                    "description": "Player's level to filter appropriate items"
                },
                "player_class": {
                    "type": "string",
                    "description": "Player's class to filter usable items (e.g., 'hunter', 'warrior')"
                }
            },
            "required": ["current_item"]
        }
    },
    {
        "name": "get_item_info",
        "description": "Get detailed information about an item including stats, where it drops, and who sells it. Use this when the player asks about a specific item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name or partial name of the item"
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "get_dungeon_info",
        "description": "Get information about a dungeon or raid instance including level range, location, difficulty modes, and entry requirements (attunements/keys). Use this when the player asks about dungeons, instances, or raids.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dungeon_name": {
                    "type": "string",
                    "description": "Name of the dungeon (e.g., 'Deadmines', 'Shadowfang Keep', 'Wailing Caverns', 'Stockade')"
                }
            },
            "required": ["dungeon_name"]
        }
    },
    {
        "name": "find_hunter_pet",
        "description": "Find tameable beasts for hunters by family type or zone. Returns [[npc:ID:Name]] markers. IMPORTANT: Include these markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_family": {
                    "type": "string",
                    "description": "Type of pet family (e.g., 'cat', 'wolf', 'bear', 'boar', 'spider', 'raptor', 'owl', 'bat', 'crab', 'gorilla', 'turtle')"
                },
                "zone": {
                    "type": "string",
                    "description": "Zone to search for tameable pets"
                },
                "max_level": {
                    "type": "integer",
                    "description": "Maximum level of pet to find (should match hunter's level)"
                }
            },
            "required": []
        }
    },
    {
        "name": "find_recipe_source",
        "description": "Find where to learn a profession recipe or pattern. Use this when a player asks where to learn a specific crafting recipe.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipe_name": {
                    "type": "string",
                    "description": "Name of the recipe or item to craft (e.g., 'Hillman's Leather Vest', 'Minor Healing Potion')"
                },
                "profession": {
                    "type": "string",
                    "description": "Profession type (e.g., 'leatherworking', 'blacksmithing', 'alchemy', 'tailoring', 'engineering', 'enchanting')"
                }
            },
            "required": ["recipe_name"]
        }
    },
    {
        "name": "get_flight_paths",
        "description": "Get information about flight paths in a zone or from a location. Use this when a player asks to list all flight points in a zone, how to fly somewhere, or about flight master connections.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_location": {
                    "type": "string",
                    "description": "Zone or location name to find flight points in (e.g., 'Tanaris', 'Stormwind', 'Auberdine')"
                },
                "to_location": {
                    "type": "string",
                    "description": "Destination location/zone (optional)"
                },
                "faction": {
                    "type": "string",
                    "description": "Player faction: 'alliance' or 'horde'"
                }
            },
            "required": ["from_location"]
        }
    },
    {
        "name": "get_boss_loot",
        "description": "Get the loot table for a dungeon or raid boss. Returns items with [[item:ID:Name:Quality]] markers that become clickable links in-game. IMPORTANT: You MUST include these [[item:...]] markers exactly as-is in your response - they will be converted to clickable item links for the player.",
        "input_schema": {
            "type": "object",
            "properties": {
                "boss_name": {
                    "type": "string",
                    "description": "Name of the boss (e.g., 'Edwin VanCleef', 'Arugal', 'Herod')"
                },
                "dungeon": {
                    "type": "string",
                    "description": "Optional dungeon name to help identify the correct boss"
                }
            },
            "required": ["boss_name"]
        }
    },
    {
        "name": "get_creature_loot",
        "description": "Get the loot table for a regular mob/creature. Returns items with [[item:ID:Name:Quality]] markers that become clickable links in-game. Use this when players ask what a specific mob drops. IMPORTANT: You MUST include these [[item:...]] markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "creature_name": {
                    "type": "string",
                    "description": "Name of the creature/mob (e.g., 'Defias Pillager', 'Blackrock Orc', 'Mosshide Gnoll')"
                },
                "zone": {
                    "type": "string",
                    "description": "Optional zone name to help identify the correct creature"
                }
            },
            "required": ["creature_name"]
        }
    },
    {
        "name": "get_zone_fishing",
        "description": "Get fish and other items that can be caught while fishing in a zone. Returns fishing skill requirements and catch rates. Use this when players ask about fishing in a zone, what fish they can catch, or fishing skill requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to search for fishing info (e.g., 'darkshore', 'westfall', 'stranglethorn')"
                }
            },
            "required": ["zone"]
        }
    },
    {
        "name": "get_zone_herbs",
        "description": "Get herbs that can be gathered in a zone. Returns herbalism skill requirements and herb names. Use this when players ask about herbalism in a zone, what herbs they can gather, or herbalism skill requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to search for herb info (e.g., 'darkshore', 'ashenvale', 'felwood')"
                }
            },
            "required": ["zone"]
        }
    },
    {
        "name": "get_zone_mining",
        "description": "Get mining nodes and ores that can be mined in a zone. Returns mining skill requirements and ore names. Use this when players ask about mining in a zone, what ores they can mine, or mining skill requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to search for mining info (e.g., 'dun morogh', 'westfall', 'badlands')"
                }
            },
            "required": ["zone"]
        }
    },
    {
        "name": "list_zone_creatures",
        "description": "List all hostile creatures/mobs in a zone. Returns [[npc:ID:Name]] markers. Use this when players ask what mobs are in a zone or what they can kill/grind in an area. IMPORTANT: Include these [[npc:...]] markers exactly as-is in your response.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to list creatures from (e.g., 'darkshore', 'westfall', 'barrens')"
                },
                "level_min": {
                    "type": "integer",
                    "description": "Optional minimum creature level filter"
                },
                "level_max": {
                    "type": "integer",
                    "description": "Optional maximum creature level filter"
                }
            },
            "required": ["zone"]
        }
    },
    {
        "name": "find_rare_spawn",
        "description": "ALWAYS use this tool to find rare spawn mobs in a zone. Do NOT guess or answer from memory - use this tool to get accurate data. Returns [[npc:ID:Name]] markers with level and spawn info. Use this when players ask about rare mobs, rare spawns, silver dragon mobs, or hunting rares in any zone. Every zone has different rares - you must query to know.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to search for rare spawns (e.g., 'teldrassil', 'darkshore', 'westfall', 'barrens')"
                }
            },
            "required": ["zone"]
        }
    },
    {
        "name": "get_zone_info",
        "description": "Get information about a zone including level range, faction, and what's there. Use this when players ask about a zone's level range, what faction it belongs to, or general zone information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {
                    "type": "string",
                    "description": "Zone name to get info about (e.g., 'darkshore', 'westfall', 'stranglethorn')"
                }
            },
            "required": ["zone"]
        }
    },
    {
        "name": "find_battlemaster",
        "description": "Find battlemasters who let you queue for battlegrounds. Use this when players ask where to queue for WSG, AB, AV, or other battlegrounds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "battleground": {
                    "type": "string",
                    "description": "Battleground name: 'warsong', 'arathi', 'alterac', 'eye of the storm', 'strand', 'isle of conquest', or 'all'"
                },
                "faction": {
                    "type": "string",
                    "description": "Player faction: 'alliance' or 'horde'"
                }
            },
            "required": ["battleground", "faction"]
        }
    },
    {
        "name": "get_weapon_skill_trainer",
        "description": "Find trainers who teach weapon skills like swords, maces, axes, etc. Use this when players ask where to learn a weapon skill.",
        "input_schema": {
            "type": "object",
            "properties": {
                "weapon_type": {
                    "type": "string",
                    "description": "Weapon type: 'swords', 'maces', 'axes', 'daggers', 'staves', 'polearms', 'fist weapons', 'bows', 'guns', 'crossbows', 'thrown', 'wands'"
                },
                "faction": {
                    "type": "string",
                    "description": "Player faction: 'alliance' or 'horde' (optional, helps narrow results)"
                }
            },
            "required": ["weapon_type"]
        }
    },
    {
        "name": "get_class_quests",
        "description": "Find class-specific quest chains like hunter pet quests, warlock demon quests, druid form quests, paladin/warlock mount quests, etc. Use this when players ask about their class quests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_class": {
                    "type": "string",
                    "description": "Player's class (e.g., 'hunter', 'warlock', 'druid', 'paladin', 'shaman', 'warrior', 'rogue', 'priest', 'mage')"
                },
                "player_level": {
                    "type": "integer",
                    "description": "Player's level to filter available quests"
                },
                "faction": {
                    "type": "string",
                    "description": "Player faction: 'alliance' or 'horde'"
                }
            },
            "required": ["player_class"]
        }
    },
    {
        "name": "get_quest_chain",
        "description": "Get the full quest chain for a quest, showing all prerequisites and follow-up quests in order. Use this when players ask about quest chains, attunements, or what quests come before/after a specific quest.",
        "input_schema": {
            "type": "object",
            "properties": {
                "quest_name": {
                    "type": "string",
                    "description": "Name of any quest in the chain (will find full chain)"
                }
            },
            "required": ["quest_name"]
        }
    },
    {
        "name": "get_reputation_info",
        "description": "Get information about a faction's reputation including how to gain rep (quests, mob kills, turn-ins) and rewards at each standing level. Use this when players ask about reputation grinding, faction rewards, or how to reach Exalted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "faction_name": {
                    "type": "string",
                    "description": "Name of the faction (e.g., 'Timbermaw Hold', 'Argent Dawn', 'Cenarion Circle', 'The Scryers')"
                }
            },
            "required": ["faction_name"]
        }
    }
]


# =============================================================================
# TOOL EXECUTORS
# =============================================================================

class GameToolExecutor:
    """Executes game data tools by querying the database."""

    # Item class/subclass mappings
    ITEM_CLASS_MAP = {
        'arrow': (6, 2), 'arrows': (6, 2),
        'bullet': (6, 3), 'bullets': (6, 3), 'shot': (6, 3),
        'ammo': [(6, 2), (6, 3)], 'ammunition': [(6, 2), (6, 3)],
        'food': (0, 5), 'drink': (0, 5), 'water': (0, 5),
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

    # Name-based item patterns for items without class/subclass
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

    # Trainer subname patterns
    TRAINER_PATTERNS = {
        'hunter': '%Hunter%', 'warrior': '%Warrior%', 'mage': '%Mage%',
        'priest': '%Priest%', 'rogue': '%Rogue%', 'warlock': '%Warlock%',
        'druid': '%Druid%', 'paladin': '%Paladin%', 'shaman': '%Shaman%',
        'death knight': '%Death Knight%',
        'leatherworking': '%Leatherworking%', 'blacksmithing': '%Blacksmith%',
        'tailoring': '%Tailor%', 'engineering': '%Engineer%',
        'alchemy': '%Alchem%', 'enchanting': '%Enchant%',
        'mining': '%Mining%', 'herbalism': '%Herb%', 'skinning': '%Skinning%',
        'cooking': '%Cooking%', 'fishing': '%Fishing%', 'first aid': '%First Aid%',
        'inscription': '%Inscription%', 'jewelcrafting': '%Jewel%',
        'riding': '%Riding%', 'pet': '%Pet%',
    }

    # Service NPC patterns
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

    # Spell name to ID mapping (curated list of common spells)
    SPELL_MAP = {
        # Hunter
        'serpent sting': 1978, 'arcane shot': 3044, 'hunters mark': 1130,
        'concussive shot': 5116, 'aspect of the hawk': 13165, 'tame beast': 1515,
        'revive pet': 982, 'mend pet': 136, 'disengage': 781, 'feign death': 5384,
        'freezing trap': 1499, 'multi-shot': 2643, 'aimed shot': 19434,
        'bestial wrath': 19574, 'steady shot': 56641, 'kill shot': 53351,
        'aspect of the monkey': 13163, 'aspect of the cheetah': 5118,
        'rapid fire': 3045, 'deterrence': 19263, 'scatter shot': 19503,
        'explosive trap': 13813, 'immolation trap': 13795, 'frost trap': 13809,
        # Warrior
        'charge': 100, 'rend': 772, 'thunder clap': 6343, 'hamstring': 1715,
        'heroic strike': 78, 'battle shout': 6673, 'overpower': 7384,
        'taunt': 355, 'execute': 5308, 'intercept': 20252, 'whirlwind': 1680,
        'mortal strike': 12294, 'bloodthirst': 23881, 'shield slam': 23922,
        'shield bash': 72, 'shield block': 2565, 'revenge': 6572,
        'sunder armor': 7386, 'demoralizing shout': 1160, 'berserker rage': 18499,
        'pummel': 6552, 'spell reflection': 23920, 'commanding shout': 469,
        'cleave': 845, 'slam': 1464, 'victory rush': 34428,
        # Mage
        'fireball': 133, 'frostbolt': 116, 'arcane missiles': 5143,
        'frost nova': 122, 'fire blast': 2136, 'blink': 1953, 'polymorph': 118,
        'counterspell': 2139, 'ice block': 45438, 'pyroblast': 11366,
        'arcane explosion': 1449, 'arcane intellect': 1459, 'conjure water': 5504,
        'conjure food': 587, 'slow fall': 130, 'remove curse': 475,
        'blizzard': 10, 'flamestrike': 2120, 'cone of cold': 120,
        'mana shield': 1463, 'ice barrier': 11426, 'evocation': 12051,
        # Priest
        'lesser heal': 2050, 'smite': 585, 'shadow word pain': 589,
        'power word fortitude': 1243, 'renew': 139, 'fade': 586,
        'psychic scream': 8122, 'mind blast': 8092, 'flash heal': 2061,
        'shadowform': 15473, 'power word shield': 17,
        'heal': 2054, 'greater heal': 2060, 'prayer of healing': 596,
        'mind flay': 15407, 'vampiric embrace': 15286, 'dispel magic': 527,
        'abolish disease': 552, 'inner fire': 588, 'divine spirit': 14752,
        'prayer of fortitude': 21562, 'resurrection': 2006,
        # Rogue
        'sinister strike': 1752, 'eviscerate': 2098, 'backstab': 53,
        'gouge': 1776, 'stealth': 1784, 'sap': 6770, 'sprint': 2983,
        'kick': 1766, 'vanish': 1856, 'cheap shot': 1833, 'blind': 2094,
        'kidney shot': 408, 'slice and dice': 5171, 'rupture': 1943,
        'expose armor': 8647, 'ambush': 8676, 'garrote': 703,
        'feint': 1966, 'evasion': 5277, 'cloak of shadows': 31224,
        'preparation': 14185, 'shadowstep': 36554, 'deadly throw': 26679,
        # Warlock
        'shadow bolt': 686, 'corruption': 172, 'immolate': 348,
        'curse of agony': 980, 'fear': 5782, 'summon imp': 688,
        'summon voidwalker': 697, 'drain life': 689, 'life tap': 1454,
        'summon succubus': 712, 'summon felhunter': 691, 'summon felguard': 30146,
        'curse of weakness': 702, 'curse of the elements': 1490,
        'drain soul': 1120, 'drain mana': 5138, 'soulstone': 693,
        'create healthstone': 6201, 'create soulwell': 29893, 'howl of terror': 5484,
        'death coil warlock': 6789, 'seed of corruption': 27243, 'banish': 710,
        # Druid
        'wrath': 5176, 'healing touch': 5185, 'moonfire': 8921,
        'rejuvenation': 774, 'thorns': 467, 'entangling roots': 339,
        'bear form': 5487, 'cat form': 768, 'travel form': 783,
        'regrowth': 8936, 'rebirth': 20484, 'innervate': 29166,
        'starfire': 2912, 'lifebloom': 33763, 'nourish': 50464,
        'swiftmend': 18562, 'wild growth': 48438, 'aquatic form': 1066,
        'claw': 1082, 'rake': 1822, 'rip': 1079, 'ferocious bite': 22568,
        'mangle': 33876, 'swipe': 779, 'maul': 6807, 'lacerate': 33745,
        'hurricane': 16914, 'barkskin': 22812, 'mark of the wild': 1126,
        # Paladin
        'holy light': 635, 'seal of righteousness': 21084,
        'blessing of might': 19740, 'hammer of justice': 853,
        'lay on hands': 633, 'divine shield': 642, 'consecration': 26573,
        'flash of light': 19750, 'seal of command': 20375, 'judgement': 20271,
        'blessing of wisdom': 19742, 'blessing of kings': 20217,
        'devotion aura': 465, 'retribution aura': 7294, 'concentration aura': 19746,
        'divine protection': 498, 'hand of freedom': 1044, 'cleanse': 4987,
        'exorcism': 879, 'holy wrath': 2812, 'avengers shield': 31935,
        'crusader strike': 35395, 'divine storm': 53385, 'holy shock': 20473,
        # Shaman
        'lightning bolt': 403, 'earth shock': 8042, 'healing wave': 331,
        'flame shock': 8050, 'ghost wolf': 2645, 'chain lightning': 421,
        'chain heal': 1064, 'bloodlust': 2825, 'heroism': 32182,
        'lesser healing wave': 8004, 'riptide': 61295, 'earthliving weapon': 51730,
        'purge': 370, 'wind shear': 57994, 'lava burst': 51505,
        'stormstrike': 17364, 'lava lash': 60103, 'shamanistic rage': 30823,
        'totemic recall': 36936, 'elemental mastery': 16166,
        'fire nova': 1535, 'frost shock': 8056,
        # Death Knight
        'blood strike': 45902, 'icy touch': 45477, 'plague strike': 45462,
        'death strike': 49998, 'death coil': 47541, 'death grip': 49576,
        'mind freeze': 47528, 'strangulate': 47476, 'anti-magic shell': 48707,
        'icebound fortitude': 48792, 'bone shield': 49222, 'vampiric blood': 55233,
        'dancing rune weapon': 49028, 'army of the dead': 42650,
        'raise dead': 46584, 'death and decay': 43265, 'obliterate': 49020,
        'frost strike': 49143, 'howling blast': 49184, 'horn of winter': 57330,
        'pestilence': 50842, 'blood boil': 48721, 'heart strike': 55050,
        'rune strike': 56815, 'empower rune weapon': 47568,
    }

    # Class name to WoW class ID mapping (for trainer table queries)
    # trainer.Type = 0 means class trainer, trainer.Requirement = class ID
    CLASS_IDS = {
        'warrior': 1, 'paladin': 2, 'hunter': 3, 'rogue': 4,
        'priest': 5, 'death knight': 6, 'shaman': 7, 'mage': 8,
        'warlock': 9, 'druid': 11
    }

    # Dungeon location mapping (map_id -> entrance zone, since this isn't in DB)
    DUNGEON_LOCATIONS = {
        # Classic Dungeons
        36: 'Westfall',           # Deadmines
        43: 'The Barrens',        # Wailing Caverns
        33: 'Silverpine Forest',  # Shadowfang Keep
        34: 'Stormwind City',     # The Stockade
        48: 'Ashenvale',          # Blackfathom Deeps
        90: 'Dun Morogh',         # Gnomeregan
        47: 'The Barrens',        # Razorfen Kraul
        129: 'The Barrens',       # Razorfen Downs
        189: 'Tirisfal Glades',   # Scarlet Monastery
        70: 'Badlands',           # Uldaman
        209: 'Tanaris',           # Zul'Farrak
        349: 'Feralas',           # Maraudon
        109: 'The Hinterlands',   # Temple of Atal'Hakkar (Sunken Temple)
        230: 'Searing Gorge',     # Blackrock Depths
        229: 'Searing Gorge',     # Lower Blackrock Spire
        429: 'Feralas',           # Dire Maul
        329: 'Eastern Plaguelands', # Stratholme
        289: 'Western Plaguelands', # Scholomance
        389: 'Orgrimmar',         # Ragefire Chasm
        # TBC Dungeons
        269: 'Tanaris',           # Caverns of Time: Opening the Dark Portal
        560: 'Tanaris',           # Caverns of Time: Old Hillsbrad
        540: 'Hellfire Peninsula', # The Shattered Halls
        542: 'Hellfire Peninsula', # The Blood Furnace
        543: 'Hellfire Peninsula', # Hellfire Ramparts
        545: 'Zangarmarsh',       # The Steamvault
        546: 'Zangarmarsh',       # The Underbog
        547: 'Zangarmarsh',       # The Slave Pens
        552: 'Netherstorm',       # The Arcatraz
        553: 'Netherstorm',       # The Botanica
        554: 'Netherstorm',       # The Mechanar
        555: 'Terokkar Forest',   # Shadow Labyrinth
        556: 'Terokkar Forest',   # Sethekk Halls
        557: 'Terokkar Forest',   # Mana-Tombs
        558: 'Terokkar Forest',   # Auchenai Crypts
        585: "Isle of Quel'Danas", # Magister's Terrace
        # WotLK Dungeons
        574: 'Howling Fjord',     # Utgarde Keep
        575: 'Howling Fjord',     # Utgarde Pinnacle
        576: 'Borean Tundra',     # The Nexus
        578: 'Borean Tundra',     # The Oculus
        595: 'Tanaris',           # Culling of Stratholme
        599: 'The Storm Peaks',   # Halls of Stone
        600: 'Dragonblight',      # Drak'Tharon Keep
        601: "Zul'Drak",          # Azjol-Nerub
        602: 'The Storm Peaks',   # Halls of Lightning
        604: 'Grizzly Hills',     # Gundrak
        608: 'Dalaran',           # The Violet Hold
        619: "Zul'Drak",          # Ahn'kahet: The Old Kingdom
        632: 'Icecrown',          # Forge of Souls
        649: 'Icecrown',          # Trial of the Champion
        650: 'Icecrown',          # Trial of the Grand Crusader
        658: 'Icecrown',          # Pit of Saron
        668: 'Icecrown',          # Halls of Reflection
        # Classic Raids
        249: "Dustwallow Marsh",  # Onyxia's Lair
        309: 'Stranglethorn Vale', # Zul'Gurub
        409: 'Searing Gorge',     # Molten Core
        469: 'Searing Gorge',     # Blackwing Lair
        509: 'Silithus',          # Ruins of Ahn'Qiraj
        531: 'Silithus',          # Temple of Ahn'Qiraj
        533: 'Dragonblight',        # Naxxramas (WotLK version)
        # TBC Raids
        532: 'Deadwind Pass',     # Karazhan
        534: 'Tanaris',           # Hyjal Summit
        544: 'Hellfire Peninsula', # Magtheridon's Lair
        548: 'Zangarmarsh',       # Serpentshrine Cavern
        550: 'Netherstorm',       # The Eye (Tempest Keep)
        564: 'Shadowmoon Valley', # Black Temple
        565: "Blade's Edge Mountains", # Gruul's Lair
        580: "Isle of Quel'Danas", # Sunwell Plateau
        # WotLK Raids
        603: 'The Storm Peaks',   # Ulduar
        615: 'Dragonblight',      # The Obsidian Sanctum
        616: 'Dragonblight',      # The Eye of Eternity
        624: 'Wintergrasp',       # Vault of Archavon
        631: 'Icecrown',          # Icecrown Citadel
        649: 'Icecrown',          # Trial of the Crusader
        724: 'Dragonblight',      # The Ruby Sanctum
    }

    # Hunter pet family mapping (family ID -> name and type)
    PET_FAMILIES = {
        1: {'name': 'Wolf', 'type': 'Ferocity', 'diet': 'Meat'},
        2: {'name': 'Cat', 'type': 'Ferocity', 'diet': 'Meat, Fish'},
        3: {'name': 'Spider', 'type': 'Cunning', 'diet': 'Meat'},
        4: {'name': 'Bear', 'type': 'Tenacity', 'diet': 'Bread, Cheese, Fish, Fruit, Fungus, Meat'},
        5: {'name': 'Boar', 'type': 'Tenacity', 'diet': 'Bread, Cheese, Fish, Fruit, Fungus, Meat'},
        6: {'name': 'Crocolisk', 'type': 'Tenacity', 'diet': 'Fish, Meat'},
        7: {'name': 'Carrion Bird', 'type': 'Ferocity', 'diet': 'Fish, Meat'},
        8: {'name': 'Crab', 'type': 'Tenacity', 'diet': 'Bread, Fish, Fruit, Fungus'},
        9: {'name': 'Gorilla', 'type': 'Tenacity', 'diet': 'Bread, Fruit, Fungus'},
        11: {'name': 'Raptor', 'type': 'Ferocity', 'diet': 'Meat'},
        12: {'name': 'Tallstrider', 'type': 'Ferocity', 'diet': 'Cheese, Fruit, Fungus'},
        20: {'name': 'Scorpid', 'type': 'Tenacity', 'diet': 'Meat'},
        21: {'name': 'Turtle', 'type': 'Tenacity', 'diet': 'Fish, Fruit, Fungus'},
        24: {'name': 'Bat', 'type': 'Cunning', 'diet': 'Fruit, Fungus'},
        25: {'name': 'Hyena', 'type': 'Ferocity', 'diet': 'Meat'},
        26: {'name': 'Bird of Prey', 'type': 'Cunning', 'diet': 'Meat'},
        27: {'name': 'Wind Serpent', 'type': 'Cunning', 'diet': 'Bread, Cheese, Fish'},
        30: {'name': 'Dragonhawk', 'type': 'Cunning', 'diet': 'Meat, Fish'},
        31: {'name': 'Ravager', 'type': 'Cunning', 'diet': 'Meat'},
        32: {'name': 'Warp Stalker', 'type': 'Tenacity', 'diet': 'Fish, Meat'},
        34: {'name': 'Nether Ray', 'type': 'Cunning', 'diet': 'Meat'},
        35: {'name': 'Serpent', 'type': 'Cunning', 'diet': 'Meat'},
        37: {'name': 'Moth', 'type': 'Ferocity', 'diet': 'Cheese, Fruit'},
        38: {'name': 'Chimaera', 'type': 'Cunning', 'diet': 'Meat'},
        39: {'name': 'Devilsaur', 'type': 'Ferocity', 'diet': 'Meat'},
        41: {'name': 'Silithid', 'type': 'Cunning', 'diet': 'Meat'},
        42: {'name': 'Worm', 'type': 'Tenacity', 'diet': 'Bread, Cheese, Fungus'},
        43: {'name': 'Rhino', 'type': 'Tenacity', 'diet': 'Bread, Cheese, Fruit, Fungus'},
        44: {'name': 'Wasp', 'type': 'Ferocity', 'diet': 'Bread, Cheese, Fruit'},
        45: {'name': 'Core Hound', 'type': 'Ferocity', 'diet': 'Meat'},
        46: {'name': 'Spirit Beast', 'type': 'Ferocity', 'diet': 'Meat, Fish'},
    }

    # Flight path connections (Alliance)
    FLIGHT_PATHS_ALLIANCE = {
        'auberdine': ['rut\'theran village', 'astranaar', 'talonbranch glade'],
        'rut\'theran village': ['auberdine'],
        'stormwind': ['ironforge', 'sentinel hill', 'darkshire', 'lakeshire', 'booty bay', 'morgan\'s vigil'],
        'ironforge': ['stormwind', 'thelsamar', 'menethil harbor', 'thorium point'],
        'menethil harbor': ['ironforge', 'auberdine', 'theramore'],
        'theramore': ['menethil harbor', 'gadgetzan', 'nijel\'s point'],
        'astranaar': ['auberdine', 'nijel\'s point', 'stonetalon peak'],
    }

    # Flight path connections (Horde)
    FLIGHT_PATHS_HORDE = {
        'orgrimmar': ['thunder bluff', 'crossroads', 'splintertree post', 'undercity'],
        'thunder bluff': ['orgrimmar', 'crossroads', 'camp taurajo'],
        'crossroads': ['orgrimmar', 'thunder bluff', 'camp taurajo', 'ratchet'],
        'undercity': ['orgrimmar', 'tarren mill', 'the sepulcher'],
        'camp taurajo': ['crossroads', 'thunder bluff', 'freewind post'],
    }

    # 1 WoW unit = 1 yard = 0.9144 meters
    YARD_TO_METER = 0.9144

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.default_zone = None  # Player's current zone, set before processing
        self.player_x = None
        self.player_y = None
        self.player_map = None
        self.distance_unit = "yards"  # "yards" or "meters"

    def set_player_zone(self, zone: str):
        """Set the player's current zone for use as default in tool calls."""
        self.default_zone = zone

    def set_player_position(self, x: float, y: float, map_id: int):
        """Set the player's current position for distance calculations."""
        self.player_x = x
        self.player_y = y
        self.player_map = map_id

    def calculate_distance(self, target_x: float, target_y: float) -> float:
        """Calculate distance from player to target coordinates.

        Returns distance in yards (WoW units), or None if player position not set.
        """
        if self.player_x is None or self.player_y is None:
            return None
        import math
        dx = target_x - self.player_x
        dy = target_y - self.player_y
        return math.sqrt(dx * dx + dy * dy)

    def get_direction(self, target_x: float, target_y: float) -> str:
        """Get compass direction from player to target.

        Returns direction string (e.g., 'north', 'southeast'), or None if position not set.
        WoW coordinate system: +X is north, +Y is west.
        """
        if self.player_x is None or self.player_y is None:
            return None
        import math
        dx = target_x - self.player_x  # positive = north
        dy = target_y - self.player_y  # positive = west

        # Calculate angle in degrees (0 = north, 90 = west, etc.)
        angle = math.degrees(math.atan2(-dy, dx))  # negate dy so east is positive
        if angle < 0:
            angle += 360

        # Convert angle to compass direction
        if angle >= 337.5 or angle < 22.5:
            return "north"
        elif angle < 67.5:
            return "northeast"
        elif angle < 112.5:
            return "east"
        elif angle < 157.5:
            return "southeast"
        elif angle < 202.5:
            return "south"
        elif angle < 247.5:
            return "southwest"
        elif angle < 292.5:
            return "west"
        else:
            return "northwest"

    def format_distance_direction(self, target_x: float, target_y: float, target_map: int = None) -> str:
        """Format distance and direction string for display.

        Returns string like "~85 yards northeast" or "~78 meters northeast"
        depending on configured distance_unit. Uses km for 1000m+.
        """
        # Only calculate if we're on the same map
        if target_map is not None and self.player_map is not None:
            if target_map != self.player_map:
                return ""

        distance = self.calculate_distance(target_x, target_y)
        direction = self.get_direction(target_x, target_y)

        if distance is not None and direction is not None:
            if self.distance_unit == "meters":
                meters = distance * self.YARD_TO_METER
                if meters >= 1000:
                    return f"~{meters / 1000:.1f} km {direction}"
                return f"~{int(meters)} m {direction}"
            return f"~{int(distance)} yards {direction}"
        return ""

    def get_connection(self):
        """Get database connection."""
        import mysql.connector
        world_config = self.db_config.copy()
        world_config['database'] = 'acore_world'
        return mysql.connector.connect(**world_config)

    def _get_zone_filter(self, zone: str) -> tuple:
        """Get zone coordinates, zone_id, and build SQL filter.

        Returns: (zone_data_dict, filter_sql) where zone_data_dict contains:
            - coords: (map_id, loc_left, loc_right, loc_top, loc_bottom)
            - zone_id: The zone ID for queries using creature.zoneId
        """
        if not zone:
            return None, ""

        zone_coords = get_zone_coordinates(zone)
        if not zone_coords:
            return None, ""

        zone_id = get_zone_id(zone)
        map_id, loc_left, loc_right, loc_top, loc_bottom = zone_coords

        # Build zone data dict
        zone_data = {
            'coords': zone_coords,
            'zone_id': zone_id,
            'map_id': map_id
        }

        # Skip filtering if zone has no coordinate data (e.g., Dalaran)
        if loc_left == 0 and loc_right == 0:
            filter_sql = f"AND c.map = {map_id}"
        else:
            # position_x is between loc_bottom and loc_top
            # position_y is between loc_right and loc_left
            filter_sql = f"AND c.map = {map_id} AND c.position_x BETWEEN {loc_bottom} AND {loc_top} AND c.position_y BETWEEN {loc_right} AND {loc_left}"
        return zone_data, filter_sql

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return results as a string."""
        # Auto-inject player's zone if not specified and tool supports it
        zone_tools = {
            'find_vendor', 'find_trainer', 'find_service_npc', 'find_npc',
            'find_quest_giver', 'get_available_quests', 'find_creature',
            'find_hunter_pet', 'get_flight_paths', 'list_zone_creatures'
        }
        if (tool_name in zone_tools and
                'zone' not in tool_input and
                self.default_zone):
            tool_input = tool_input.copy()  # Don't modify original
            tool_input['zone'] = self.default_zone
            logger.info(f"Auto-injected zone '{self.default_zone}' into {tool_name}")

        logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

        try:
            if tool_name == "find_vendor":
                return self._find_vendor(tool_input)
            elif tool_name == "find_trainer":
                return self._find_trainer(tool_input)
            elif tool_name == "find_service_npc":
                return self._find_service_npc(tool_input)
            elif tool_name == "find_npc":
                return self._find_npc(tool_input)
            elif tool_name == "get_spell_info":
                return self._get_spell_info(tool_input)
            elif tool_name == "list_spells_by_level":
                return self._list_spells_by_level(tool_input)
            elif tool_name == "find_quest_giver":
                return self._find_quest_giver(tool_input)
            elif tool_name == "get_available_quests":
                return self._get_available_quests(tool_input)
            elif tool_name == "find_creature":
                return self._find_creature(tool_input)
            elif tool_name == "get_quest_info":
                return self._get_quest_info(tool_input)
            elif tool_name == "get_item_info":
                return self._get_item_info(tool_input)
            elif tool_name == "find_item_upgrades":
                return self._find_item_upgrades(tool_input)
            elif tool_name == "get_dungeon_info":
                return self._get_dungeon_info(tool_input)
            elif tool_name == "find_hunter_pet":
                return self._find_hunter_pet(tool_input)
            elif tool_name == "find_recipe_source":
                return self._find_recipe_source(tool_input)
            elif tool_name == "get_flight_paths":
                return self._get_flight_paths(tool_input)
            elif tool_name == "get_boss_loot":
                return self._get_boss_loot(tool_input)
            elif tool_name == "get_creature_loot":
                return self._get_creature_loot(tool_input)
            elif tool_name == "get_zone_fishing":
                return self._get_zone_fishing(tool_input)
            elif tool_name == "get_zone_herbs":
                return self._get_zone_herbs(tool_input)
            elif tool_name == "get_zone_mining":
                return self._get_zone_mining(tool_input)
            elif tool_name == "list_zone_creatures":
                return self._list_zone_creatures(tool_input)
            elif tool_name == "find_rare_spawn":
                return self._find_rare_spawn(tool_input)
            elif tool_name == "get_zone_info":
                return self._get_zone_info(tool_input)
            elif tool_name == "find_battlemaster":
                return self._find_battlemaster(tool_input)
            elif tool_name == "get_weapon_skill_trainer":
                return self._get_weapon_skill_trainer(tool_input)
            elif tool_name == "get_class_quests":
                return self._get_class_quests(tool_input)
            elif tool_name == "get_quest_chain":
                return self._get_quest_chain(tool_input)
            elif tool_name == "get_reputation_info":
                return self._get_reputation_info(tool_input)
            else:
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Error executing tool: {str(e)}"

    def _find_vendor(self, params: dict) -> str:
        """Find vendors selling specific items."""
        item_type = params.get("item_type", "").lower()
        zone = params.get("zone", "").lower()

        zone_coords, zone_filter = self._get_zone_filter(zone)

        # Special case: "general" vendor (any vendor to sell junk to)
        if item_type in ('general', 'supplies', 'any', 'vendor', 'junk', 'sell'):
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"""
                SELECT DISTINCT ct.entry as vendor_entry, ct.name as vendor_name, ct.subname as title,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
                FROM creature_template ct
                JOIN creature c ON ct.entry = c.id1
                WHERE (ct.subname LIKE '%Supplies%' OR ct.subname LIKE '%Goods%' OR ct.subname LIKE '%Merchant%')
                  AND ct.npcflag & 128 > 0 {zone_filter}
                ORDER BY ct.name
                LIMIT 5
            """)
            vendors = cursor.fetchall()
            cursor.close()
            conn.close()

            if not vendors:
                return f"No general vendor found in {zone or 'the area'}."

            result = f"General vendors in {zone or 'the area'}:\n"
            for v in vendors:
                npc_link = f"[[npc:{v['vendor_entry']}:{v['vendor_name']}]]"
                title = f" ({v['title']})" if v['title'] else ""
                # Add distance/direction if available
                dist_info = self.format_distance_direction(v['pos_x'], v['pos_y'], v['map_id'])
                dist_str = f" ({dist_info})" if dist_info else ""
                coords = ""
                if zone_coords and v['pos_x'] and v['pos_y']:
                    map_coords = world_to_map_coords(zone, v['pos_x'], v['pos_y'])
                    if map_coords:
                        coords = f" at {map_coords[0]}, {map_coords[1]}"
                result += f"- {npc_link}{title}{dist_str}{coords}\n"
            result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
            return result

        # Get item class/subclass
        class_filters = []
        if item_type in self.ITEM_CLASS_MAP:
            class_info = self.ITEM_CLASS_MAP[item_type]
            if isinstance(class_info, list):
                class_filters = class_info
            else:
                class_filters = [class_info]

        # Check name patterns
        name_patterns = self.ITEM_NAME_MAP.get(item_type, [])

        if not class_filters and not name_patterns:
            return f"Unknown item type: {item_type}. Try: general, arrows, food, drink, reagents, bags, potions, bandages."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        vendors = []

        if class_filters:
            conditions = [f"(it.class = {c} AND it.subclass = {s})" for c, s in class_filters]
            cursor.execute(f"""
                SELECT DISTINCT ct.entry as vendor_entry, ct.name as vendor_name, ct.subname as title,
                       GROUP_CONCAT(DISTINCT it.name ORDER BY it.name SEPARATOR ', ') as items,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
                FROM npc_vendor nv
                JOIN creature_template ct ON nv.entry = ct.entry
                JOIN creature c ON ct.entry = c.id1
                JOIN item_template it ON nv.item = it.entry
                WHERE ({' OR '.join(conditions)}) {zone_filter}
                GROUP BY ct.entry, c.position_x, c.position_y, c.map
                LIMIT 5
            """)
            vendors = cursor.fetchall()

        if not vendors and name_patterns:
            placeholders = ' OR '.join(['it.name LIKE %s'] * len(name_patterns))
            cursor.execute(f"""
                SELECT DISTINCT ct.entry as vendor_entry, ct.name as vendor_name, ct.subname as title,
                       GROUP_CONCAT(DISTINCT it.name ORDER BY it.name SEPARATOR ', ') as items,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
                FROM npc_vendor nv
                JOIN creature_template ct ON nv.entry = ct.entry
                JOIN creature c ON ct.entry = c.id1
                JOIN item_template it ON nv.item = it.entry
                WHERE ({placeholders}) {zone_filter}
                GROUP BY ct.entry, c.position_x, c.position_y, c.map
                LIMIT 5
            """, [f"%{p}%" for p in name_patterns])
            vendors = cursor.fetchall()

        cursor.close()
        conn.close()

        if not vendors:
            return f"No vendors selling {item_type} found in {zone or 'the world'}."

        result = f"Vendors selling {item_type} in {zone or 'the world'}:\n"
        for v in vendors:
            title = f" ({v['title']})" if v['title'] else ""
            items = v['items'][:80] + "..." if len(v['items']) > 80 else v['items']
            npc_link = f"[[npc:{v['vendor_entry']}:{v['vendor_name']}]]"
            # Add distance/direction if available
            dist_info = self.format_distance_direction(v['pos_x'], v['pos_y'], v['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            result += f"- {npc_link}{title}{dist_str}: {items}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _find_trainer(self, params: dict) -> str:
        """Find class or profession trainers."""
        trainer_type = params.get("trainer_type", "").lower()
        zone = params.get("zone", "").lower()

        pattern = self.TRAINER_PATTERNS.get(trainer_type)
        if not pattern:
            return f"Unknown trainer type: {trainer_type}. Try: hunter, warrior, mage, leatherworking, mining, cooking, etc."

        zone_coords, zone_filter = self._get_zone_filter(zone)

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT DISTINCT ct.entry as trainer_entry, ct.name as trainer_name, ct.subname as title,
                   c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE ct.subname LIKE %s AND ct.npcflag & 16 > 0 {zone_filter}
            ORDER BY ct.name
            LIMIT 5
        """, (pattern,))

        trainers = cursor.fetchall()
        cursor.close()
        conn.close()

        if not trainers:
            return f"No {trainer_type} trainer found in {zone or 'the world'}."

        result = f"{trainer_type.title()} trainers in {zone or 'the world'}:\n"
        for t in trainers:
            npc_link = f"[[npc:{t['trainer_entry']}:{t['trainer_name']}]]"
            # Add distance/direction if available
            dist_info = self.format_distance_direction(t['pos_x'], t['pos_y'], t['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            coords = ""
            if zone_coords and t['pos_x'] and t['pos_y']:
                map_coords = world_to_map_coords(zone, round(t['pos_x'], 1), round(t['pos_y'], 1))
                if map_coords:
                    coords = f" at {map_coords[0]}, {map_coords[1]}"
            result += f"- {npc_link} ({t['title']}){dist_str}{coords}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _find_service_npc(self, params: dict) -> str:
        """Find service NPCs."""
        service_type = params.get("service_type", "").lower()
        zone = params.get("zone", "").lower()

        pattern = self.SERVICE_PATTERNS.get(service_type)
        if not pattern:
            return f"Unknown service: {service_type}. Try: stable master, innkeeper, flight master, banker, auctioneer."

        zone_coords, zone_filter = self._get_zone_filter(zone)

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT DISTINCT ct.entry as npc_entry, ct.name as npc_name, ct.subname as title,
                   c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE ct.subname LIKE %s {zone_filter}
            LIMIT 5
        """, (pattern,))

        npcs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not npcs:
            return f"No {service_type} found in {zone or 'the world'}."

        result = f"{service_type.title()} in {zone or 'the world'}:\n"
        for n in npcs:
            # Add distance/direction if available
            dist_info = self.format_distance_direction(n['pos_x'], n['pos_y'], n['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            coords = ""
            if zone_coords and n['pos_x'] and n['pos_y']:
                map_coords = world_to_map_coords(zone, round(n['pos_x'], 1), round(n['pos_y'], 1))
                if map_coords:
                    coords = f" at {map_coords[0]}, {map_coords[1]}"
            npc_link = f"[[npc:{n['npc_entry']}:{n['npc_name']}]]"
            result += f"- {npc_link}{dist_str}{coords}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _find_npc(self, params: dict) -> str:
        """Find a specific NPC by name."""
        npc_name = params.get("npc_name", "")
        zone = params.get("zone", "").lower() if params.get("zone") else None

        if not npc_name:
            return "Please specify an NPC name to search for."

        zone_coords, zone_filter = self._get_zone_filter(zone) if zone else (None, "")

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT DISTINCT ct.entry as npc_entry, ct.name as npc_name, ct.subname as title,
                   c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE ct.name LIKE %s {zone_filter}
            LIMIT 5
        """, (f"%{npc_name}%",))

        npcs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not npcs:
            return f"No NPC named '{npc_name}' found{' in ' + zone if zone else ''}."

        result = f"Found NPC(s) matching '{npc_name}':\n"
        for n in npcs:
            title = f" ({n['title']})" if n['title'] else ""
            # Add distance/direction if available
            dist_info = self.format_distance_direction(n['pos_x'], n['pos_y'], n['map_id'])
            dist_str = f" ({dist_info})" if dist_info else ""
            coords = ""
            if zone_coords and n['pos_x'] and n['pos_y']:
                map_coords = world_to_map_coords(zone, round(n['pos_x'], 1), round(n['pos_y'], 1))
                if map_coords:
                    coords = f" at {map_coords[0]}, {map_coords[1]}"
            npc_link = f"[[npc:{n['npc_entry']}:{n['npc_name']}]]"
            result += f"- {npc_link}{title}{dist_str}{coords}\n"
        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored NPC links!"
        return result

    def _get_spell_info(self, params: dict) -> str:
        """Get spell training info."""
        spell_name = params.get("spell_name", "").lower()
        player_class = params.get("player_class", "").lower()

        spell_id = self.SPELL_MAP.get(spell_name)
        if not spell_id:
            # Try partial match
            for name, sid in self.SPELL_MAP.items():
                if spell_name in name or name in spell_name:
                    spell_id = sid
                    spell_name = name
                    break

        if not spell_id:
            return f"Spell '{spell_name}' not found in database. This might be a talent or special ability."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT ts.ReqLevel, ts.MoneyCost
            FROM trainer_spell ts
            WHERE ts.SpellId = %s
            LIMIT 1
        """, (spell_id,))

        spell_data = cursor.fetchone()
        cursor.close()
        conn.close()

        if not spell_data:
            return f"'{spell_name.title()}' appears to be a talent or automatically learned ability, not trained from a trainer."

        level = spell_data['ReqLevel']
        cost = spell_data['MoneyCost']

        # Format cost
        if cost >= 10000:
            cost_str = f"{cost // 10000}g {(cost % 10000) // 100}s" if cost % 10000 >= 100 else f"{cost // 10000}g"
        elif cost >= 100:
            cost_str = f"{cost // 100}s"
        else:
            cost_str = f"{cost}c"

        # Use spell link marker
        spell_link = f"[[spell:{spell_id}:{spell_name.title()}]]"
        desc = SPELL_DESCRIPTIONS.get(spell_id, "")
        result = f"Spell: {spell_link}\nAvailable at level: {level}\nTraining cost: {cost_str}"
        if desc:
            result += f"\nDescription: {desc}"
        result += "\nVisit your class trainer to learn this spell.\n\nIMPORTANT: Include the [[spell:...]] marker exactly as shown in your response - it becomes a clickable spell link!"
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

        # Query trainer table to get class trainers, then get their spells
        # trainer.Type = 0 means class trainer, trainer.Requirement = class ID
        # Try with spell_dbc first, fall back to no-DBC query if table doesn't exist
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
            # spell_dbc table might not exist, query without it
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
            # Try spell_dbc name first, then SPELL_NAMES (49k spells), then generic
            name = s.get('spell_name') or SPELL_NAMES.get(spell_id) or "Spell"
            desc = SPELL_DESCRIPTIONS.get(spell_id, "")
            cost = s['MoneyCost']
            if cost >= 10000:
                cost_str = f"{cost // 10000}g"
            elif cost >= 100:
                cost_str = f"{cost // 100}s"
            else:
                cost_str = f"{cost}c"
            # Use spell link marker - client resolves the name automatically
            spell_link = f"[[spell:{spell_id}:{name.title()}]]"
            result += f"- {spell_link} ({cost_str})"
            if desc:
                result += f" - {desc}"
            result += "\n"

        result += "\nIMPORTANT: Include the [[spell:...]] markers exactly as shown in your response - they become clickable spell links!"
        return result

    def _find_quest_giver(self, params: dict) -> str:
        """Find quest givers in a zone."""
        zone = params.get("zone", "").lower() if params.get("zone") else None
        quest_name = params.get("quest_name")

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        if quest_name:
            # Find specific quest giver (with position for distance)
            cursor.execute("""
                SELECT ct.entry as npc_entry, ct.name as npc_name, qt.ID as quest_id,
                       qt.LogTitle as quest_title, qt.QuestLevel,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
                FROM quest_template qt
                JOIN creature_queststarter cq ON qt.ID = cq.quest
                JOIN creature_template ct ON cq.id = ct.entry
                JOIN creature c ON ct.entry = c.id1
                WHERE qt.LogTitle LIKE %s
                LIMIT 5
            """, (f"%{quest_name}%",))
        else:
            # Find quest givers in zone
            zone_coords, zone_filter = self._get_zone_filter(zone) if zone else (None, "")
            cursor.execute(f"""
                SELECT ct.entry as npc_entry, ct.name as npc_name, COUNT(DISTINCT cq.quest) as quest_count,
                       c.position_x as pos_x, c.position_y as pos_y, c.map as map_id
                FROM creature_template ct
                JOIN creature c ON ct.entry = c.id1
                JOIN creature_queststarter cq ON ct.entry = cq.id
                WHERE 1=1 {zone_filter}
                GROUP BY ct.entry, c.position_x, c.position_y, c.map
                ORDER BY quest_count DESC
                LIMIT 10
            """)

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if not results:
            return f"No quest givers found{' for ' + quest_name if quest_name else ' in ' + zone if zone else ''}."

        if quest_name:
            result = f"Quest '{quest_name}' is given by:\n"
            for r in results:
                # Use both NPC and quest link markers
                npc_link = f"[[npc:{r['npc_entry']}:{r['npc_name']}]]"
                quest_link = f"[[quest:{r['quest_id']}:{r['quest_title']}:{r['QuestLevel']}]]"
                # Add distance/direction if available
                dist_info = self.format_distance_direction(r['pos_x'], r['pos_y'], r['map_id'])
                dist_str = f" ({dist_info})" if dist_info else ""
                result += f"- {npc_link}{dist_str} (Quest: {quest_link})\n"
            result += "\nIMPORTANT: Include all [[...]] markers exactly as shown - they become clickable links!"
        else:
            result = f"Quest givers in {zone or 'the world'}:\n"
            for r in results:
                npc_link = f"[[npc:{r['npc_entry']}:{r['npc_name']}]]"
                # Add distance/direction if available
                dist_info = self.format_distance_direction(r['pos_x'], r['pos_y'], r['map_id'])
                dist_str = f" ({dist_info})" if dist_info else ""
                result += f"- {npc_link}{dist_str} ({r['quest_count']} quests)\n"
        return result

    def _get_available_quests(self, params: dict) -> str:
        """Find quests available to a player at their current level in a zone."""
        zone = params.get("zone", "").lower() if params.get("zone") else None
        player_level = params.get("player_level", 1)
        player_class = params.get("player_class", "").lower()
        faction = params.get("faction", "").lower()

        if not zone:
            return "Please specify a zone to search for available quests."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        if not zone_coords:
            return f"Zone '{zone}' not found. Try a different zone name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Faction filter: Alliance=690, Horde=1101 (common quest race masks)
        # RequiredRaces=0 means available to all
        # We use a simplified approach: check if quest is available to common Alliance/Horde races
        faction_filter = ""
        if faction == "alliance":
            # Alliance race mask: Human(1)+Dwarf(4)+NightElf(8)+Gnome(64)+Draenei(1024) = 1101
            faction_filter = "AND (qt.AllowableRaces = 0 OR (qt.AllowableRaces & 1101) > 0)"
        elif faction == "horde":
            # Horde race mask: Orc(2)+Undead(16)+Tauren(32)+Troll(128)+BloodElf(512) = 690
            faction_filter = "AND (qt.AllowableRaces = 0 OR (qt.AllowableRaces & 690) > 0)"

        # Class filter: AllowableClasses in quest_template_addon
        # 0 or NULL means available to all classes
        class_mask = {
            'warrior': 1, 'paladin': 2, 'hunter': 4, 'rogue': 8,
            'priest': 16, 'death knight': 32, 'shaman': 64, 'mage': 128,
            'warlock': 256, 'druid': 1024
        }
        class_bit = class_mask.get(player_class, 0)
        class_filter = ""
        if class_bit:
            # Include quests where AllowableClasses is 0/NULL (all classes) OR matches player's class
            class_filter = f"AND (qta.AllowableClasses IS NULL OR qta.AllowableClasses = 0 OR (qta.AllowableClasses & {class_bit}) > 0)"

        # Find quests where:
        # - MinLevel <= player_level (player can pick it up)
        # - QuestLevel is reasonable (not too far below player level to be grey/trivial)
        # - Quest giver is in the specified zone
        # - Class restriction matches (or no restriction)
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
              {zone_filter}
            ORDER BY qt.QuestLevel ASC, qt.LogTitle
            LIMIT 20
        """, (player_level, max(1, player_level - 5), player_level + 10))

        quests = cursor.fetchall()
        cursor.close()
        conn.close()

        if not quests:
            return f"No quests available at level {player_level} in {zone}. You may need to level up or check a different zone."

        # Group by NPC for cleaner output
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
            for q in quest_list[:3]:  # Limit per NPC to avoid spam
                quest_link = f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]"
                level_note = f" (Lvl {q['QuestLevel']}, requires {q['MinLevel']})"
                result += f"  - {quest_link}{level_note}\n"
            if len(quest_list) > 3:
                result += f"  - ... and {len(quest_list) - 3} more quests\n"
            result += "\n"

        result += "IMPORTANT: Include the [[quest:...]] and [[npc:...]] markers exactly as shown - they become clickable links!"
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

    def _get_quest_info(self, params: dict) -> str:
        """Get detailed quest information.
        Returns ALL matching quests (handles
        Alliance/Horde variants with same name).
        """
        quest_name = params.get("quest_name", "")

        if not quest_name:
            return (
                "Please specify a quest name "
                "to look up."
            )

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get ALL matching quests (not LIMIT 1)
        # to handle faction variants
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

        # AllowableRaces bitmask:
        # Alliance: 1101(Human) | Dwarf | NElf |
        #   Gnome | Draenei = 0x4F1 = 1265
        # Horde: Orc | Undead | Tauren | Troll |
        #   BElf = 0x2B2 = 690
        # 0 = all races (neutral)
        ALLIANCE_MASK = 0x4F1
        HORDE_MASK = 0x2B2

        def get_faction_tag(races):
            if races == 0:
                return "Both factions"
            alliance = bool(
                races & ALLIANCE_MASK
            )
            horde = bool(races & HORDE_MASK)
            if alliance and horde:
                return "Both factions"
            if alliance:
                return "Alliance only"
            if horde:
                return "Horde only"
            return "Unknown faction"

        all_results = []

        for quest in quests:
            faction = get_faction_tag(
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

            # Description
            if quest['LogDescription']:
                desc = (
                    quest['LogDescription']
                    .replace('$b$b', ' ')
                    .replace('$b', ' ')[:200]
                )
                out += f"Description: {desc}...\n\n"

            # Objectives
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

            # Quest giver + location
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
                    # Just include area ID
                    # for context
                    giver_str += (
                        f" (area {area_id})"
                    )
                out += giver_str + "\n"

            # Turn in NPC
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

            # Rewards
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

            # Next quest in chain
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

    def _get_item_info(self, params: dict) -> str:
        """Get detailed item information."""
        item_name = params.get("item_name", "")

        if not item_name:
            return "Please specify an item name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT entry, name, Quality, ItemLevel, RequiredLevel,
                   class as item_class, subclass, InventoryType,
                   dmg_min1, dmg_max1, armor, stat_type1, stat_value1,
                   stat_type2, stat_value2, stat_type3, stat_value3
            FROM item_template
            WHERE name LIKE %s
            LIMIT 1
        """, (f"%{item_name}%",))

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

        # Use item link marker
        item_link = f"[[item:{item['entry']}:{item['name']}:{item['Quality']}]]"
        result = f"Item: {item_link} ({quality})\n"
        result += f"Item Level: {item['ItemLevel']}, Requires Level: {item['RequiredLevel']}\n"
        if slot:
            result += f"Slot: {slot}\n"

        # Weapon damage
        if item['dmg_min1'] > 0:
            result += f"Damage: {int(item['dmg_min1'])} - {int(item['dmg_max1'])}\n"

        # Armor
        if item['armor'] > 0:
            result += f"Armor: {item['armor']}\n"

        # Stats
        stats = []
        for i in range(1, 4):
            stat_type = item[f'stat_type{i}']
            stat_val = item[f'stat_value{i}']
            if stat_type and stat_val:
                stat_name = stat_names.get(stat_type, f'Stat{stat_type}')
                stats.append(f"+{stat_val} {stat_name}")
        if stats:
            result += f"Stats: {', '.join(stats)}\n"

        # Where it drops
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

        # Who sells it
        cursor.execute("""
            SELECT ct.name FROM npc_vendor nv
            JOIN creature_template ct ON nv.entry = ct.entry
            WHERE nv.item = %s LIMIT 3
        """, (item['entry'],))
        vendors = cursor.fetchall()
        if vendors:
            vendor_list = [v['name'] for v in vendors]
            result += f"Sold by: {', '.join(vendor_list)}\n"

        # Quest reward
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

        # First find the current item
        cursor.execute("""
            SELECT entry, name, ItemLevel, InventoryType, class as item_class, subclass
            FROM item_template
            WHERE name LIKE %s
            LIMIT 1
        """, (f"%{current_item}%",))

        current = cursor.fetchone()

        if not current:
            cursor.close()
            conn.close()
            return f"Item '{current_item}' not found."

        # Class bitmask for filtering
        class_mask = {
            'warrior': 1, 'paladin': 2, 'hunter': 4, 'rogue': 8,
            'priest': 16, 'death knight': 32, 'shaman': 64, 'mage': 128,
            'warlock': 256, 'druid': 1024
        }
        class_bit = class_mask.get(player_class, 0)

        # Preferred stats by class (stat_type IDs)
        # 3=Agi, 4=Str, 5=Int, 6=Spirit, 7=Stam, 31=Hit, 32=Crit, 38=AP, 45=SP
        class_preferred_stats = {
            'hunter': [3, 7, 31, 32, 38],      # Agi, Stam, Hit, Crit, AP
            'rogue': [3, 7, 31, 32, 38],       # Agi, Stam, Hit, Crit, AP
            'warrior': [4, 7, 31, 32, 38],     # Str, Stam, Hit, Crit, AP
            'death knight': [4, 7, 31, 32, 38],# Str, Stam, Hit, Crit, AP
            'paladin': [4, 7, 5, 31, 45],      # Str, Stam, Int, Hit, SP (hybrid)
            'shaman': [5, 7, 31, 45, 3],       # Int, Stam, Hit, SP, Agi (hybrid)
            'druid': [3, 5, 7, 31, 45],        # Agi, Int, Stam, Hit, SP (hybrid)
            'mage': [5, 7, 31, 32, 45],        # Int, Stam, Hit, Crit, SP
            'warlock': [5, 7, 31, 32, 45],     # Int, Stam, Hit, Crit, SP
            'priest': [5, 6, 7, 31, 45],       # Int, Spirit, Stam, Hit, SP
        }
        preferred_stats = class_preferred_stats.get(player_class, [])

        # Build stat filter if we have class preferences
        stat_filter = ""
        if preferred_stats:
            stat_conditions = []
            for stat in preferred_stats:
                stat_conditions.append(f"stat_type1 = {stat} OR stat_type2 = {stat} OR stat_type3 = {stat}")
            stat_filter = f"AND ({' OR '.join(stat_conditions)})"

        # Find upgrades - same slot, higher item level, appropriate stats
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

        quality_names = {0: 'Poor/Gray', 1: 'Common/White', 2: 'Uncommon/Green', 3: 'Rare/Blue', 4: 'Epic/Purple', 5: 'Legendary/Orange'}
        stat_names = {3: 'Agi', 4: 'Str', 5: 'Int', 6: 'Spi', 7: 'Stam', 31: 'Hit', 32: 'Crit', 38: 'AP', 45: 'SP'}

        result = f"Upgrades for {current['name']} (iLvl {current['ItemLevel']}) for {player_class}:\n"
        for u in upgrades:
            quality = quality_names.get(u['Quality'], '')
            stats = []
            if u['stat_type1'] and u['stat_value1']:
                stats.append(f"+{u['stat_value1']} {stat_names.get(u['stat_type1'], '?')}")
            if u['stat_type2'] and u['stat_value2']:
                stats.append(f"+{u['stat_value2']} {stat_names.get(u['stat_type2'], '?')}")
            stat_str = f" [{', '.join(stats)}]" if stats else ""
            # Use item link marker
            item_link = f"[[item:{u['entry']}:{u['name']}:{u['Quality']}]]"
            result += f"- {item_link} (iLvl {u['ItemLevel']}, req {u['RequiredLevel']}){stat_str}\n"

        result += "\nIMPORTANT: Include the [[item:...]] markers exactly as shown - they become clickable item links!"
        return result

    def _get_dungeon_info(self, params: dict) -> str:
        """Get dungeon/instance information from database."""
        dungeon_name = params.get("dungeon_name", "").lower()

        if not dungeon_name:
            return "Please specify a dungeon name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Search dungeon_access_template by name (comment field)
        cursor.execute("""
            SELECT DISTINCT dat.id, dat.map_id, dat.min_level, dat.max_level,
                   dat.min_avg_item_level, dat.difficulty, dat.comment as name
            FROM dungeon_access_template dat
            WHERE LOWER(dat.comment) LIKE %s
            ORDER BY dat.difficulty, dat.min_level
        """, (f"%{dungeon_name}%",))

        dungeons = cursor.fetchall()

        if not dungeons:
            # Try partial match with common abbreviations
            cursor.execute("""
                SELECT DISTINCT dat.id, dat.map_id, dat.min_level, dat.max_level,
                       dat.min_avg_item_level, dat.difficulty, dat.comment as name
                FROM dungeon_access_template dat
                ORDER BY dat.min_level
                LIMIT 30
            """)
            all_dungeons = cursor.fetchall()
            cursor.close()
            conn.close()
            # Show sample dungeons
            sample = [d['name'] for d in all_dungeons[:15]]
            return f"Dungeon '{dungeon_name}' not found. Try names like: {', '.join(sample)}"

        # Get the primary dungeon (normal mode)
        primary = dungeons[0]
        map_id = primary['map_id']

        # Get requirements for this dungeon
        cursor.execute("""
            SELECT dar.requirement_type, dar.requirement_id, dar.requirement_note,
                   dar.faction, dar.comment
            FROM dungeon_access_requirements dar
            WHERE dar.dungeon_access_id = %s
        """, (primary['id'],))
        requirements = cursor.fetchall()

        cursor.close()
        conn.close()

        # Build response
        result = f"**{primary['name']}**\n"

        # Level info
        if primary['max_level'] and primary['max_level'] > 0:
            result += f"Level: {primary['min_level']}-{primary['max_level']}\n"
        else:
            result += f"Minimum Level: {primary['min_level']}\n"

        # Item level requirement (for WotLK heroics)
        if primary['min_avg_item_level'] and primary['min_avg_item_level'] > 0:
            result += f"Required Item Level: {primary['min_avg_item_level']}\n"

        # Location from our mapping
        location = self.DUNGEON_LOCATIONS.get(map_id, "Unknown")
        result += f"Location: {location}\n"

        # Difficulty modes available
        difficulty_names = {0: 'Normal', 1: 'Heroic', 2: '10-man Heroic', 3: '25-man Heroic'}
        modes = list(set(d['difficulty'] for d in dungeons))
        mode_str = ', '.join(difficulty_names.get(m, f'Mode {m}') for m in sorted(modes))
        if len(modes) > 1:
            result += f"Modes: {mode_str}\n"

        # Requirements
        if requirements:
            result += "\n**Entry Requirements:**\n"
            for req in requirements:
                req_type = "Quest" if req['requirement_type'] == 1 else "Key/Item"
                faction = {0: 'Alliance', 1: 'Horde', 2: 'Both'}.get(req['faction'], 'Both')
                note = req['requirement_note'] or req['comment'] or ''
                if faction != 'Both':
                    result += f"- {req_type}: {note} ({faction} only)\n"
                else:
                    result += f"- {req_type}: {note}\n"

        return result

    def _find_hunter_pet(self, params: dict) -> str:
        """Find tameable beasts for hunters."""
        pet_family = params.get("pet_family", "").lower()
        zone = params.get("zone", "").lower() if params.get("zone") else None
        max_level = params.get("max_level", 80)

        # Find family ID from name
        family_id = None
        family_info = None
        for fid, finfo in self.PET_FAMILIES.items():
            if pet_family and pet_family in finfo['name'].lower():
                family_id = fid
                family_info = finfo
                break

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        zone_coords, zone_filter = self._get_zone_filter(zone) if zone else (None, "")

        # Build query
        if family_id:
            cursor.execute(f"""
                SELECT DISTINCT ct.entry, ct.name, ct.minlevel, ct.maxlevel
                FROM creature_template ct
                JOIN creature c ON ct.entry = c.id1
                WHERE ct.type = 1 AND ct.family = %s
                  AND ct.minlevel <= %s
                  {zone_filter}
                ORDER BY ct.minlevel
                LIMIT 10
            """, (family_id, max_level))
        else:
            cursor.execute(f"""
                SELECT DISTINCT ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.family
                FROM creature_template ct
                JOIN creature c ON ct.entry = c.id1
                WHERE ct.type = 1 AND ct.family > 0
                  AND ct.minlevel <= %s
                  {zone_filter}
                ORDER BY ct.minlevel
                LIMIT 15
            """, (max_level,))

        pets = cursor.fetchall()
        cursor.close()
        conn.close()

        if not pets:
            return f"No tameable pets found{' of type ' + pet_family if pet_family else ''}{' in ' + zone if zone else ''} up to level {max_level}."

        if family_info:
            result = f"Tameable {family_info['name']}s ({family_info['type']} pet, eats: {family_info['diet']}):\n"
        else:
            result = f"Tameable pets{' in ' + zone if zone else ''}:\n"

        for p in pets:
            lvl = f"Level {p['minlevel']}" if p['minlevel'] == p['maxlevel'] else f"Level {p['minlevel']}-{p['maxlevel']}"
            fam_name = ""
            if not family_id and p.get('family'):
                fam_info = self.PET_FAMILIES.get(p['family'], {})
                fam_name = f" ({fam_info.get('name', 'Unknown')})" if fam_info else ""
            npc_link = f"[[npc:{p['entry']}:{p['name']}]]"
            result += f"- {npc_link} - {lvl}{fam_name}\n"

        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored links!"
        return result

    def _find_recipe_source(self, params: dict) -> str:
        """Find where to learn a profession recipe."""
        recipe_name = params.get("recipe_name", "")
        profession = params.get("profession", "").lower()

        if not recipe_name:
            return "Please specify a recipe or item name to craft."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # First, find the recipe item (Pattern:, Plans:, Schematic:, etc.)
        cursor.execute("""
            SELECT entry, name, Quality FROM item_template
            WHERE name LIKE %s OR name LIKE %s OR name LIKE %s OR name LIKE %s
            LIMIT 5
        """, (f"Pattern: %{recipe_name}%", f"Plans: %{recipe_name}%",
              f"Schematic: %{recipe_name}%", f"Recipe: %{recipe_name}%"))

        recipes = cursor.fetchall()

        results = []
        for recipe in recipes:
            # Check if trainable
            cursor.execute("""
                SELECT ts.ReqSkillRank, ct.entry as trainer_entry, ct.name as trainer_name, ct.subname
                FROM trainer_spell ts
                JOIN creature_default_trainer cdt ON ts.TrainerId = cdt.TrainerId
                JOIN creature_template ct ON cdt.CreatureId = ct.entry
                WHERE ts.SpellId IN (
                    SELECT spellid_1 FROM item_template WHERE entry = %s
                    UNION SELECT spellid_2 FROM item_template WHERE entry = %s
                )
                LIMIT 3
            """, (recipe['entry'], recipe['entry']))
            trainers = cursor.fetchall()

            # Check vendor sources
            cursor.execute("""
                SELECT ct.entry as vendor_entry, ct.name as vendor_name, ct.subname
                FROM npc_vendor nv
                JOIN creature_template ct ON nv.entry = ct.entry
                WHERE nv.item = %s
                LIMIT 3
            """, (recipe['entry'],))
            vendors = cursor.fetchall()

            # Check drop sources
            cursor.execute("""
                SELECT ct.entry, ct.name, cl.Chance
                FROM creature_loot_template cl
                JOIN creature_template ct ON cl.Entry = ct.lootid
                WHERE cl.Item = %s AND cl.Chance > 0
                ORDER BY cl.Chance DESC
                LIMIT 3
            """, (recipe['entry'],))
            drops = cursor.fetchall()

            # Use item link for recipe
            recipe_link = f"[[item:{recipe['entry']}:{recipe['name']}:{recipe['Quality']}]]"
            result = f"Recipe: {recipe_link}\n"
            if trainers:
                trainer_links = [f"[[npc:{t['trainer_entry']}:{t['trainer_name']}]]" for t in trainers]
                result += f"  Trained by: {', '.join(trainer_links)}\n"
            if vendors:
                vendor_links = [f"[[npc:{v['vendor_entry']}:{v['vendor_name']}]]" for v in vendors]
                result += f"  Sold by: {', '.join(vendor_links)}\n"
            if drops:
                drop_links = [f"[[npc:{d['entry']}:{d['name']}]] ({d['Chance']:.1f}%)" for d in drops]
                result += f"  Drops from: {', '.join(drop_links)}\n"
            if not trainers and not vendors and not drops:
                result += "  Source: Unknown (may be quest reward or world drop)\n"

            results.append(result)

        cursor.close()
        conn.close()

        if not results:
            return f"Recipe for '{recipe_name}' not found. Try a different name or check if it's a trainer-only recipe."

        final_result = "\n".join(results)
        final_result += "\nIMPORTANT: Include the [[item:...]] markers exactly as shown - they become clickable item links!"
        return final_result

    def _get_flight_paths(self, params: dict) -> str:
        """Get flight path information."""
        from_location = params.get("from_location", "").lower()
        to_location = params.get("to_location", "").lower() if params.get("to_location") else None
        faction = params.get("faction", "").lower()

        if not from_location:
            return "Please specify a starting location."

        # Boat routes (both factions)
        boat_routes = {
            'menethil harbor': ['auberdine', 'theramore', 'howling fjord (valgarde)'],
            'auberdine': ['menethil harbor', 'stormwind harbor (via darnassus)'],
            'stormwind harbor': ['auberdine (via darnassus)', 'borean tundra (valiance keep)'],
            'theramore': ['menethil harbor'],
            'ratchet': ['booty bay'],
            'booty bay': ['ratchet'],
            'undercity': ['howling fjord (vengeance landing)'],
            'orgrimmar': ['borean tundra (warsong hold)'],
        }

        # Get flight paths based on faction
        flight_paths = {}
        if faction == 'alliance' or not faction:
            flight_paths.update(self.FLIGHT_PATHS_ALLIANCE)
        if faction == 'horde' or not faction:
            flight_paths.update(self.FLIGHT_PATHS_HORDE)

        # Find from location
        from_key = None
        for key in flight_paths.keys():
            if from_location in key or key in from_location:
                from_key = key
                break

        result = f"Travel from {from_location.title()}:\n\n"

        # Flight paths
        if from_key and from_key in flight_paths:
            connections = flight_paths[from_key]
            result += "Flight paths to:\n"
            for dest in connections:
                result += f"- {dest.title()}\n"
        else:
            result += f"No flight paths found from {from_location}. Check if you have the flight point.\n"

        # Boat routes
        boat_key = None
        for key in boat_routes.keys():
            if from_location in key or key in from_location:
                boat_key = key
                break

        if boat_key and boat_key in boat_routes:
            result += "\nBoat routes to:\n"
            for dest in boat_routes[boat_key]:
                result += f"- {dest.title()}\n"

        # If looking for specific destination
        if to_location:
            result += f"\nTo reach {to_location.title()}: "
            # Simple path suggestion (could be enhanced)
            result += "Check flight master for direct flight, or take connecting flights/boats."

        return result

    def _get_boss_loot(self, params: dict) -> str:
        """Get loot table for a boss with item links."""
        boss_name = params.get("boss_name", "")
        dungeon = params.get("dungeon", "").lower() if params.get("dungeon") else None

        if not boss_name:
            return "Please specify a boss name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Find the boss creature
        cursor.execute("""
            SELECT entry, name, `rank`
            FROM creature_template
            WHERE name LIKE %s AND `rank` IN (1, 3)
            ORDER BY `rank` DESC
            LIMIT 5
        """, (f"%{boss_name}%",))

        bosses = cursor.fetchall()

        if not bosses:
            # Try without rank filter for named NPCs
            cursor.execute("""
                SELECT entry, name, `rank`
                FROM creature_template
                WHERE name LIKE %s
                ORDER BY `rank` DESC
                LIMIT 5
            """, (f"%{boss_name}%",))
            bosses = cursor.fetchall()

        if not bosses:
            cursor.close()
            conn.close()
            return f"Boss '{boss_name}' not found."

        # Use the first (highest rank) boss
        boss = bosses[0]
        boss_entry = boss['entry']

        # Get loot from creature_loot_template
        # Note: Some bosses use reference loot (Reference > 0)
        cursor.execute("""
            SELECT it.entry as item_id, it.name, it.Quality, clt.Chance
            FROM creature_loot_template clt
            JOIN item_template it ON clt.Item = it.entry
            WHERE clt.Entry = %s AND clt.Chance > 0
            ORDER BY it.Quality DESC, clt.Chance DESC
            LIMIT 15
        """, (boss_entry,))

        direct_loot = cursor.fetchall()

        # Also check reference loot tables (common for bosses)
        # Chance=0 in reference table means equal weight among items in that group
        cursor.execute("""
            SELECT it.entry as item_id, it.name, it.Quality, clt.Chance as ref_chance
            FROM creature_loot_template clt
            JOIN reference_loot_template rlt ON clt.Reference = rlt.Entry
            JOIN item_template it ON rlt.Item = it.entry
            WHERE clt.Entry = %s AND clt.Reference > 0
            ORDER BY it.Quality DESC, clt.Chance DESC
            LIMIT 15
        """, (boss_entry,))

        reference_loot = cursor.fetchall()

        cursor.close()
        conn.close()

        # Normalize chance column name from reference loot
        for item in reference_loot:
            if 'ref_chance' in item:
                item['Chance'] = item['ref_chance']

        # Combine and deduplicate
        seen_items = set()
        all_loot = []
        for item in direct_loot + reference_loot:
            if item['item_id'] not in seen_items:
                seen_items.add(item['item_id'])
                all_loot.append(item)

        # Sort by quality then chance
        all_loot.sort(key=lambda x: (-x['Quality'], -x.get('Chance', 0)))

        if not all_loot:
            return f"No loot data found for {boss['name']}. This boss may use a special loot system."

        quality_names = {0: 'Poor/Gray', 1: 'Common/White', 2: 'Uncommon/Green', 3: 'Rare/Blue', 4: 'Epic/Purple', 5: 'Legendary/Orange'}
        rank_names = {1: 'Elite', 3: 'Boss'}

        rank_str = f" ({rank_names.get(boss['rank'], '')})" if boss['rank'] in rank_names else ""
        result = f"Loot from {boss['name']}{rank_str}:\n\n"

        for item in all_loot[:12]:  # Limit to 12 items
            quality = quality_names.get(item['Quality'], 'Unknown')
            chance = item['Chance']

            # Use the [[item:ID:Name:Quality]] format for the C++ side to convert
            # Format: [[item:entry:name:quality]]
            item_link = f"[[item:{item['item_id']}:{item['name']}:{item['Quality']}]]"

            if chance >= 100:
                result += f"- {item_link} ({quality}) - Guaranteed\n"
            elif chance >= 50:
                result += f"- {item_link} ({quality}) - {chance:.0f}% drop\n"
            else:
                result += f"- {item_link} ({quality}) - {chance:.1f}% drop\n"

        result += "\nIMPORTANT: Include the [[item:...]] markers exactly as shown above in your response - they become clickable item links for the player!"
        return result

    def _get_creature_loot(self, params: dict) -> str:
        """Get loot table for a regular creature with item links."""
        creature_name = params.get("creature_name", "")
        zone = params.get("zone", "").lower() if params.get("zone") else None

        if not creature_name:
            return "Please specify a creature name."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        zone_coords, zone_filter = self._get_zone_filter(zone) if zone else (None, "")

        # Find the creature
        cursor.execute(f"""
            SELECT DISTINCT ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.lootid
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE ct.name LIKE %s {zone_filter}
            LIMIT 5
        """, (f"%{creature_name}%",))

        creatures = cursor.fetchall()

        if not creatures:
            cursor.close()
            conn.close()
            return f"Creature '{creature_name}' not found{' in ' + zone if zone else ''}."

        # Use the first creature
        creature = creatures[0]
        loot_id = creature['lootid'] if creature['lootid'] else creature['entry']

        # Get loot from creature_loot_template
        cursor.execute("""
            SELECT it.entry as item_id, it.name, it.Quality, clt.Chance
            FROM creature_loot_template clt
            JOIN item_template it ON clt.Item = it.entry
            WHERE clt.Entry = %s AND clt.Chance > 0
            ORDER BY it.Quality DESC, clt.Chance DESC
            LIMIT 12
        """, (loot_id,))

        loot = cursor.fetchall()

        # Also check reference loot (Chance=0 in reference table means equal weight)
        # The actual drop chance comes from creature_loot_template.Chance for the reference
        # Order by Quality DESC first so we get rare/epic items even at low drop rates
        cursor.execute("""
            SELECT it.entry as item_id, it.name, it.Quality, clt.Chance as ref_chance
            FROM creature_loot_template clt
            JOIN reference_loot_template rlt ON clt.Reference = rlt.Entry
            JOIN item_template it ON rlt.Item = it.entry
            WHERE clt.Entry = %s AND clt.Reference > 0
            ORDER BY it.Quality DESC, clt.Chance DESC
            LIMIT 25
        """, (loot_id,))

        reference_loot = cursor.fetchall()

        cursor.close()
        conn.close()

        # Normalize chance column name from reference loot
        for item in reference_loot:
            if 'ref_chance' in item:
                item['Chance'] = item['ref_chance']

        # Combine all loot
        seen_items = set()
        all_items = []
        for item in loot + reference_loot:
            if item['item_id'] not in seen_items:
                seen_items.add(item['item_id'])
                all_items.append(item)

        if not all_items:
            return f"No loot data found for {creature['name']}. This creature may not have a loot table."

        # Separate by quality: show valuable items first, then a few common ones
        epic_rare = [i for i in all_items if i['Quality'] >= 3]  # Blue+
        uncommon = [i for i in all_items if i['Quality'] == 2]   # Green
        common = [i for i in all_items if i['Quality'] <= 1]     # White/Grey

        # Sort each tier by drop chance
        epic_rare.sort(key=lambda x: -x.get('Chance', 0))
        uncommon.sort(key=lambda x: -x.get('Chance', 0))
        common.sort(key=lambda x: -x.get('Chance', 0))

        # Build final list: up to 3 rare, up to 5 green, up to 3 common
        all_loot = epic_rare[:3] + uncommon[:5] + common[:3]

        quality_names = {0: 'Poor/Gray', 1: 'Common/White', 2: 'Uncommon/Green', 3: 'Rare/Blue', 4: 'Epic/Purple', 5: 'Legendary/Orange'}

        lvl_str = f"Level {creature['minlevel']}" if creature['minlevel'] == creature['maxlevel'] else f"Level {creature['minlevel']}-{creature['maxlevel']}"
        result = f"Loot from {creature['name']} ({lvl_str}):\n\n"

        for item in all_loot:
            quality = quality_names.get(item['Quality'], 'Unknown')
            chance = item['Chance']

            item_link = f"[[item:{item['item_id']}:{item['name']}:{item['Quality']}]]"

            if chance >= 100:
                result += f"- {item_link} ({quality}) - Guaranteed\n"
            elif chance >= 50:
                result += f"- {item_link} ({quality}) - {chance:.0f}%\n"
            elif chance >= 1:
                result += f"- {item_link} ({quality}) - {chance:.1f}%\n"
            else:
                result += f"- {item_link} ({quality}) - {chance:.2f}%\n"

        result += "\nIMPORTANT: Include the [[item:...]] markers exactly as shown above in your response - they become clickable item links for the player!"
        return result

    # Lock ID to skill requirement mappings for gathering
    HERB_SKILL_MAP = {
        29: 1, 30: 15, 9: 50, 31: 70, 11: 85, 519: 85, 33: 105, 32: 115,
        45: 125, 27: 150, 47: 160, 521: 170, 49: 185, 51: 195, 50: 205,
        439: 210, 440: 220, 441: 230, 442: 235, 443: 245, 444: 250,
        1119: 260, 1120: 270, 1121: 280, 1122: 285, 1123: 290, 1124: 300,
        1639: 315, 1641: 325, 1642: 335, 1643: 340, 1644: 350, 1645: 365,
        1646: 375, 1787: 385, 1788: 400, 1789: 425, 1790: 435, 1792: 450
    }

    MINING_SKILL_MAP = {
        38: 1, 39: 65, 40: 75, 41: 125, 42: 155, 379: 175, 380: 230,
        400: 245, 719: 230, 939: 275, 1649: 300, 1650: 325, 1651: 375,
        1652: 350, 1800: 350, 1782: 375, 1783: 400, 1784: 425, 1785: 450
    }

    def _get_zone_fishing(self, params: dict) -> str:
        """Get fishing information for a zone."""
        zone = params.get("zone", "").lower()
        if not zone:
            return "Please specify a zone name."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        if not zone_coords:
            return f"Zone '{zone}' not found. Try zones like: darkshore, westfall, stranglethorn."

        zone_id = zone_coords.get('zone_id')
        if not zone_id:
            return f"Could not determine zone ID for '{zone}'."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get fishing skill requirement for the zone
        cursor.execute("""
            SELECT skill FROM skill_fishing_base_level WHERE entry = %s
        """, (zone_id,))
        skill_row = cursor.fetchone()

        if skill_row:
            base_skill = skill_row['skill']
            if base_skill < 0:
                no_getaway_skill = base_skill + 95
            else:
                no_getaway_skill = base_skill + 75
        else:
            no_getaway_skill = None

        # Get fish from fishing_loot_template (resolve references)
        cursor.execute("""
            SELECT
                COALESCE(r.Item, f.Item) AS item_id,
                i.name AS item_name,
                COALESCE(r.Chance, f.Chance) AS chance,
                COALESCE(r.QuestRequired, f.QuestRequired) AS quest_required
            FROM fishing_loot_template f
            LEFT JOIN reference_loot_template r ON f.Reference = r.Entry AND f.Reference != 0
            JOIN item_template i ON i.entry = COALESCE(r.Item, f.Item)
            WHERE f.Entry = %s AND f.LootMode = 1
            ORDER BY COALESCE(r.Chance, f.Chance) DESC, i.name
        """, (zone_id,))

        fish = cursor.fetchall()
        cursor.close()
        conn.close()

        if not fish:
            return f"No fishing data found for {zone}. Fishing may not be available or the zone ID ({zone_id}) may not have fishing loot."

        result = f"Fishing in {zone.title()}:\n\n"

        if no_getaway_skill:
            result += f"Skill requirement: {no_getaway_skill} (to avoid fish getting away)\n\n"

        result += "Fish and catches:\n"
        for f in fish:
            chance = f['chance']
            quest_note = " (Quest)" if f['quest_required'] else ""

            if chance >= 50:
                result += f"- {f['item_name']} - {chance:.0f}%{quest_note}\n"
            elif chance >= 1:
                result += f"- {f['item_name']} - {chance:.1f}%{quest_note}\n"
            elif chance > 0:
                result += f"- {f['item_name']} - {chance:.2f}% (rare){quest_note}\n"
            else:
                result += f"- {f['item_name']} - common catch{quest_note}\n"

        return result

    def _get_zone_herbs(self, params: dict) -> str:
        """Get herbs that can be gathered in a zone."""
        zone = params.get("zone", "").lower()
        if not zone:
            return "Please specify a zone name."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        if not zone_coords:
            return f"Zone '{zone}' not found. Try zones like: darkshore, ashenvale, felwood."

        # Build gameobject coordinate filter (zone_filter uses 'c.' prefix for creatures)
        go_zone_filter = zone_filter.replace('c.map', 'g.map').replace('c.position_x', 'g.position_x').replace('c.position_y', 'g.position_y')

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get herbs in the zone using coordinates (zoneId often empty)
        cursor.execute(f"""
            SELECT
                gt.name AS node_name,
                gt.Data0 AS lock_id,
                it.entry AS item_id,
                it.name AS herb_name,
                COUNT(g.guid) AS spawn_count
            FROM gameobject g
            JOIN gameobject_template gt ON g.id = gt.entry
            JOIN gameobject_loot_template glt ON gt.Data1 = glt.Entry
            JOIN item_template it ON glt.Item = it.entry
            WHERE 1=1 {go_zone_filter}
              AND gt.type = 3
              AND it.class = 7 AND it.subclass = 9
              AND glt.Chance >= 90
            GROUP BY gt.name, gt.Data0, it.entry, it.name
            ORDER BY gt.Data0, gt.name
        """)

        herbs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not herbs:
            return f"No herbs found in {zone}. This zone may not have herbalism nodes."

        result = f"Herbs in {zone.title()}:\n\n"

        for h in herbs:
            skill = self.HERB_SKILL_MAP.get(h['lock_id'], 0)
            result += f"- {h['herb_name']} (Skill: {skill}) - {h['spawn_count']} spawn points\n"

        return result

    def _get_zone_mining(self, params: dict) -> str:
        """Get mining nodes and ores in a zone."""
        zone = params.get("zone", "").lower()
        if not zone:
            return "Please specify a zone name."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        if not zone_coords:
            return f"Zone '{zone}' not found. Try zones like: dun morogh, westfall, badlands."

        # Build gameobject coordinate filter (zone_filter uses 'c.' prefix for creatures)
        go_zone_filter = zone_filter.replace('c.map', 'g.map').replace('c.position_x', 'g.position_x').replace('c.position_y', 'g.position_y')

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get mining nodes in the zone using coordinates (zoneId often empty)
        cursor.execute(f"""
            SELECT
                gt.name AS node_name,
                gt.Data0 AS lock_id,
                it.entry AS item_id,
                it.name AS ore_name,
                COUNT(g.guid) AS spawn_count
            FROM gameobject g
            JOIN gameobject_template gt ON g.id = gt.entry
            JOIN gameobject_loot_template glt ON gt.Data1 = glt.Entry
            JOIN item_template it ON glt.Item = it.entry
            WHERE 1=1 {go_zone_filter}
              AND gt.type = 3
              AND it.class = 7 AND it.subclass = 7
              AND glt.Chance >= 90
            GROUP BY gt.name, gt.Data0, it.entry, it.name
            ORDER BY gt.Data0, gt.name
        """)

        nodes = cursor.fetchall()
        cursor.close()
        conn.close()

        if not nodes:
            return f"No mining nodes found in {zone}. This zone may not have mining deposits."

        result = f"Mining in {zone.title()}:\n\n"

        for n in nodes:
            skill = self.MINING_SKILL_MAP.get(n['lock_id'], 0)
            result += f"- {n['ore_name']} from {n['node_name']} (Skill: {skill}) - {n['spawn_count']} spawn points\n"

        return result

    def _list_zone_creatures(self, params: dict) -> str:
        """List hostile creatures in a zone."""
        zone = params.get("zone", "").lower()
        level_min = params.get("level_min")
        level_max = params.get("level_max")

        if not zone:
            return "Please specify a zone name."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        if not zone_coords:
            return f"Zone '{zone}' not found. Try zones like: darkshore, westfall, barrens."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Build level filter
        level_filter = ""
        if level_min:
            level_filter += f" AND ct.maxlevel >= {int(level_min)}"
        if level_max:
            level_filter += f" AND ct.minlevel <= {int(level_max)}"

        # Get hostile creatures in the zone using coordinate bounds
        # Note: zoneId field is often empty, so we use coordinates instead
        cursor.execute(f"""
            SELECT DISTINCT
                ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.`rank`,
                COUNT(c.guid) AS spawn_count
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE 1=1 {zone_filter}
              AND ct.faction IN (14, 16, 17, 19, 20, 21, 22, 24, 28, 32, 34, 45, 48, 54, 55, 56, 60, 64, 80, 85, 87, 90, 93, 168)
              AND ct.unit_flags NOT IN (33554432, 67108864)
              AND ct.name NOT LIKE '%%Trigger%%'
              AND ct.name NOT LIKE '%%Invisible%%'
              AND ct.name NOT LIKE '%%DND%%'
              AND ct.name NOT LIKE '%%Bunny%%'
              {level_filter}
            GROUP BY ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.`rank`
            ORDER BY ct.minlevel, ct.name
            LIMIT 25
        """)

        creatures = cursor.fetchall()
        cursor.close()
        conn.close()

        if not creatures:
            return f"No hostile creatures found in {zone}. The zone may be a city or safe area."

        rank_names = {0: '', 1: ' (Elite)', 2: ' (Rare Elite)', 3: ' (Boss)', 4: ' (Rare)'}

        result = f"Creatures in {zone.title()}:\n\n"

        for c in creatures:
            lvl = f"Level {c['minlevel']}" if c['minlevel'] == c['maxlevel'] else f"Level {c['minlevel']}-{c['maxlevel']}"
            rank = rank_names.get(c['rank'], '')
            npc_link = f"[[npc:{c['entry']}:{c['name']}]]"
            result += f"- {npc_link} - {lvl}{rank}\n"

        result += "\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored links!"
        return result

    def _find_rare_spawn(self, params: dict) -> str:
        """Find rare spawn mobs in a zone."""
        zone = params.get("zone", "").lower()

        if not zone:
            return "Please specify a zone name."

        zone_coords, zone_filter = self._get_zone_filter(zone)
        if not zone_coords:
            return f"Zone '{zone}' not found. Try zones like: darkshore, westfall, barrens."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Use coordinate-based filtering (zoneId column often unpopulated)
        # zone_filter starts with AND, so we use WHERE 1=1 as base
        # Find rare mobs (rank = 4) in the zone
        cursor.execute(f"""
            SELECT DISTINCT
                ct.entry, ct.name, ct.minlevel, ct.maxlevel,
                COUNT(c.guid) AS spawn_count,
                AVG(c.position_x) AS avg_x,
                AVG(c.position_y) AS avg_y
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE 1=1 {zone_filter}
              AND ct.`rank` = 4
              AND ct.name NOT LIKE '%%Trigger%%'
              AND ct.name NOT LIKE '%%Invisible%%'
              AND ct.name NOT LIKE '%%DND%%'
            GROUP BY ct.entry, ct.name, ct.minlevel, ct.maxlevel
            ORDER BY ct.minlevel, ct.name
        """)

        rares = cursor.fetchall()

        # Also check for rare elites (rank = 2)
        cursor.execute(f"""
            SELECT DISTINCT
                ct.entry, ct.name, ct.minlevel, ct.maxlevel,
                COUNT(c.guid) AS spawn_count
            FROM creature_template ct
            JOIN creature c ON ct.entry = c.id1
            WHERE 1=1 {zone_filter}
              AND ct.`rank` = 2
              AND ct.name NOT LIKE '%%Trigger%%'
              AND ct.name NOT LIKE '%%Invisible%%'
            GROUP BY ct.entry, ct.name, ct.minlevel, ct.maxlevel
            ORDER BY ct.minlevel, ct.name
        """)

        rare_elites = cursor.fetchall()
        cursor.close()
        conn.close()

        if not rares and not rare_elites:
            return f"No rare spawns found in {zone}."

        result = f"Rare Spawns in {zone.title()}:\n\n"

        if rares:
            result += "**Rares:**\n"
            for r in rares:
                lvl = f"Level {r['minlevel']}" if r['minlevel'] == r['maxlevel'] else f"Level {r['minlevel']}-{r['maxlevel']}"
                npc_link = f"[[npc:{r['entry']}:{r['name']}]]"
                result += f"- {npc_link} - {lvl} ({r['spawn_count']} spawn point(s))\n"

        if rare_elites:
            result += "\n**Rare Elites:**\n"
            for r in rare_elites:
                lvl = f"Level {r['minlevel']}" if r['minlevel'] == r['maxlevel'] else f"Level {r['minlevel']}-{r['maxlevel']}"
                npc_link = f"[[npc:{r['entry']}:{r['name']}]]"
                result += f"- {npc_link} - {lvl} ({r['spawn_count']} spawn point(s))\n"

        result += "\nNote: Rare spawns have long respawn timers (hours to days)."
        result += "\n\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored links!"
        return result

    # Zone info data (not stored in DB in queryable form)
    ZONE_INFO = {
        "elwynn forest": {"level_min": 1, "level_max": 10, "faction": "Alliance", "continent": "Eastern Kingdoms", "capital": "Stormwind City"},
        "dun morogh": {"level_min": 1, "level_max": 10, "faction": "Alliance", "continent": "Eastern Kingdoms", "capital": "Ironforge"},
        "teldrassil": {"level_min": 1, "level_max": 10, "faction": "Alliance", "continent": "Kalimdor", "capital": "Darnassus"},
        "tirisfal glades": {"level_min": 1, "level_max": 10, "faction": "Horde", "continent": "Eastern Kingdoms", "capital": "Undercity"},
        "durotar": {"level_min": 1, "level_max": 10, "faction": "Horde", "continent": "Kalimdor", "capital": "Orgrimmar"},
        "mulgore": {"level_min": 1, "level_max": 10, "faction": "Horde", "continent": "Kalimdor", "capital": "Thunder Bluff"},
        "eversong woods": {"level_min": 1, "level_max": 10, "faction": "Horde", "continent": "Eastern Kingdoms", "capital": "Silvermoon City"},
        "azuremyst isle": {"level_min": 1, "level_max": 10, "faction": "Alliance", "continent": "Kalimdor", "capital": "The Exodar"},
        "westfall": {"level_min": 10, "level_max": 20, "faction": "Alliance", "continent": "Eastern Kingdoms"},
        "loch modan": {"level_min": 10, "level_max": 20, "faction": "Alliance", "continent": "Eastern Kingdoms"},
        "darkshore": {"level_min": 10, "level_max": 20, "faction": "Alliance", "continent": "Kalimdor"},
        "bloodmyst isle": {"level_min": 10, "level_max": 20, "faction": "Alliance", "continent": "Kalimdor"},
        "silverpine forest": {"level_min": 10, "level_max": 20, "faction": "Horde", "continent": "Eastern Kingdoms"},
        "the barrens": {"level_min": 10, "level_max": 25, "faction": "Horde", "continent": "Kalimdor"},
        "ghostlands": {"level_min": 10, "level_max": 20, "faction": "Horde", "continent": "Eastern Kingdoms"},
        "redridge mountains": {"level_min": 15, "level_max": 25, "faction": "Alliance", "continent": "Eastern Kingdoms"},
        "duskwood": {"level_min": 20, "level_max": 30, "faction": "Alliance", "continent": "Eastern Kingdoms"},
        "wetlands": {"level_min": 20, "level_max": 30, "faction": "Alliance", "continent": "Eastern Kingdoms"},
        "ashenvale": {"level_min": 20, "level_max": 30, "faction": "Contested", "continent": "Kalimdor"},
        "hillsbrad foothills": {"level_min": 20, "level_max": 30, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "stonetalon mountains": {"level_min": 15, "level_max": 27, "faction": "Contested", "continent": "Kalimdor"},
        "thousand needles": {"level_min": 25, "level_max": 35, "faction": "Contested", "continent": "Kalimdor"},
        "desolace": {"level_min": 30, "level_max": 40, "faction": "Contested", "continent": "Kalimdor"},
        "arathi highlands": {"level_min": 30, "level_max": 40, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "stranglethorn vale": {"level_min": 30, "level_max": 45, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "dustwallow marsh": {"level_min": 35, "level_max": 45, "faction": "Contested", "continent": "Kalimdor"},
        "badlands": {"level_min": 35, "level_max": 45, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "swamp of sorrows": {"level_min": 35, "level_max": 45, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "feralas": {"level_min": 40, "level_max": 50, "faction": "Contested", "continent": "Kalimdor"},
        "tanaris": {"level_min": 40, "level_max": 50, "faction": "Contested", "continent": "Kalimdor"},
        "the hinterlands": {"level_min": 40, "level_max": 50, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "searing gorge": {"level_min": 43, "level_max": 50, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "blasted lands": {"level_min": 45, "level_max": 55, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "azshara": {"level_min": 45, "level_max": 55, "faction": "Contested", "continent": "Kalimdor"},
        "un'goro crater": {"level_min": 48, "level_max": 55, "faction": "Contested", "continent": "Kalimdor"},
        "felwood": {"level_min": 48, "level_max": 55, "faction": "Contested", "continent": "Kalimdor"},
        "burning steppes": {"level_min": 50, "level_max": 58, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "western plaguelands": {"level_min": 51, "level_max": 58, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "eastern plaguelands": {"level_min": 54, "level_max": 60, "faction": "Contested", "continent": "Eastern Kingdoms"},
        "winterspring": {"level_min": 55, "level_max": 60, "faction": "Contested", "continent": "Kalimdor"},
        "silithus": {"level_min": 55, "level_max": 60, "faction": "Contested", "continent": "Kalimdor"},
        "hellfire peninsula": {"level_min": 58, "level_max": 63, "faction": "Contested", "continent": "Outland"},
        "zangarmarsh": {"level_min": 60, "level_max": 64, "faction": "Contested", "continent": "Outland"},
        "terokkar forest": {"level_min": 62, "level_max": 65, "faction": "Contested", "continent": "Outland"},
        "nagrand": {"level_min": 64, "level_max": 67, "faction": "Contested", "continent": "Outland"},
        "blade's edge mountains": {"level_min": 65, "level_max": 68, "faction": "Contested", "continent": "Outland"},
        "netherstorm": {"level_min": 67, "level_max": 70, "faction": "Contested", "continent": "Outland"},
        "shadowmoon valley": {"level_min": 67, "level_max": 70, "faction": "Contested", "continent": "Outland"},
        "borean tundra": {"level_min": 68, "level_max": 72, "faction": "Contested", "continent": "Northrend"},
        "howling fjord": {"level_min": 68, "level_max": 72, "faction": "Contested", "continent": "Northrend"},
        "dragonblight": {"level_min": 71, "level_max": 75, "faction": "Contested", "continent": "Northrend"},
        "grizzly hills": {"level_min": 73, "level_max": 75, "faction": "Contested", "continent": "Northrend"},
        "zul'drak": {"level_min": 74, "level_max": 77, "faction": "Contested", "continent": "Northrend"},
        "sholazar basin": {"level_min": 76, "level_max": 78, "faction": "Contested", "continent": "Northrend"},
        "storm peaks": {"level_min": 77, "level_max": 80, "faction": "Contested", "continent": "Northrend"},
        "icecrown": {"level_min": 77, "level_max": 80, "faction": "Contested", "continent": "Northrend"},
    }

    def _get_zone_info(self, params: dict) -> str:
        """Get information about a zone."""
        zone = params.get("zone", "").lower()

        if not zone:
            return "Please specify a zone name."

        # Check our zone data
        zone_data = self.ZONE_INFO.get(zone)
        if not zone_data:
            # Try partial match
            for z_name, z_data in self.ZONE_INFO.items():
                if zone in z_name or z_name in zone:
                    zone_data = z_data
                    zone = z_name
                    break

        if not zone_data:
            return f"Zone '{zone}' not found. Try zones like: westfall, darkshore, barrens, hellfire peninsula, borean tundra."

        result = f"**{zone.title()}**\n\n"
        result += f"Level Range: {zone_data['level_min']}-{zone_data['level_max']}\n"
        result += f"Faction: {zone_data['faction']}\n"
        result += f"Continent: {zone_data['continent']}\n"

        if 'capital' in zone_data:
            result += f"Nearby Capital: {zone_data['capital']}\n"

        # Add adjacent zone suggestions based on level
        adjacent = []
        for z_name, z_data in self.ZONE_INFO.items():
            if z_name != zone and z_data['continent'] == zone_data['continent']:
                if abs(z_data['level_min'] - zone_data['level_max']) <= 5:
                    adjacent.append(f"{z_name.title()} ({z_data['level_min']}-{z_data['level_max']})")

        if adjacent:
            result += f"\nNearby zones: {', '.join(adjacent[:4])}"

        return result

    # Battlemaster data (NPCs that queue you for battlegrounds)
    BATTLEMASTERS = {
        "warsong gulch": {
            "alliance": [("Elfarran", 2302, "Silverwing Grove, Ashenvale"), ("Lylandris", 15105, "Ironforge"), ("Lylandris", 15105, "Stormwind")],
            "horde": [("Brakgul Deathbringer", 2804, "Mor'shan Base Camp, Barrens"), ("Brak'kar", 14982, "Orgrimmar"), ("Brak'kar", 14982, "Undercity")]
        },
        "arathi basin": {
            "alliance": [("Sir Maximus Adams", 19855, "Refugeepoint, Arathi Highlands"), ("Donal Osgood", 857, "Ironforge"), ("Lady Hoteshem", 15008, "Stormwind")],
            "horde": [("Aneera Thunade", 15106, "Hammerfall, Arathi Highlands"), ("Kym Wildmane", 14991, "Orgrimmar"), ("Sir Malory Wheeler", 15007, "Undercity")]
        },
        "alterac valley": {
            "alliance": [("Thelman Slatefist", 15102, "Alterac Mountains"), ("Karyn Threshwind", 15127, "Ironforge"), ("Lylandris", 15105, "Stormwind")],
            "horde": [("Grunnda Wolfheart", 15103, "Alterac Mountains"), ("Brak'kar", 14982, "Orgrimmar"), ("Kymn Wolfheart", 15126, "Undercity")]
        },
        "eye of the storm": {
            "alliance": [("Lara Karr", 20388, "Shattrath City")],
            "horde": [("Lara Karr", 20388, "Shattrath City")]
        },
        "strand of the ancients": {
            "alliance": [("Affi Silverstrand", 34955, "Dalaran")],
            "horde": [("Affi Silverstrand", 34955, "Dalaran")]
        },
        "isle of conquest": {
            "alliance": [("Battlemaster Gavin", 34957, "Dalaran")],
            "horde": [("Battlemaster Gavin", 34957, "Dalaran")]
        },
    }

    def _find_battlemaster(self, params: dict) -> str:
        """Find battlemasters for battlegrounds."""
        battleground = params.get("battleground", "").lower()
        faction = params.get("faction", "").lower()

        if not battleground:
            # List all battlegrounds
            result = "Available Battlegrounds:\n\n"
            result += "- **Warsong Gulch** (10-19, 20-29, etc.) - Capture the flag\n"
            result += "- **Arathi Basin** (20-29, 30-39, etc.) - Resource control\n"
            result += "- **Alterac Valley** (51-60, 61-70, 71-80) - Large-scale warfare\n"
            result += "- **Eye of the Storm** (61-70, 71-80) - Hybrid CTF/resource\n"
            result += "- **Strand of the Ancients** (71-80) - Attack/defend siege\n"
            result += "- **Isle of Conquest** (71-80) - Large-scale siege warfare\n"
            result += "\nSpecify a battleground name to find its battlemasters."
            return result

        # Find matching battleground
        bg_key = None
        for bg_name in self.BATTLEMASTERS.keys():
            if battleground in bg_name or bg_name.replace("'", "") in battleground:
                bg_key = bg_name
                break

        if not bg_key:
            return f"Battleground '{battleground}' not found. Try: warsong gulch, arathi basin, alterac valley, eye of the storm, strand of the ancients, isle of conquest."

        bg_data = self.BATTLEMASTERS[bg_key]

        result = f"**Battlemasters for {bg_key.title()}:**\n\n"

        if not faction or faction == "alliance":
            result += "**Alliance:**\n"
            for name, entry, location in bg_data.get("alliance", []):
                npc_link = f"[[npc:{entry}:{name}]]"
                result += f"- {npc_link} - {location}\n"

        if not faction or faction == "horde":
            result += "\n**Horde:**\n"
            for name, entry, location in bg_data.get("horde", []):
                npc_link = f"[[npc:{entry}:{name}]]"
                result += f"- {npc_link} - {location}\n"

        result += "\nYou can queue from any battlemaster for your faction."
        result += "\n\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored links!"
        return result

    # Weapon skill trainer data
    WEAPON_TRAINERS = {
        "alliance": {
            "stormwind": {
                "name": "Woo Ping",
                "entry": 11867,
                "location": "Trade District, Stormwind",
                "skills": ["crossbows", "daggers", "swords", "polearms", "staves", "two-handed swords"]
            },
            "ironforge": {
                "name": "Buliwyf Stonehand",
                "entry": 11868,
                "location": "Military Ward, Ironforge",
                "skills": ["crossbows", "daggers", "fist weapons", "guns", "maces", "two-handed maces"]
            },
            "darnassus": {
                "name": "Ilyenia Moonfire",
                "entry": 11866,
                "location": "Warrior's Terrace, Darnassus",
                "skills": ["bows", "daggers", "fist weapons", "staves", "thrown"]
            },
            "exodar": {
                "name": "Handiir",
                "entry": 20511,
                "location": "The Vault of Lights, Exodar",
                "skills": ["crossbows", "daggers", "maces", "swords", "two-handed maces", "two-handed swords"]
            }
        },
        "horde": {
            "orgrimmar": {
                "name": "Sayoc",
                "entry": 11869,
                "location": "Valley of Honor, Orgrimmar",
                "skills": ["bows", "daggers", "fist weapons", "staves", "thrown"]
            },
            "undercity": {
                "name": "Archibald",
                "entry": 11870,
                "location": "War Quarter, Undercity",
                "skills": ["crossbows", "daggers", "polearms", "swords", "two-handed swords"]
            },
            "thunder bluff": {
                "name": "Ansekhwa",
                "entry": 11865,
                "location": "Middle Rise, Thunder Bluff",
                "skills": ["guns", "maces", "staves", "two-handed maces"]
            },
            "silvermoon": {
                "name": "Ileda",
                "entry": 16499,
                "location": "Farstriders' Square, Silvermoon City",
                "skills": ["bows", "daggers", "polearms", "swords", "two-handed swords", "thrown"]
            }
        }
    }

    def _get_weapon_skill_trainer(self, params: dict) -> str:
        """Find weapon skill trainers."""
        weapon_type = params.get("weapon_type", "").lower()
        faction = params.get("faction", "").lower()

        if not faction:
            faction = None  # Show both

        result = "**Weapon Skill Trainers:**\n\n"

        # Collect trainers, optionally filtering by weapon type
        trainers_to_show = []

        for fac in ["alliance", "horde"]:
            if faction and faction != fac:
                continue

            for city, trainer in self.WEAPON_TRAINERS[fac].items():
                if weapon_type:
                    # Check if this trainer teaches the weapon
                    if not any(weapon_type in skill for skill in trainer["skills"]):
                        continue

                trainers_to_show.append({
                    "faction": fac,
                    "city": city,
                    "trainer": trainer
                })

        if not trainers_to_show:
            return f"No trainers found for '{weapon_type}'. Try: swords, maces, daggers, axes, polearms, staves, bows, guns, crossbows, thrown, fist weapons."

        current_faction = None
        for t in trainers_to_show:
            if t["faction"] != current_faction:
                current_faction = t["faction"]
                result += f"\n**{current_faction.title()}:**\n"

            trainer = t["trainer"]
            npc_link = f"[[npc:{trainer['entry']}:{trainer['name']}]]"
            result += f"\n{npc_link} ({t['city'].title()})\n"
            result += f"  Location: {trainer['location']}\n"
            result += f"  Teaches: {', '.join(trainer['skills'])}\n"

        result += "\n\nIMPORTANT: Include the [[npc:...]] markers exactly as shown - they become colored links!"
        return result

    def _get_class_quests(self, params: dict) -> str:
        """Find class-specific quest chains."""
        player_class = params.get("player_class", "").lower()
        level = params.get("level")

        if not player_class:
            return "Please specify a class (warrior, paladin, hunter, rogue, priest, shaman, mage, warlock, druid, death knight)."

        # Class ID mapping
        class_ids = {
            "warrior": 1, "paladin": 2, "hunter": 3, "rogue": 4, "priest": 5,
            "death knight": 6, "shaman": 7, "mage": 8, "warlock": 9, "druid": 11
        }

        class_id = class_ids.get(player_class)
        if not class_id:
            return f"Unknown class '{player_class}'. Valid classes: warrior, paladin, hunter, rogue, priest, shaman, mage, warlock, druid, death knight."

        # Convert to RequiredClasses bitmask (2^(classId-1))
        class_mask = 1 << (class_id - 1)

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        # Build level filter (show quests within reasonable range)
        level_filter = ""
        if level:
            min_lvl = max(1, int(level) - 10)
            max_lvl = int(level) + 5
            level_filter = f"AND qt.QuestLevel BETWEEN {min_lvl} AND {max_lvl}"

        # Find class-specific quests (AllowableClasses is in quest_template_addon)
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

        # Add notable class quest info (WotLK 3.3.5 accurate)
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

        # Find the quest by name
        cursor.execute("""
            SELECT qt.ID, qt.LogTitle, qt.QuestLevel, qt.MinLevel, qt.RewardNextQuest,
                   COALESCE(qta.PrevQuestID, 0) AS PrevQuestID
            FROM quest_template qt
            LEFT JOIN quest_template_addon qta ON qt.ID = qta.ID
            WHERE qt.LogTitle LIKE %s
            LIMIT 1
        """, (f"%{quest_name}%",))

        quest = cursor.fetchone()

        if not quest:
            cursor.close()
            conn.close()
            return f"Quest '{quest_name}' not found."

        # Step 1: Traverse backward to find the chain start
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

            # Prevent infinite loops
            if prev_quest['PrevQuestID'] in visited:
                break

            chain_start_id = prev_quest['PrevQuestID']
            visited.add(chain_start_id)

            # Safety limit
            if len(visited) > 30:
                break

        # Step 2: Traverse forward from chain start to build full chain
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

            # Safety limit
            if len(chain) > 30:
                break

        cursor.close()
        conn.close()

        if not chain:
            return f"Could not build quest chain for '{quest_name}'."

        # Find the position of the searched quest in the chain
        search_position = -1
        for i, q in enumerate(chain):
            if q['ID'] == quest['ID']:
                search_position = i
                break

        result = f"**Quest Chain** ({len(chain)} quests):\n\n"

        for i, q in enumerate(chain):
            lvl = q['QuestLevel'] if q['QuestLevel'] > 0 else q['MinLevel']
            quest_link = f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]"

            # Mark the searched quest
            marker = " ← (this quest)" if i == search_position else ""

            # Show quest giver if available
            giver = f" from {q['QuestGiver']}" if q['QuestGiver'] else ""

            result += f"{i+1}. {quest_link} (Level {lvl}){giver}{marker}\n"

        if len(chain) == 1:
            result += "\nThis quest is not part of a chain (standalone quest)."
        else:
            result += f"\nChain has {len(chain)} quests total."

        result += "\n\nIMPORTANT: Include the [[quest:...]] markers exactly as shown - they become clickable links!"
        return result

    # Faction ID to name mapping (from client DBC files)
    FACTION_NAMES = {
        # Alliance cities
        47: ("Ironforge", "alliance"),
        54: ("Gnomeregan", "alliance"),
        69: ("Darnassus", "alliance"),
        72: ("Stormwind", "alliance"),
        930: ("Exodar", "alliance"),
        # Horde cities
        68: ("Undercity", "horde"),
        76: ("Orgrimmar", "horde"),
        81: ("Thunder Bluff", "horde"),
        530: ("Darkspear Trolls", "horde"),
        911: ("Silvermoon City", "horde"),
        # Classic factions
        21: ("Booty Bay", "neutral"),
        87: ("Bloodsail Buccaneers", "neutral"),
        270: ("Zandalar Tribe", "neutral"),
        529: ("Argent Dawn", "neutral"),
        576: ("Timbermaw Hold", "neutral"),
        577: ("Everlook", "neutral"),
        589: ("Wintersaber Trainers", "alliance"),
        609: ("Cenarion Circle", "neutral"),
        729: ("Frostwolf Clan", "horde"),
        730: ("Stormpike Guard", "alliance"),
        749: ("Hydraxian Waterlords", "neutral"),
        889: ("Warsong Outriders", "horde"),
        890: ("Silverwing Sentinels", "alliance"),
        909: ("Darkmoon Faire", "neutral"),
        910: ("Brood of Nozdormu", "neutral"),
        # TBC factions
        932: ("The Aldor", "neutral"),
        933: ("The Consortium", "neutral"),
        934: ("The Scryers", "neutral"),
        935: ("The Sha'tar", "neutral"),
        941: ("The Mag'har", "horde"),
        942: ("Cenarion Expedition", "neutral"),
        946: ("Honor Hold", "alliance"),
        947: ("Thrallmar", "horde"),
        967: ("The Violet Eye", "neutral"),
        970: ("Sporeggar", "neutral"),
        978: ("Kurenai", "alliance"),
        989: ("Keepers of Time", "neutral"),
        990: ("The Scale of the Sands", "neutral"),
        1011: ("Lower City", "neutral"),
        1012: ("Ashtongue Deathsworn", "neutral"),
        1015: ("Netherwing", "neutral"),
        1031: ("Sha'tari Skyguard", "neutral"),
        1038: ("Ogri'la", "neutral"),
        1077: ("Shattered Sun Offensive", "neutral"),
        # WotLK factions
        1037: ("Alliance Vanguard", "alliance"),
        1050: ("Valiance Expedition", "alliance"),
        1052: ("Horde Expedition", "horde"),
        1064: ("The Taunka", "horde"),
        1067: ("The Hand of Vengeance", "horde"),
        1068: ("Explorers' League", "alliance"),
        1073: ("The Kalu'ak", "neutral"),
        1085: ("Warsong Offensive", "horde"),
        1090: ("Kirin Tor", "neutral"),
        1091: ("The Wyrmrest Accord", "neutral"),
        1094: ("The Silver Covenant", "alliance"),
        1098: ("Knights of the Ebon Blade", "neutral"),
        1104: ("Frenzyheart Tribe", "neutral"),
        1105: ("The Oracles", "neutral"),
        1106: ("Argent Crusade", "neutral"),
        1119: ("The Sons of Hodir", "neutral"),
        1124: ("The Sunreavers", "horde"),
        1126: ("The Frostborn", "alliance"),
        1156: ("The Ashen Verdict", "neutral"),
    }

    # Standing rank names and values
    STANDING_RANKS = {
        0: "Hated",
        1: "Hostile",
        2: "Unfriendly",
        3: "Neutral",
        4: "Friendly",
        5: "Honored",
        6: "Revered",
        7: "Exalted"
    }

    def _get_reputation_info(self, params: dict) -> str:
        """Get reputation information for a faction."""
        faction_name = params.get("faction_name", "").lower()

        if not faction_name:
            return "Please specify a faction name (e.g., 'Timbermaw Hold', 'Argent Dawn', 'Cenarion Expedition')."

        # Find faction by name
        faction_id = None
        actual_name = None
        faction_type = None

        for fid, (fname, ftype) in self.FACTION_NAMES.items():
            if faction_name in fname.lower() or fname.lower() in faction_name:
                faction_id = fid
                actual_name = fname
                faction_type = ftype
                break

        if not faction_id:
            # List some common factions
            return f"Faction '{faction_name}' not found. Try: Argent Dawn, Timbermaw Hold, Cenarion Circle, The Scryers, The Aldor, Kirin Tor, Sons of Hodir, Knights of the Ebon Blade."

        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)

        result = f"**{actual_name}** ({faction_type.title()} faction)\n\n"

        # 1. Find creatures that give reputation when killed
        cursor.execute("""
            SELECT ct.entry, ct.name, ct.minlevel, ct.maxlevel,
                   cor.RewOnKillRepValue1 AS rep_value,
                   cor.MaxStanding1 AS max_standing
            FROM creature_onkill_reputation cor
            JOIN creature_template ct ON cor.creature_id = ct.entry
            WHERE cor.RewOnKillRepFaction1 = %s AND cor.RewOnKillRepValue1 > 0
            ORDER BY cor.RewOnKillRepValue1 DESC
            LIMIT 10
        """, (faction_id,))

        kill_mobs = cursor.fetchall()

        # 2. Find quests that give reputation (prioritize repeatables)
        cursor.execute("""
            SELECT qt.ID, qt.LogTitle, qt.QuestLevel, qt.MinLevel,
                   COALESCE(qt.RewardFactionOverride1, qt.RewardFactionValue1) AS rep_value,
                   CASE WHEN qta.SpecialFlags & 1 = 1 THEN 1 ELSE 0 END AS is_repeatable
            FROM quest_template qt
            LEFT JOIN quest_template_addon qta ON qt.ID = qta.ID
            WHERE qt.RewardFactionID1 = %s
              AND qt.LogTitle IS NOT NULL AND qt.LogTitle != ''
            ORDER BY is_repeatable DESC, rep_value DESC
            LIMIT 15
        """, (faction_id,))

        quests = cursor.fetchall()

        # 3. Find faction rewards (items requiring this faction's reputation)
        cursor.execute("""
            SELECT it.entry, it.name, it.Quality,
                   it.RequiredReputationRank,
                   nv.entry AS vendor_id,
                   ct.name AS vendor_name
            FROM item_template it
            LEFT JOIN npc_vendor nv ON it.entry = nv.item
            LEFT JOIN creature_template ct ON nv.entry = ct.entry
            WHERE it.RequiredReputationFaction = %s
            ORDER BY it.RequiredReputationRank, it.Quality DESC
            LIMIT 20
        """, (faction_id,))

        rewards = cursor.fetchall()

        cursor.close()
        conn.close()

        # Build result: Ways to gain rep
        result += "**Ways to Gain Reputation:**\n"

        if kill_mobs:
            result += "\n*Kill mobs:*\n"
            for mob in kill_mobs:
                lvl = f"{mob['minlevel']}-{mob['maxlevel']}" if mob['minlevel'] != mob['maxlevel'] else str(mob['minlevel'])
                max_standing = self.STANDING_RANKS.get(mob['max_standing'], "Exalted")
                npc_link = f"[[npc:{mob['entry']}:{mob['name']}]]"
                result += f"- {npc_link} (Level {lvl}) - {mob['rep_value']} rep (caps at {max_standing})\n"

        if quests:
            repeatable = [q for q in quests if q['is_repeatable']]
            one_time = [q for q in quests if not q['is_repeatable']]

            if repeatable:
                result += "\n*Repeatable quests:*\n"
                for q in repeatable[:5]:
                    quest_link = f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]"
                    rep = q['rep_value'] if q['rep_value'] else "varies"
                    result += f"- {quest_link} - {rep} rep\n"

            if one_time:
                result += "\n*One-time quests:*\n"
                for q in one_time[:5]:
                    quest_link = f"[[quest:{q['ID']}:{q['LogTitle']}:{q['QuestLevel']}]]"
                    rep = q['rep_value'] if q['rep_value'] else "varies"
                    result += f"- {quest_link} - {rep} rep\n"

        if not kill_mobs and not quests:
            result += "- No direct reputation sources found in database.\n"

        # Build result: Faction rewards
        if rewards:
            result += "\n**Faction Rewards:**\n"

            # Group by standing
            by_standing = {}
            for r in rewards:
                rank = r['RequiredReputationRank']
                if rank not in by_standing:
                    by_standing[rank] = []
                by_standing[rank].append(r)

            for rank in sorted(by_standing.keys()):
                rank_name = self.STANDING_RANKS.get(rank, f"Rank {rank}")
                result += f"\n*{rank_name}:*\n"
                for item in by_standing[rank][:4]:  # Limit per rank
                    item_link = f"[[item:{item['entry']}:{item['name']}:{item['Quality']}]]"
                    vendor = f" (from {item['vendor_name']})" if item['vendor_name'] else ""
                    result += f"- {item_link}{vendor}\n"

        result += "\n\nIMPORTANT: Include the [[item:...]], [[quest:...]], and [[npc:...]] markers exactly as shown!"
        return result
