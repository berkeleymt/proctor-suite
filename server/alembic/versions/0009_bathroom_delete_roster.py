"""bathroom records can be soft-deleted; ContestDojo roster

Revision ID: 0009

Additive only, so `deploy.sh --rollback` stays safe: the old code reads bathroom_visits with
named fields (the new column is ignored) and never touches roster_students.
"""

from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    op.execute("ALTER TABLE bathroom_visits ADD COLUMN deleted boolean NOT NULL DEFAULT false")
    op.execute("""
        CREATE TABLE roster_students (
            student_id text PRIMARY KEY,
            name text NOT NULL DEFAULT '',
            school text NOT NULL DEFAULT '',
            team text NOT NULL DEFAULT '',
            room text NOT NULL DEFAULT '',
            contact text NOT NULL DEFAULT '',
            source text NOT NULL,
            synced_at_ms bigint NOT NULL
        )""")


def downgrade() -> None:
    op.execute("DROP TABLE roster_students")
    op.execute("ALTER TABLE bathroom_visits DROP COLUMN deleted")
