"""clarifications: text posted to all rooms or a chosen subset, hideable

Revision ID: 0003
"""

from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE clarifications (
            id uuid PRIMARY KEY,
            body text NOT NULL,
            room_ids text[],
            hidden boolean NOT NULL DEFAULT false,
            created_at_ms bigint NOT NULL,
            rev integer NOT NULL
        )""")


def downgrade() -> None:
    op.execute("DROP TABLE clarifications")
