"""add audit event table

Revision ID: b1d94d9b8d42
Revises: 9f8b8c4d6e21
Create Date: 2026-03-26 16:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1d94d9b8d42"
down_revision: Union[str, Sequence[str], None] = "9f8b8c4d6e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.String(length=24), nullable=True),
        sa.Column("actor_api_key_id", sa.String(length=24), nullable=True),
        sa.Column("credential_type", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_event_action"), "audit_event", ["action"], unique=False)
    op.create_index("ix_audit_event_action_created_at", "audit_event", ["action", "created_at"], unique=False)
    op.create_index(op.f("ix_audit_event_actor_api_key_id"), "audit_event", ["actor_api_key_id"], unique=False)
    op.create_index(op.f("ix_audit_event_actor_type"), "audit_event", ["actor_type"], unique=False)
    op.create_index(op.f("ix_audit_event_actor_user_id"), "audit_event", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_audit_event_created_at"), "audit_event", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_event_request_id"), "audit_event", ["request_id"], unique=False)
    op.create_index(op.f("ix_audit_event_result"), "audit_event", ["result"], unique=False)
    op.create_index("ix_audit_event_target_type_target_id", "audit_event", ["target_type", "target_id"], unique=False)
    op.create_index(op.f("ix_audit_event_target_type"), "audit_event", ["target_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_event_target_type"), table_name="audit_event")
    op.drop_index("ix_audit_event_target_type_target_id", table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_result"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_request_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_created_at"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_actor_user_id"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_actor_type"), table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_actor_api_key_id"), table_name="audit_event")
    op.drop_index("ix_audit_event_action_created_at", table_name="audit_event")
    op.drop_index(op.f("ix_audit_event_action"), table_name="audit_event")
    op.drop_table("audit_event")
