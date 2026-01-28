"""
Zone coordinate mappings from WorldMapArea.dbc (WotLK 3.3.5).

Format: zone_name -> (map_id, loc_left, loc_right, loc_top, loc_bottom)

The loc* values define the zone's world coordinate boundaries:
- loc_left/loc_right: Y-axis boundaries (world_y)
- loc_top/loc_bottom: X-axis boundaries (world_x)

Conversion formula:
    map_x = (loc_left - world_y) / (loc_left - loc_right) * 100
    map_y = (loc_top - world_x) / (loc_top - loc_bottom) * 100
"""

# Extracted from WorldMapArea.dbc (WotLK 3.3.5a)
# Format: (map_id, loc_left, loc_right, loc_top, loc_bottom)
ZONE_COORDINATES = {
    # ======================================================================
    # Eastern Kingdoms (map 0)
    # ======================================================================
    "alterac mountains": (0, 783.3333, -2016.6666, 1500.0000, -366.6667),
    "arathi highlands": (0, -866.6666, -4466.6665, -133.3333, -2533.3333),
    "badlands": (0, -2079.1665, -4566.6665, -5889.5830, -7547.9165),
    "blasted lands": (0, -1241.6666, -4591.6665, -10566.6660, -12800.0000),
    "burning steppes": (0, -266.6667, -3195.8333, -7031.2495, -8983.3330),
    "deadwind pass": (0, -833.3333, -3333.3333, -9866.6660, -11533.3330),
    "dun morogh": (0, 1802.0833, -3122.9165, -3877.0833, -7160.4165),
    "duskwood": (0, 833.3333, -1866.6666, -9716.6660, -11516.6660),
    "eastern plaguelands": (0, -2287.5000, -6318.7500, 3704.1665, 1016.6666),
    "elwynn forest": (0, 1535.4166, -1935.4166, -7939.5830, -10254.1660),
    "hillsbrad foothills": (0, 1066.6666, -2133.3333, 400.0000, -1733.3333),
    "ironforge": (0, -713.5914, -1504.2164, -4569.2412, -5096.8457),
    "loch modan": (0, -1993.7499, -4752.0830, -4487.5000, -6327.0830),
    "redridge mountains": (0, -1570.8333, -3741.6665, -8575.0000, -10022.9160),
    "searing gorge": (0, -322.9167, -2554.1665, -6100.0000, -7587.4995),
    "silverpine forest": (0, 3449.9998, -750.0000, 1666.6666, -1133.3333),
    "stormwind city": (0, 1722.9166, -14.5833, -7995.8330, -9154.1660),
    "stranglethorn vale": (0, 2220.8333, -4160.4165, -11168.7500, -15422.9160),
    "swamp of sorrows": (0, -2222.9165, -4516.6665, -9620.8330, -11150.0000),
    "the hinterlands": (0, -1575.0000, -5425.0000, 1466.6666, -1100.0000),
    "tirisfal glades": (0, 3033.3333, -1485.4166, 3837.4998, 824.9999),
    "undercity": (0, 873.1926, -86.1824, 1877.9453, 1237.8412),
    "western plaguelands": (0, 416.6667, -3883.3333, 3366.6665, 500.0000),
    "westfall": (0, 3016.6665, -483.3333, -9400.0000, -11733.3330),
    "wetlands": (0, -389.5833, -4525.0000, -2147.9165, -4904.1665),

    # ======================================================================
    # Kalimdor (map 1)
    # ======================================================================
    "ashenvale": (1, 1699.9999, -4066.6665, 4672.9165, 829.1666),
    "azshara": (1, -3277.0833, -8347.9160, 5341.6665, 1960.4166),
    "darkshore": (1, 2941.6665, -3608.3333, 8333.3330, 3966.6665),
    "darnassus": (1, 2938.3628, 1880.0295, 10238.3164, 9532.5869),
    "desolace": (1, 4233.3330, -262.5000, 452.0833, -2545.8333),
    "durotar": (1, -1962.4999, -7249.9995, 1808.3333, -1716.6666),
    "dustwallow marsh": (1, -974.9999, -6225.0000, -2033.3333, -5533.3330),
    "felwood": (1, 1641.6666, -4108.3330, 7133.3330, 3299.9998),
    "feralas": (1, 5441.6665, -1508.3333, -2366.6665, -6999.9995),
    "moonglade": (1, -1381.2500, -3689.5833, 8491.6660, 6952.0830),
    "mulgore": (1, 2047.9166, -3089.5833, -272.9167, -3697.9165),
    "orgrimmar": (1, -3680.6011, -5083.2056, 2273.8772, 1338.4606),
    "silithus": (1, 2537.5000, -945.8340, -5958.3340, -8281.2500),
    "stonetalon mountains": (1, 3245.8333, -1637.4999, 2916.6665, -339.5833),
    "tanaris": (1, -218.7500, -7118.7495, -5875.0000, -10475.0000),
    "teldrassil": (1, 3814.5833, -1277.0833, 11831.2500, 8437.5000),
    "the barrens": (1, 2622.9165, -7510.4165, 1612.4999, -5143.7500),
    "thousand needles": (1, -433.3333, -4833.3330, -3966.6665, -6899.9995),
    "thunder bluff": (1, 516.6666, -527.0833, -849.9999, -1545.8333),
    "un'goro crater": (1, 533.3333, -3166.6665, -5966.6665, -8433.3330),
    "winterspring": (1, -316.6667, -7416.6665, 8533.3330, 3799.9998),

    # ======================================================================
    # Outland (map 530)
    # ======================================================================
    "azuremyst isle": (530, -10500.0000, -14570.8330, -2793.7500, -5508.3330),
    "blade's edge mountains": (530, 8845.8330, 3420.8333, 4408.3330, 791.6666),
    "bloodmyst isle": (530, -10075.0000, -13337.4990, -758.3333, -2933.3333),
    "eversong woods": (530, -4487.5000, -9412.5000, 11041.6660, 7758.3330),
    "ghostlands": (530, -5283.3330, -8583.3330, 8266.6660, 6066.6665),
    "hellfire peninsula": (530, 5539.5830, 375.0000, 1481.2500, -1962.4999),
    "nagrand": (530, 10295.8330, 4770.8330, 41.6667, -3641.6665),
    "netherstorm": (530, 5483.3330, -91.6667, 5456.2500, 1739.5833),
    "shadowmoon valley": (530, 4225.0000, -1275.0000, -1947.9166, -5614.5830),
    "shattrath city": (530, 6135.2588, 4829.0088, -1473.9545, -2344.7878),
    "silvermoon city": (530, -6400.7500, -7612.2085, 10153.7090, 9346.9385),
    "terokkar forest": (530, 7083.3330, 1683.3333, -999.9999, -4600.0000),
    "the exodar": (530, -11066.3672, -12123.1377, -3609.6833, -4314.3711),
    "zangarmarsh": (530, 9475.0000, 4447.9165, 1935.4166, -1416.6666),

    # ======================================================================
    # Northrend (map 571)
    # ======================================================================
    "borean tundra": (571, 8570.8330, 2806.2500, 4897.9165, 1054.1666),
    "crystalsong forest": (571, 1443.7500, -1279.1666, 6502.0830, 4687.5000),
    "dalaran": (571, 0.0, 0.0, 0.0, 0.0),  # City instance, coords N/A
    "dragonblight": (571, 3627.0833, -1981.2499, 5575.0000, 1835.4166),
    "grizzly hills": (571, -1110.4166, -6360.4165, 5516.6665, 2016.6666),
    "howling fjord": (571, -1397.9166, -7443.7495, 3116.6665, -914.5833),
    "hrothgar's landing": (571, 2797.9165, -879.1666, 10781.2500, 8329.1660),
    "icecrown": (571, 5443.7500, -827.0833, 9427.0830, 5245.8330),
    "sholazar basin": (571, 6929.1665, 2572.9165, 7287.4995, 4383.3330),
    "the storm peaks": (571, 1841.6666, -5270.8330, 10197.9160, 5456.2500),
    "wintergrasp": (571, 4329.1665, 1354.1666, 5716.6665, 3733.3333),
    "zul'drak": (571, -600.0000, -5593.7500, 7668.7495, 4339.5830),
}

