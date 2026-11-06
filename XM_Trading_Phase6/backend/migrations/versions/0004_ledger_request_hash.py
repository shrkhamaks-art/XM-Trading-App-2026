"""Bind idempotency key to immutable posting payload."""
from alembic import op
import sqlalchemy as sa
revision = "0004_ledger_hash"
down_revision = "0003_sessions_ledger"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("ledger_transactions", sa.Column("request_hash", sa.String(64), nullable=True))
    op.execute("UPDATE ledger_transactions SET request_hash = 'legacy-unverified' WHERE request_hash IS NULL")
    with op.batch_alter_table("ledger_transactions") as batch:
        batch.alter_column("request_hash", existing_type=sa.String(64), nullable=False)
def downgrade():
    op.drop_column("ledger_transactions", "request_hash")
