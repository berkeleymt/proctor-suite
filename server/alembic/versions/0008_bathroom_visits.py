"""bathroom log: one row per student leaving the room

Revision ID: 0008

Additive only, so `deploy.sh --rollback` stays safe. Rows go away with their room (Empty).
"""

from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE bathroom_visits (
            id uuid PRIMARY KEY,
            room_id text NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
            student_id text NOT NULL,
            left_ms bigint NOT NULL,
            back_ms bigint
        )""")
    op.execute("CREATE INDEX bathroom_visits_room ON bathroom_visits (room_id, left_ms)")


def downgrade() -> None:
    op.execute("DROP TABLE bathroom_visits")
