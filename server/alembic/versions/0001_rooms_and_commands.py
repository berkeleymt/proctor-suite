"""rooms and commands

Revision ID: 0001
"""

from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE rooms (
            room_id text PRIMARY KEY,
            name text NOT NULL UNIQUE,
            test_name text NOT NULL,
            duration_ms bigint NOT NULL,
            created_at_ms bigint NOT NULL,
            version integer NOT NULL
        )""")
    op.execute("""
        CREATE TABLE commands (
            seq bigserial PRIMARY KEY,
            command_id uuid NOT NULL UNIQUE,
            room_id text NOT NULL REFERENCES rooms(room_id),
            type text NOT NULL,
            session_id text NOT NULL,
            actor_kind text,
            claimed_at_ms bigint,
            received_at_ms bigint,
            delta_ms bigint,
            is_event boolean NOT NULL,
            outcome text NOT NULL,
            reason text
        )""")
    op.execute("CREATE INDEX commands_room_seq ON commands (room_id, seq)")


def downgrade() -> None:
    op.execute("DROP TABLE commands")
    op.execute("DROP TABLE rooms")
