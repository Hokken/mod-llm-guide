"""Conservative, request-local checks on lookup completeness, not intent."""

import json
import re


class AnswerReadiness:
    def __init__(self):
        self.checks = {}

    def record(self, name, arguments, result, executor):
        # Keep separate searches separate; a successful retry replaces only
        # the same call's previous failure. Never persist across requests.
        key = (name, json.dumps(arguments, sort_keys=True))
        notes = []
        usable = True
        if result.startswith(('Error executing tool:', 'Unknown tool:',
                              'Invalid tool arguments:')):
            usable = False
            notes.append('A requested lookup failed; its facts remain unverified.')
        elif not result.strip() or result.startswith(('No ', 'Please specify',
                'Unknown ', 'I found multiple items matching')) or re.match(
                r"Item '.+' not found\.$", result):
            usable = False
            notes.append('A lookup returned no resolved match or needs more '
                         'detail. This does not prove the requested thing '
                         'does not exist. Clarify the target or search scope.')
        elif name == 'get_character_context' and executor.snapshot is None:
            usable = bool(getattr(executor, 'character_summary', '').strip())
            notes.append('The full character snapshot is unavailable; any '
                         'legacy summary may be incomplete.')
        elif name == 'find_service_npc':
            if not re.search(r'\[\[npc:\d+:', result):
                usable = False
                notes.append('No verified service NPC was returned. A known '
                             'NPC name or a more specific location may help.')
            elif not re.search(r'~\d+(?:\.\d+)? (?:yards|m|km)\b', result):
                notes.append('Distance to the service NPC is unavailable; '
                             'I cannot establish which NPC is closest.')
        elif name == 'find_item_upgrades':
            if not any(comparison in result for comparison in
                       executor.item_comparisons.values()):
                usable = False
                notes.append('No verified upgrade comparison was returned. '
                             'Confirm the current item and role before '
                             'comparing again.')
            if 'Source not found' in result:
                notes.append('Acquisition sources are unverified.')
        if name == 'get_flight_paths' and usable:
            notes.append('Travel data is a limited route table, not a verified '
                         'end-to-end journey. I cannot establish the fastest '
                         'route or which flight nodes you have unlocked.')
        self.checks[key] = (usable, notes)

    def notes(self):
        return list(dict.fromkeys(note for _, notes in self.checks.values()
                                  for note in notes))

    def blocked(self):
        return bool(self.checks) and not any(
            usable for usable, _ in self.checks.values())

    def prompt(self):
        notes = self.notes()
        if not notes:
            return ''
        return ('\n\nAnswer-readiness checks (code-generated):\n- ' +
                '\n- '.join(notes) +
                '\nUse another relevant lookup when it can fill a gap, within '
                'the existing tool-round limit. Do not repeat an unchanged '
                'failed lookup. Otherwise explain the limitation or ask for '
                'the missing detail. Answer only the supported parts; do not '
                'claim a complete result or invent missing facts.')

    def finalize(self, response):
        notes = self.notes()
        if not notes:
            return response
        if self.blocked():
            # Do not publish a confident model answer based only on failures,
            # ambiguity, or absent results. No raw backend errors reach chat.
            if any('lookup failed' in note for note in notes):
                return 'I could not verify that right now. Please try again.'
            return ('I could not find a clear match. Which name or location '
                    'do you mean?')
        # Full diagnostics stay in the model context, not in player chat.
        # Preserve a short caveat without repeating known source wording.
        if all(note == 'Acquisition sources are unverified.' for note in notes):
            return response
        if any('Travel data' in note for note in notes):
            caveat = ('I cannot establish the fastest route or which flight '
                      'nodes you have unlocked.')
        elif any('closest' in note for note in notes):
            caveat = 'Distance is unavailable, so I cannot confirm the closest NPC.'
        else:
            caveat = 'Some requested details remain unverified.'
        return response if caveat.lower() in response.lower() else response + ' ' + caveat
