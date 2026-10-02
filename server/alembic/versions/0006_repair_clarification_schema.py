"""Repair the clarification schema if 0005 was recorded without its columns."""

from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE clarifications
            ADD COLUMN IF NOT EXISTS edited_room_ids text[] NOT NULL DEFAULT '{}'
    """)
    op.execute("""
        ALTER TABLE clarifications
            ADD COLUMN IF NOT EXISTS deleted boolean NOT NULL DEFAULT false
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE clarifications
            DROP COLUMN IF EXISTS edited_room_ids,
            DROP COLUMN IF EXISTS deleted
    """)
