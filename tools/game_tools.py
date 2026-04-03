"""
Game data tools for Claude tool use.
Defines tools that Claude can call to query the WoW database.
"""

import logging
from zone_coordinates import get_zone_coordinates, get_zone_id, ZONE_COORDINATES

from guide_tool_shared import GuideToolSharedMixin
from guide_tool_npcs import GuideToolNpcMixin
from guide_tool_spells import GuideToolSpellMixin
from guide_tool_quests import GuideToolQuestMixin
from guide_tool_items import GuideToolItemMixin

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

class GameToolExecutor(
    GuideToolNpcMixin,
    GuideToolSpellMixin,
    GuideToolQuestMixin,
    GuideToolItemMixin,
    GuideToolSharedMixin,
):
    """Executes game data tools by querying the database."""

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
        self.default_player_level = None
        self.default_player_class = None
        self.default_faction = None
        self.active_quest_ids = []

    def set_player_zone(self, zone: str):
        """Set the player's current zone for use as default in tool calls."""
        self.default_zone = zone

    def set_player_position(self, x: float, y: float, map_id: int):
        """Set the player's current position for distance calculations."""
        self.player_x = x
        self.player_y = y
        self.player_map = map_id

    def set_player_defaults(
        self, level: int = None,
        player_class: str = None,
        faction: str = None
    ):
        """Set parsed player defaults for tool auto-injection."""
        self.default_player_level = level
        self.default_player_class = (
            player_class.lower()
            if player_class else None
        )
        self.default_faction = (
            faction.lower()
            if faction else None
        )

    def set_active_quest_ids(
        self, quest_ids: list[int] | None
    ):
        """Set current active quest IDs for availability filtering."""
        self.active_quest_ids = quest_ids or []

    _DEFAULT_NPC_ORDER = "ORDER BY ct.name"

    def _distance_order_params(
        self, fallback=None
    ):
        """Return (sql_cols, order_clause,
        select_params, order_params, distance_active)
        for distance-based sorting.

        When player position is available, adds computed
        columns for same-map priority and squared
        Euclidean distance, with the fallback as a
        secondary sort for cross-map and tie-breaking.
        Falls back to *fallback* (default: ORDER BY
        ct.name) when position is unknown.

        Returns a 5-tuple. Callers must place
        select_params before WHERE params, and
        order_params after WHERE params:
          cursor.execute(sql,
              (*select_params, *where_params,
               *order_params))
        """
        if fallback is None:
            fallback = self._DEFAULT_NPC_ORDER
        secondary = fallback.replace(
            "ORDER BY ", "", 1
        )
        if (self.player_x is not None
                and self.player_y is not None
                and self.player_map is not None):
            cols = (
                ", CASE WHEN c.map = %s THEN 0 "
                "ELSE 1 END AS same_map"
                ", (c.position_x - %s) "
                "* (c.position_x - %s) "
                "+ (c.position_y - %s) "
                "* (c.position_y - %s) "
                "AS dist_sq"
            )
            order = (
                "ORDER BY same_map ASC, "
                "CASE WHEN c.map = %s "
                "THEN dist_sq END ASC, "
                f"{secondary}"
            )
            select_params = (
                self.player_map,
                self.player_x,
                self.player_x,
                self.player_y,
                self.player_y,
            )
            order_params = (self.player_map,)
            return (cols, order, select_params,
                    order_params, True)
        return "", fallback, (), (), False

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

        # Auto-inject structured player defaults when the tool can use them.
        injected_fields = []
        if tool_name in {
                'get_spell_info', 'list_spells_by_level',
                'get_available_quests', 'find_item_upgrades',
                'get_class_quests'}:
            if ('player_class' not in tool_input and
                    self.default_player_class):
                tool_input = tool_input.copy()
                tool_input['player_class'] = (
                    self.default_player_class
                )
                injected_fields.append('player_class')
        if tool_name in {
                'list_spells_by_level', 'get_available_quests',
                'find_item_upgrades', 'get_class_quests'}:
            if ('level' not in tool_input and
                    tool_name in {
                        'list_spells_by_level',
                        'get_class_quests'} and
                    self.default_player_level is not None):
                tool_input = tool_input.copy()
                tool_input['level'] = (
                    self.default_player_level
                )
                injected_fields.append('level')
            if ('player_level' not in tool_input and
                    tool_name in {
                        'get_available_quests',
                        'find_item_upgrades'} and
                    self.default_player_level is not None):
                tool_input = tool_input.copy()
                tool_input['player_level'] = (
                    self.default_player_level
                )
                injected_fields.append('player_level')
        if tool_name in {
                'get_available_quests', 'find_battlemaster',
                'get_weapon_skill_trainer', 'get_flight_paths'}:
            if ('faction' not in tool_input and
                    self.default_faction):
                tool_input = tool_input.copy()
                tool_input['faction'] = (
                    self.default_faction
                )
                injected_fields.append('faction')
        if (tool_name == 'get_available_quests' and
                'active_quest_ids' not in tool_input and
                self.active_quest_ids):
            tool_input = tool_input.copy()
            tool_input['active_quest_ids'] = (
                self.active_quest_ids
            )
            injected_fields.append('active_quest_ids')
        if injected_fields:
            logger.info(
                f"Auto-injected player defaults into "
                f"{tool_name}: {sorted(set(injected_fields))}"
            )

        logger.debug(
            f"Executing tool: {tool_name} "
            f"with input: {tool_input}"
        )

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
