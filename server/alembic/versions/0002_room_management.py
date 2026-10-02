"""room management: sessions (reset), soft delete, doc url

Revision ID: 0002
"""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.execute("ALTER TABLE rooms ADD COLUMN session_seq integer NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE rooms ADD COLUMN session_created_ms bigint")
    op.execute("ALTER TABLE rooms ADD COLUMN deleted boolean NOT NULL DEFAULT false")
    op.execute("ALTER TABLE rooms ADD COLUMN doc_url text")


def downgrade() -> None:
    for col in ("doc_url", "deleted", "session_created_ms", "session_seq"):
        op.execute(f"ALTER TABLE rooms DROP COLUMN {col}")
