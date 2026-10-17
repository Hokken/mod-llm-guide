"""Remove known diagnostic boilerplate without truncating game links."""

import re

from guide_reliability import EvidenceLedger


def compact_equipment_answer(text):
    """Format ordinary recommendations; not for requested numeric analysis."""
    if '[[item:' not in text:
        return text
    prefix = '\ue000'
    while prefix in text:
        prefix += '_'
    links = {}

    def protect(match):
        token = prefix + str(len(links)) + '\ue001'
        links[token] = match[0]
        return token

    text = EvidenceLedger.MARKER.sub(protect, text)
    text = re.sub(r'\bBase[- ]stats? (?:only|comparison only)[.;:]?\s*', '',
                  text, flags=re.IGNORECASE)
    text = re.sub(
        r'\b(?:enchants|gems|set bonuses|procs|character DPS|pet scaling)'
        r'(?:\s*(?:,|and)?\s*(?:enchants|gems|set bonuses|procs|character DPS|pet scaling))*'
        r'\s+(?:are )?not evaluated[.;]?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:Some )?acquisition sources are unverified[.]?\s*',
                  '', text, flags=re.IGNORECASE)
    stat = (r'[+\-]\d+(?:\.\d+)?\s*(?:weapon DPS|DPS|Agility|Strength|'
            r'Stamina|Intellect|Spirit|Armor|Attack Power|Spell Power|'
            r'Agi|Str|Sta|Int|Spi)\b')

    def parenthesis(match):
        value = match[0][1:-1]
        # Never change names, IDs, or formatting inside item/NPC links.
        parts, start = [], 0
        changed = False
        for marker in list(EvidenceLedger.MARKER.finditer(value)) + [None]:
            end = marker.start() if marker else len(value)
            segment, count = re.subn(stat + r'(?:\s*[,/]\s*' + stat + r')*',
                                     '', value[start:end], flags=re.IGNORECASE)
            changed |= count > 0
            parts.append(segment)
            if marker:
                parts.append(marker[0])
                start = marker.end()
        if not changed:
            return match[0]
        remaining = ''.join(parts).strip(' ,;/')
        if not remaining:
            return ''
        if remaining.lower().startswith('from '):
            return remaining
        return '(' + remaining + ')'

    text = re.sub(r'\([^()]*\)', parenthesis, text)
    text = re.sub(r' +([.,;])', r'\1', re.sub(r' {2,}', ' ', text)).strip()
    for token, marker in links.items():
        text = text.replace(token, marker)
    return text