# Aliases for common zone names, abbreviations, and subzone -> parent mappings
ZONE_ALIASES = {
    # Zone abbreviations
    "alterac": "alterac mountains",
    "arathi": "arathi highlands",
    "azuremyst": "azuremyst isle",
    "barrens": "the barrens",
    "blades edge": "blade's edge mountains",
    "bloodmyst": "bloodmyst isle",
    "borean": "borean tundra",
    "crystalsong": "crystalsong forest",
    "dal": "dalaran",
    "darn": "darnassus",
    "deadwind": "deadwind pass",
    "dustwallow": "dustwallow marsh",
    "elwynn": "elwynn forest",
    "epl": "eastern plaguelands",
    "eversong": "eversong woods",
    "exodar": "the exodar",
    "grizzly": "grizzly hills",
    "hfp": "hellfire peninsula",
    "hellfire": "hellfire peninsula",
    "hillsbrad": "hillsbrad foothills",
    "hinterlands": "the hinterlands",
    "howling": "howling fjord",
    "if": "ironforge",
    "org": "orgrimmar",
    "redridge": "redridge mountains",
    "shadowmoon": "shadowmoon valley",
    "shatt": "shattrath city",
    "sholazar": "sholazar basin",
    "silvermoon": "silvermoon city",
    "silverpine": "silverpine forest",
    "smv": "shadowmoon valley",
    "stonetalon": "stonetalon mountains",
    "storm peaks": "the storm peaks",
    "stormwind": "stormwind city",
    "stranglethorn": "stranglethorn vale",
    "stv": "stranglethorn vale",
    "sw": "stormwind city",
    "tb": "thunder bluff",
    "terokkar": "terokkar forest",
    "tirisfal": "tirisfal glades",
    "uc": "undercity",
    "un'goro": "un'goro crater",
    "ungoro": "un'goro crater",
    "wpl": "western plaguelands",
    "zangar": "zangarmarsh",
    "zuldrak": "zul'drak",

    # Town/Subzone -> Parent Zone mappings
    # Eastern Kingdoms
    "goldshire": "elwynn forest",
    "northshire": "elwynn forest",
    "sentinel hill": "westfall",
    "moonbrook": "westfall",
    "lakeshire": "redridge mountains",
    "darkshire": "duskwood",
    "booty bay": "stranglethorn vale",
    "grom'gol": "stranglethorn vale",
    "southshore": "hillsbrad foothills",
    "tarren mill": "hillsbrad foothills",
    "menethil harbor": "wetlands",
    "menethil": "wetlands",
    "thelsamar": "loch modan",
    "kharanos": "dun morogh",
    "coldridge valley": "dun morogh",
    "brill": "tirisfal glades",
    "deathknell": "tirisfal glades",
    "sepulcher": "silverpine forest",
    "the sepulcher": "silverpine forest",
    "light's hope": "eastern plaguelands",
    "light's hope chapel": "eastern plaguelands",
    "chillwind camp": "western plaguelands",
    "refuge pointe": "arathi highlands",
    "hammerfall": "arathi highlands",
    "aerie peak": "the hinterlands",
    "revantusk village": "the hinterlands",
    "nethergarde keep": "blasted lands",
    "stonard": "swamp of sorrows",
    "morgan's vigil": "burning steppes",
    "flame crest": "burning steppes",
    "thorium point": "searing gorge",
    "kargath": "badlands",

    # Kalimdor
    "auberdine": "darkshore",
    "shadowglen": "teldrassil",
    "dolanaar": "teldrassil",
    "crossroads": "the barrens",
    "the crossroads": "the barrens",
    "camp taurajo": "the barrens",
    "ratchet": "the barrens",
    "razor hill": "durotar",
    "sen'jin village": "durotar",
    "valley of trials": "durotar",
    "bloodhoof village": "mulgore",
    "bloodhoof": "mulgore",
    "red cloud mesa": "mulgore",
    "camp narache": "mulgore",
    "astranaar": "ashenvale",
    "splintertree post": "ashenvale",
    "theramore": "dustwallow marsh",
    "brackenwall village": "dustwallow marsh",
    "gadgetzan": "tanaris",
    "cenarion hold": "silithus",
    "everlook": "winterspring",
    "nijel's point": "desolace",
    "shadowprey village": "desolace",
    "feathermoon stronghold": "feralas",
    "feathermoon": "feralas",
    "camp mojache": "feralas",
    "freewind post": "thousand needles",
    "marshal's refuge": "un'goro crater",
    "sun rock retreat": "stonetalon mountains",
    "stonetalon peak": "stonetalon mountains",
    "nighthaven": "moonglade",
    "talrendis point": "azshara",
    "valormok": "azshara",
    "talonbranch glade": "felwood",
    "emerald sanctuary": "felwood",

    # Outland
    "honor hold": "hellfire peninsula",
    "thrallmar": "hellfire peninsula",
    "telredor": "zangarmarsh",
    "cenarion refuge": "zangarmarsh",
    "zabra'jin": "zangarmarsh",
    "allerian stronghold": "terokkar forest",
    "stonebreaker hold": "terokkar forest",
    "sylvanaar": "blade's edge mountains",
    "thunderlord stronghold": "blade's edge mountains",
    "toshley's station": "blade's edge mountains",
    "area 52": "netherstorm",
    "the stormspire": "netherstorm",
    "telaar": "nagrand",
    "garadar": "nagrand",
    "wildhammer stronghold": "shadowmoon valley",
    "shadowmoon village": "shadowmoon valley",
    "altar of sha'tar": "shadowmoon valley",
    "sanctum of the stars": "shadowmoon valley",
    "sunstrider isle": "eversong woods",
    "falconwing square": "eversong woods",
    "fairbreeze village": "eversong woods",
    "tranquillien": "ghostlands",
    "ammen vale": "azuremyst isle",
    "azure watch": "azuremyst isle",
    "blood watch": "bloodmyst isle",

    # Northrend
    "valiance keep": "borean tundra",
    "warsong hold": "borean tundra",
    "fizzcrank airstrip": "borean tundra",
    "taunka'le village": "borean tundra",
    "valgarde": "howling fjord",
    "vengeance landing": "howling fjord",
    "fort wildervar": "howling fjord",
    "camp winterhoof": "howling fjord",
    "wintergarde keep": "dragonblight",
    "agmar's hammer": "dragonblight",
    "stars' rest": "dragonblight",
    "moa'ki harbor": "dragonblight",
    "wyrmrest temple": "dragonblight",
    "amberpine lodge": "grizzly hills",
    "conquest hold": "grizzly hills",
    "westfall brigade": "grizzly hills",
    "camp oneqwah": "grizzly hills",
    "light's breach": "zul'drak",
    "the argent stand": "zul'drak",
    "zim'torga": "zul'drak",
    "k3": "the storm peaks",
    "frosthold": "the storm peaks",
    "dun niffelem": "the storm peaks",
    "brunnhildar village": "the storm peaks",
    "nesingwary base camp": "sholazar basin",
    "river's heart": "sholazar basin",
    "argent tournament": "icecrown",
    "the argent tournament grounds": "icecrown",
    "argent vanguard": "icecrown",
    "shadow vault": "icecrown",
}


