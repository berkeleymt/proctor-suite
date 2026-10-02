"""clarification edits (kept history), per-room hide/delete, and a persisted version counter

Revision ID: 0004

Additive only, so `deploy.sh --rollback` stays safe. `clar_counter` exists because deleting a
clarification removes its row; without it a restart could rebuild a smaller version counter and
devices would ignore newer snapshots.
"""

from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE clarifications
            ADD COLUMN previous text[] NOT NULL DEFAULT '{}',
            ADD COLUMN edited_at_ms bigint,
            ADD COLUMN hidden_room_ids text[] NOT NULL DEFAULT '{}',
            ADD COLUMN removed_room_ids text[] NOT NULL DEFAULT '{}'""")
    op.execute("""
        CREATE TABLE clar_counter (
            id smallint PRIMARY KEY CHECK (id = 1),
            rev integer NOT NULL
        )""")


def downgrade() -> None:
    op.execute("DROP TABLE clar_counter")
    op.execute("""
        ALTER TABLE clarifications
            DROP COLUMN previous, DROP COLUMN edited_at_ms,
            DROP COLUMN hidden_room_ids, DROP COLUMN removed_room_ids""")
