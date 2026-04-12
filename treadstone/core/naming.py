import secrets
import string
from collections.abc import Iterable

# Keep lists compact initially; can be extended without API change.
_ADJECTIVES: tuple[str, ...] = (
    "brave",
    "calm",
    "clever",
    "crisp",
    "daring",
    "eager",
    "fuzzy",
    "gentle",
    "glossy",
    "humble",
    "icy",
    "jolly",
    "keen",
    "lively",
    "merry",
    "neat",
    "nimble",
    "proud",
    "quick",
    "quiet",
    "rapid",
    "shiny",
    "silent",
    "smart",
    "snug",
    "solid",
    "spry",
    "sturdy",
    "sunny",
    "swift",
    "tidy",
    "tiny",
    "vivid",
    "warm",
    "witty",
    "zesty",
    "bold",
    "bright",
    "chill",
    "clean",
)

_NOUNS: tuple[str, ...] = (
    "acorn",
    "amber",
    "anchor",
    "aster",
    "badge",
    "beacon",
    "birch",
    "breeze",
    "canyon",
    "cedar",
    "comet",
    "coral",
    "cotton",
    "crane",
    "ember",
    "falcon",
    "feather",
    "flint",
    "harbor",
    "heron",
    "horizon",
    "iron",
    "ivy",
    "juniper",
    "lagoon",
    "larch",
    "mesa",
    "minnow",
    "nebula",
    "oak",
    "onyx",
    "otter",
    "pebble",
    "pine",
    "quartz",
    "reef",
    "river",
    "spruce",
    "tundra",
    "willow",
)

_ALLOWED = set(string.ascii_lowercase + string.digits + "-")


def _slugify(parts: Iterable[str]) -> str:
    out: list[str] = []
    for part in parts:
        s = part.strip().lower().replace(" ", "-")
        s = "".join(ch for ch in s if ch in _ALLOWED)
        if s:
            out.append(s)
    return "-".join(out)


def generate_sandbox_name(prefix: str = "sb", suffix_hex_bytes: int = 2) -> str:
    """Generate a readable, regex-compliant sandbox name.

    Format: sb-<adjective>-<noun>-<hex>
    - All lowercase, hyphen-separated, ASCII only.
    - suffix_hex_bytes controls the length of the random tail (>=1).
    """
    if suffix_hex_bytes < 1:
        suffix_hex_bytes = 1
    adj = secrets.choice(_ADJECTIVES)
    noun = secrets.choice(_NOUNS)
    tail = secrets.token_hex(suffix_hex_bytes)
    return _slugify((prefix, adj, noun, tail))
