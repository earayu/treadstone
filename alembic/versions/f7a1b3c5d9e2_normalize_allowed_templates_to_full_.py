"""normalize allowed_templates to full K8s names

Converts short template names ("tiny") to full K8s CRD names ("aio-sandbox-tiny")
in tier_template and user_plan tables. This handles both existing production data
and seed data inserted by migration 9f3a6a152a5c which used short names.

Revision ID: f7a1b3c5d9e2
Revises: 9f3a6a152a5c
Create Date: 2026-03-28 12:00:00.000000

"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a1b3c5d9e2"
down_revision: str | Sequence[str] | None = "9f3a6a152a5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHORT_TO_FULL = {
    "tiny": "aio-sandbox-tiny",
    "small": "aio-sandbox-small",
    "medium": "aio-sandbox-medium",
    "large": "aio-sandbox-large",
    "xlarge": "aio-sandbox-xlarge",
}

FULL_TO_SHORT = {v: k for k, v in SHORT_TO_FULL.items()}


def _replace_json_array(table: str, mapping: dict[str, str]) -> None:
    """Replace each value in the JSON array column allowed_templates using the given mapping."""
    conn = op.get_bind()
    rows = conn.execute(sa.text(f"SELECT id, allowed_templates FROM {table}")).fetchall()  # noqa: S608
    for row_id, templates in rows:
        if not templates:
            continue
        updated = [mapping.get(t, t) for t in templates]
        if updated != templates:
            conn.execute(
                sa.text(f"UPDATE {table} SET allowed_templates = :val WHERE id = :id"),  # noqa: S608
                {"val": json.dumps(updated), "id": row_id},
            )


def upgrade() -> None:
    _replace_json_array("tier_template", SHORT_TO_FULL)
    _replace_json_array("user_plan", SHORT_TO_FULL)


def downgrade() -> None:
    _replace_json_array("tier_template", FULL_TO_SHORT)
    _replace_json_array("user_plan", FULL_TO_SHORT)
