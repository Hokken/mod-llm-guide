"""Revalidate historical link identities, never historical gameplay claims."""

import logging

from spell_names import SPELL_NAMES

logger = logging.getLogger(__name__)

UNRESOLVED = ('I could not verify an entity reference in this answer. '
              'Please specify the NPC, item, quest or spell you mean.')


def lookup_identity(executor, kind, entity_id):
    """Exact IDs only. Spell names use the same catalog as spell tools."""
    if kind == 'spell':
        name = SPELL_NAMES.get(entity_id)
        return f'[[spell:{entity_id}:{name}]]' if name else None
    queries = {
        'npc': 'SELECT name FROM creature_template WHERE entry = %s',
        'item': 'SELECT name, Quality FROM item_template WHERE entry = %s',
        'quest': 'SELECT LogTitle AS name, QuestLevel FROM quest_template '
                 'WHERE ID = %s',
    }
    connection = executor.get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(queries[kind], (entity_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()
    finally:
        connection.close()
    if not row:
        return None
    suffix = (f":{row['Quality']}" if kind == 'item' else
              f":{row['QuestLevel']}" if kind == 'quest' else '')
    return f"[[{kind}:{entity_id}:{row['name']}{suffix}]]"


def reverify_followup(response, recent, executor, remaining_timeout, limit):
    """Return answer and whether a deterministic clarification replaced it."""
    ledger = executor.evidence
    response = ledger.canonicalize_links(response)
    pending = {}
    for match in ledger.MARKER.finditer(response):
        if match[0] in ledger.markers:
            continue
        identity = ledger.identity(match[0])
        # Any unresolved identity must pass the same exact check, regardless
        # of whether history mentioned it as a link, plain text, or not at all.
        pending[identity] = None
    if len(pending) > limit:
        logger.warning('Entity link verification exceeded limit')
        return UNRESOLVED, True
    verified = set()
    for identity in pending:
        remaining_timeout()
        try:
            marker = lookup_identity(executor, identity[0], identity[1])
        except Exception as error:
            logger.warning('Historical identity lookup failed: %s',
                           type(error).__name__)
            return UNRESOLVED, True
        remaining_timeout()
        if not marker or ledger.identity(marker) != identity:
            return UNRESOLVED, True
        verified.add(marker)
    # Identity-only verification must NOT count as factual answer evidence.
    ledger.markers.update(verified)
    return ledger.canonicalize_links(response), False
