"""Canonical service identities; never infer NPC capabilities from spelling."""

import re


# None means a flag-based lookup. Other services retain their existing filters.
SERVICE_PATTERNS = {
    'flight_master': None,
    'stable_master': '%Stable Master%', 'innkeeper': '%Innkeeper%',
    'banker': '%Banker%', 'auctioneer': '%Auctioneer%', 'barber': '%Barber%',
    'repair': '%Repair%', 'armorer': '%Armor%', 'guild_master': '%Guild Master%',
}

SERVICE_ALIASES = {
    'flight_master': (
        'flight master', 'flight', 'flight point', 'taxi', 'taxi master',
        'gryphon master', 'gryphon', 'griphon', 'griphon master',
        'griffon', 'griffon master', 'griffin', 'griffin master',
        'wind rider', 'wind rider master', 'hippogryph', 'hippogryph master',
        'dragonhawk', 'dragonhawk master', 'bat handler', 'bat master',
    ),
    'stable_master': ('stable master', 'stable'),
    'innkeeper': ('innkeeper', 'inn'),
    'banker': ('banker', 'bank'),
    'auctioneer': ('auctioneer', 'auction', 'auction house'),
    'barber': ('barber',), 'repair': ('repair',), 'armorer': ('armorer',),
    'guild_master': ('guild master',),
}


def normalize_service(value):
    return re.sub(r'[\W_]+', ' ', value.casefold()).strip()


def resolve_service(value):
    """Exact aliases only; semantic interpretation belongs to the router."""
    if not isinstance(value, str):
        return None
    value = normalize_service(value)
    for canonical, aliases in SERVICE_ALIASES.items():
        if value in {normalize_service(canonical), *aliases}:
            return canonical
    return None
