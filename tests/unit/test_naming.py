import re

from treadstone.core.naming import generate_sandbox_name

PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,53}[a-z0-9])?$")


def test_generate_name_pattern_and_prefix():
    for _ in range(100):
        name = generate_sandbox_name()
        assert name.startswith("sb-"), name
        assert PATTERN.fullmatch(name), name
        assert len(name) <= 55


def test_generate_name_retry_shape():
    # Not testing collisions here, just shape/entropy sanity
    names = {generate_sandbox_name() for _ in range(1000)}
    # Expect high uniqueness thanks to hex tail
    assert len(names) > 990