# Zone IDs from AreaTable.dbc (for queries using creature.zoneId, gameobject.zoneId)
ZONE_IDS = {
    # Eastern Kingdoms
    "alterac mountains": 36,
    "arathi highlands": 45,
    "badlands": 3,
    "blasted lands": 4,
    "burning steppes": 46,
    "deadwind pass": 41,
    "dun morogh": 1,
    "duskwood": 10,
    "eastern plaguelands": 139,
    "elwynn forest": 12,
    "eversong woods": 3430,
    "ghostlands": 3433,
    "hillsbrad foothills": 267,
    "ironforge": 1537,
    "isle of quel'danas": 4080,
    "loch modan": 38,
    "redridge mountains": 44,
    "searing gorge": 51,
    "silverpine forest": 130,
    "stormwind city": 1519,
    "stranglethorn vale": 33,
    "swamp of sorrows": 8,
    "the hinterlands": 47,
    "tirisfal glades": 85,
    "undercity": 1497,
    "western plaguelands": 28,
    "westfall": 40,
    "wetlands": 11,
    "silvermoon city": 3487,
    # Kalimdor
    "ashenvale": 331,
    "azshara": 16,
    "azuremyst isle": 3524,
    "bloodmyst isle": 3525,
    "darkshore": 148,
    "darnassus": 1657,
    "desolace": 405,
    "durotar": 14,
    "dustwallow marsh": 15,
    "felwood": 361,
    "feralas": 357,
    "moonglade": 493,
    "mulgore": 215,
    "orgrimmar": 1637,
    "silithus": 1377,
    "stonetalon mountains": 406,
    "tanaris": 440,
    "teldrassil": 141,
    "the barrens": 17,
    "the exodar": 3557,
    "thousand needles": 400,
    "thunder bluff": 1638,
    "un'goro crater": 490,
    "winterspring": 618,
    # Outland
    "blade's edge mountains": 3522,
    "hellfire peninsula": 3483,
    "nagrand": 3518,
    "netherstorm": 3523,
    "shadowmoon valley": 3520,
    "shattrath city": 3703,
    "terokkar forest": 3519,
    "zangarmarsh": 3521,
    # Northrend
    "borean tundra": 3537,
    "crystalsong forest": 2817,
    "dalaran": 4395,
    "dragonblight": 65,
    "grizzly hills": 394,
    "howling fjord": 495,
    "icecrown": 210,
    "sholazar basin": 3711,
    "the storm peaks": 67,
    "wintergrasp": 4197,
    "zul'drak": 66,
}


