"""projector display sizes, one per room (protocol 0.13.0)

Revision ID: 0010

Additive only, so `deploy.sh --rollback` stays safe: the old code reads rooms with named fields
(the new column is ignored) and its INSERT leaves the column to its default.
"""

from alembic import op

revision = "0010"
down_revision = "0009"


def upgrade() -> None:
    op.execute("ALTER TABLE rooms ADD COLUMN display jsonb NOT NULL DEFAULT '{}'::jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE rooms DROP COLUMN display")
