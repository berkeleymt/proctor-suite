"""runtime settings (name, icon, passwords) and the super-admin allowlist

Revision ID: 0007

Additive only, so `deploy.sh --rollback` stays safe. A row in `settings` overrides the matching
environment variable; with no row the .env value is used.
"""

from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE settings (
            key text PRIMARY KEY,
            value text NOT NULL,
            updated_at_ms bigint NOT NULL,
            updated_by text NOT NULL
        )""")
    op.execute("""
        CREATE TABLE super_admins (
            email text PRIMARY KEY,
            added_by text NOT NULL,
            added_at_ms bigint NOT NULL
        )""")


def downgrade() -> None:
    op.execute("DROP TABLE super_admins")
    op.execute("DROP TABLE settings")