def get_zone_id(zone_name: str) -> int:
    """Get zone ID for a zone name. Returns None if not found."""
    zone_lower = zone_name.lower().strip()

    # Check aliases first
    if zone_lower in ZONE_ALIASES:
        zone_lower = ZONE_ALIASES[zone_lower]

    return ZONE_IDS.get(zone_lower)


def get_zone_coordinates(zone_name: str) -> tuple:
    """
    Get coordinates for a zone by name.
    Returns (map_id, loc_left, loc_right, loc_top, loc_bottom) or None if not found.
    """
    zone_lower = zone_name.lower().strip()

    # Check aliases first
    if zone_lower in ZONE_ALIASES:
        zone_lower = ZONE_ALIASES[zone_lower]

    return ZONE_COORDINATES.get(zone_lower)


def find_zone_in_text(text: str) -> tuple:
    """
    Find a zone name mentioned in text.
    Returns (zone_name, coordinates) or (None, None).
    """
    text_lower = text.lower()

    # Check for full zone names first (longer matches take priority)
    for zone_name in sorted(ZONE_COORDINATES.keys(), key=len, reverse=True):
        if zone_name in text_lower:
            return (zone_name, ZONE_COORDINATES[zone_name])

    # Check aliases
    for alias, zone_name in ZONE_ALIASES.items():
        if f" {alias} " in f" {text_lower} ":
            return (zone_name, ZONE_COORDINATES.get(zone_name))

    return (None, None)


