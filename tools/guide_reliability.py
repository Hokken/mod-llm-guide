"""Request snapshots and evidence validation shared by provider adapters."""

import json
import re
import unicodedata


ANSWER_RULES = (
    "\n\nPrevious answers help resolve references such as there or that item, "
    "but are not current factual evidence. Recheck locations, routes, stats "
    "and availability with appropriate tools. Historical entity links may "
    "be identity-checked by the bridge; this does not verify those claims. "
    "\n\nFor personal equipment or professions, call get_character_context. "
    "Use its current equipment slot labels exactly: rings are not trinkets "
    "and back items are neither. Preserve all returned item link markers. "
    "Only explicitly identified professions are professions; riding is a "
    "travel skill and racial skills/abilities are not professions. Current "
    "request data overrides earlier conversation history. "
    "For upgrades, use find_item_upgrades and consider measured gains AND losses internally. "
    "and include returned acquisition sources or explicitly say the source "
    "is unknown. Meeting equip requirements does not establish acquisition "
    "feasibility. Item level is not required character level. These are "
    "base-stat candidates, not simulated or exhaustive rankings: do not say "
    "best, no-brainer, strictly better, or trades nothing. Enchants, gems, "
    "procs and other excluded effects can change the result. Weapon DPS "
    "is specific to that weapon, not a character DPS gain. For hunters, "
    "do not treat melee weapon DPS as ranged DPS or infer pet scaling from "
    "an agility delta. Do not invent class/pet mechanics the tools cannot "
    "verify. These are internal reasoning constraints, not boilerplate for "
    "the player. For ordinary recommendations, give the clickable item, "
    "where to get it, and a short qualitative reason. Item tooltips show "
    "stats: omit numeric stat lists and parenthetical stat comparisons unless "
    "the player explicitly requests numbers or a detailed comparison. "
    "Put an unknown source beside that item, never in a blanket closing warning. "
    "Do not add 'base stats only' or "
    "lists of unevaluated enchants, gems, procs or pet scaling. Discuss an "
    "excluded effect only when the player asks about it or it materially "
    "affects the recommendation; do not invent its impact."
)


def decode_snapshot(raw):
    """Accept legacy requests; reject malformed or unknown new contracts."""
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict) or int(data.get("version", 0)) != 1:
        raise ValueError("Unsupported character snapshot")
    for field in ("level", "race_mask", "class_mask", "captured_at"):
        data[field] = int(data[field])
    for field in ("skills", "reputation", "equipment"):
        data[field] = {
            str(key): int(value)
            for key, value in (data.get(field) or {}).items()
        }
    data["eligible_quest_ids"] = [
        int(value) for value in (data.get("eligible_quest_ids") or [])
    ]
    data["known_spells"] = [
        int(value) for value in (data.get("known_spells") or [])
    ]
    return data


def requires_evidence(question):
    # Only unambiguous social acknowledgements bypass factual lookups.
    return question.strip().lower().rstrip(".!?") not in {
        "hi", "hello", "hey", "thanks", "thank you", "cheers", "bye",
        "goodbye", "ok", "okay",
    }


def validate_arguments(schema, value):
    if not isinstance(value, dict):
        return "Tool arguments must be an object."
    properties = schema.get("properties", {})
    alternatives = schema.get('anyOf', [])
    if alternatives and all(validate_arguments(
            dict(schema, anyOf=[], **branch), value) for branch in alternatives):
        return 'Supply at least one of the required alternative arguments.'
    for key in schema.get("required", []):
        if key not in value:
            return f"Missing required argument: {key}"
    types = {
        "string": str, "integer": int, "number": (int, float),
        "boolean": bool, "array": list, "object": dict,
    }
    for key, item in value.items():
        if key not in properties:
            return f"Unknown argument: {key}"
        definition = properties[key]
        expected = types.get(definition.get("type"))
        if expected and (not isinstance(item, expected) or (
                isinstance(item, bool) and definition.get("type") in
                {"integer", "number"})):
            return f"Invalid type for argument: {key}"
        if "enum" in definition and item not in definition["enum"]:
            return f"Invalid value for argument: {key}"
        if 'minimum' in definition and item < definition['minimum']:
            return f"Invalid value for argument: {key}"
        if definition.get('type') == 'array':
            expected_item = types.get(definition.get('items', {}).get('type'))
            if expected_item and any(
                    not isinstance(entry, expected_item) or
                    isinstance(entry, bool) for entry in item):
                return f"Invalid array element for argument: {key}"
    return None


