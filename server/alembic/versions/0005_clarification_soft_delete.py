"""clarifications: soft delete (restore / empty) and per-room edited copies

Revision ID: 0005

Additive only, so `deploy.sh --rollback` stays safe.
"""

from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE clarifications
            ADD COLUMN deleted boolean NOT NULL DEFAULT false,
            ADD COLUMN edited_room_ids text[] NOT NULL DEFAULT '{}'""")


def downgrade() -> None:
    op.execute("ALTER TABLE clarifications DROP COLUMN deleted, DROP COLUMN edited_room_ids")
