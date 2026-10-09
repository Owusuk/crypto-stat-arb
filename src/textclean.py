"""Normalise typography for every generated deliverable: plain hyphens instead
of en/em dashes or the unicode minus, and straight quotes instead of curly."""

_MAP = {
    "—": "-", "–": "-", "‒": "-", "‐": "-", "‑": "-",
    "−": "-", "―": "-",
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "…": "...",
}


def clean(s):
    if not isinstance(s, str):
        return s
    for k, v in _MAP.items():
        s = s.replace(k, v)
    return s


BAD = set(_MAP)


def has_bad(s):
    return any(ch in BAD for ch in s)