class EvidenceLedger:
    """Track returned markers, not merely whether a tool was invoked."""

    MARKER = re.compile(r"\[\[(item|quest|spell|npc):(\d+):[^\]]+\]\]")

    def __init__(self):
        self.results = []
        self.markers = set()

    def record(self, result):
        if result.startswith(("Error executing tool:", "Unknown tool:",
                              "Invalid tool arguments:")):
            return
        self.results.append(result)
        self.markers.update(match.group(0) for match in
                            self.MARKER.finditer(result))

    def validate(self, response, required):
        if not response.strip():
            raise ValueError("Provider returned an empty answer")
        if required and not self.results:
            raise ValueError("No successful factual lookup")
        for match in self.MARKER.finditer(response):
            if match[0] not in self.markers:
                raise ValueError(
                    "Answer contains an unverified entity link: "
                    f"{match[1]} ID {match[2]}")
        if "|H" in response or "|h" in response:
            raise ValueError("Answer contains a raw game hyperlink")
        remainder = self.MARKER.sub('', response)
        if re.search(r'\[\[(?:item|quest|spell|npc):', remainder):
            raise ValueError("Answer contains a malformed entity link")

    @staticmethod
    def identity(marker):
        """Entity identity excludes link presentation metadata."""
        kind, entity_id, name = marker[2:-2].split(':', 2)
        if kind in {'item', 'quest'}:
            parts = name.rsplit(':', 1)
            if len(parts) == 2 and re.fullmatch(r'-?\d+', parts[1]):
                name = parts[0]
        name = unicodedata.normalize('NFKC', name)
        name = name.translate(str.maketrans({'’': "'", '‘': "'"}))
        return kind, int(entity_id), ' '.join(name.casefold().split())

    def canonicalize_links(self, response):
        """Repair presentation only when both entity ID and name agree."""

        candidates = {}
        for marker in self.markers:
            candidates.setdefault(self.identity(marker), set()).add(marker)

        def replace(match):
            if match[0] in self.markers:
                return match[0]
            matches = candidates.get(self.identity(match[0]), set())
            return next(iter(matches)) if len(matches) == 1 else match[0]

        return self.MARKER.sub(replace, response)

    def link_item_mentions(self, response):
        """Link exact, unambiguous item names from this request's evidence."""
        names = {}
        for marker in self.markers:
            match = re.fullmatch(r'\[\[item:\d+:(.+):\d+\]\]', marker)
            if match:
                names.setdefault(match[1], set()).add(marker)
        links = {name: next(iter(markers)) for name, markers in names.items()
                 if len(markers) == 1}
        if not links:
            return response
        alternatives = '|'.join(re.escape(name) for name in
                                sorted(links, key=len, reverse=True))
        pattern = re.compile(
            r'(?<!\w)(?:\[(' + alternatives + r')\]|(' + alternatives +
            r'))(?!\w)')

        def replace(match):
            return links[match[1] or match[2]]
        # Preserve existing entity markers; never replace a name inside one.
        parts, start = [], 0
        for match in self.MARKER.finditer(response):
            parts.append(pattern.sub(replace, response[start:match.start()]))
            parts.append(match[0])
            start = match.end()
        parts.append(pattern.sub(replace, response[start:]))
        return ''.join(parts)