def world_to_map_coords(zone_name: str, world_x: float, world_y: float) -> tuple:
    """
    Convert world coordinates (from database) to map percentage coordinates.
    Uses WorldMapArea.dbc boundary data for accurate conversion.

    Args:
        zone_name: Zone name (will be normalized)
        world_x: position_x from database (north-south axis)
        world_y: position_y from database (east-west axis)

    Returns:
        (map_x, map_y) as percentages (0-100) or None if zone not found.
        map_x = left-right on map (0=left, 100=right)
        map_y = top-bottom on map (0=top, 100=bottom)
    """
    zone_lower = zone_name.lower().strip() if zone_name else None

    # Check aliases
    if zone_lower and zone_lower in ZONE_ALIASES:
        zone_lower = ZONE_ALIASES[zone_lower]

    if not zone_lower or zone_lower not in ZONE_COORDINATES:
        return None

    map_id, loc_left, loc_right, loc_top, loc_bottom = ZONE_COORDINATES[zone_lower]

    # Skip zones with invalid/zero coordinates (like Dalaran instance)
    if loc_left == 0 and loc_right == 0:
        return None

    # Conversion formula based on WorldMapArea.dbc structure:
    # - loc_left/loc_right define Y-axis (world_y) boundaries
    # - loc_top/loc_bottom define X-axis (world_x) boundaries
    # Map origin is top-left (0,0), bottom-right is (100,100)
    map_x = (loc_left - world_y) / (loc_left - loc_right) * 100
    map_y = (loc_top - world_x) / (loc_top - loc_bottom) * 100

    # Clamp to 0-100 range (point might be slightly outside zone bounds)
    map_x = max(0, min(100, map_x))
    map_y = max(0, min(100, map_y))

    return (round(map_x, 1), round(map_y, 1))


def extract_player_zone(context: str) -> tuple:
    """
    Extract the player's current zone from context string.
    Looks for pattern like "in <Zone>." at the end of the location phrase.
    More precise than find_zone_in_text for char context.
    Returns (zone_name, coordinates) or (None, None).
    """
    import re

    # Look for "in <Zone>." or "in <Zone>," pattern (player location)
    match = re.search(r'\bin ([A-Z][a-zA-Z\' ]+?)[\.,]', context)
    if match:
        potential_zone = match.group(1).lower().strip()

        # Check direct match
        if potential_zone in ZONE_COORDINATES:
            return (potential_zone, ZONE_COORDINATES[potential_zone])

        # Check aliases
        if potential_zone in ZONE_ALIASES:
            zone_name = ZONE_ALIASES[potential_zone]
            return (zone_name, ZONE_COORDINATES.get(zone_name))

    # Fallback to general search
    return find_zone_in_text(context)
