"""Cross-domain helper logic for guide tool mixins."""

import difflib
import re


class GuideToolSharedMixin:
    """Shared matching helpers used across multiple domains."""

    CLASS_IDS = {
        'warrior': 1, 'paladin': 2, 'hunter': 3, 'rogue': 4,
        'priest': 5, 'death knight': 6, 'shaman': 7, 'mage': 8,
        'warlock': 9, 'druid': 11
    }

    _NORMALIZE_RE = re.compile(r'[^a-z0-9]+')

    @staticmethod
    def _fuzzy_dict_match(
        user_input, lookup_dict, threshold=0.6
    ):
        if user_input in lookup_dict:
            return (
                user_input,
                lookup_dict[user_input],
            )

        words = user_input.split()
        candidates = [
            k for k in lookup_dict
            if k in words or any(
                w.startswith(k) for w in words
            )
        ]
        if candidates:
            best = max(candidates, key=len)
            return best, lookup_dict[best]

        matches = difflib.get_close_matches(
            user_input, lookup_dict.keys(),
            n=1, cutoff=threshold,
        )
        if matches:
            match = matches[0]
            shorter = min(len(user_input), len(match))
            longer = max(len(user_input), len(match))
            if shorter >= 3 and longer <= shorter * 2:
                return match, lookup_dict[match]

        return None, None

    @classmethod
    def _normalize_lookup_text(cls, value: str) -> str:
        return cls._NORMALIZE_RE.sub(
            " ", value.lower()
        ).strip()

    @classmethod
    def _score_name_match(
        cls, query: str, candidate: str
    ) -> int:
        q = cls._normalize_lookup_text(query)
        c = cls._normalize_lookup_text(candidate)

        if not q or not c:
            return 0
        if q == c:
            return 1000
        if c.startswith(q):
            return 850 - max(0, len(c) - len(q))
        if q in c:
            return 700 - max(0, len(c) - len(q))

        q_words = q.split()
        c_words = c.split()
        if q_words and all(word in c_words for word in q_words):
            return 600 - max(0, len(c_words) - len(q_words))

        ratio = difflib.SequenceMatcher(
            None, q, c
        ).ratio()
        if ratio >= 0.78:
            return int(ratio * 500)

        return 0

    @classmethod
    def _is_ambiguous_top_match(
        cls, matches: list[dict]
    ) -> bool:
        if len(matches) < 2:
            return False

        top = matches[0]
        second = matches[1]
        top_score = top.get('score', 0)
        second_score = second.get('score', 0)
        top_name = cls._normalize_lookup_text(
            top.get('name', '')
        )
        second_name = cls._normalize_lookup_text(
            second.get('name', '')
        )

        if (
            top_name and second_name and
            top_name == second_name and
            second_score >= top_score - 25
        ):
            return True
        if top_score < 650:
            return (
                second_score >= 300 and
                second_score >= top_score - 100
            )
        if second_score >= top_score - 25:
            return True
        return False
