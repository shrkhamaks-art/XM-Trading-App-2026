"""Session revocation and non-operational ledger schema."""
from alembic import op
import sqlalchemy as sa
revision = "0003_sessions_ledger"
down_revision = "0002_rate_limits"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("auth_sessions", sa.Column("token_id", sa.String(100), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table("ledger_accounts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(100), unique=True, nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id")))
    op.create_table("ledger_transactions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("idempotency_key", sa.String(128), unique=True, nullable=False), sa.Column("reference", sa.String(255), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True)))
    op.create_table("ledger_entries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("ledger_transactions.id"), nullable=False), sa.Column("account_id", sa.Integer(), sa.ForeignKey("ledger_accounts.id"), nullable=False), sa.Column("debit", sa.Numeric(20,4), nullable=False), sa.Column("credit", sa.Numeric(20,4), nullable=False), sa.CheckConstraint("debit >= 0 AND credit >= 0 AND ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))", name="ck_ledger_entry_one_side"))
    op.create_index("ix_ledger_entries_transaction_id", "ledger_entries", ["transaction_id"])

def downgrade():
    op.drop_index("ix_ledger_entries_transaction_id", "ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_table("ledger_transactions")
    op.drop_table("ledger_accounts")
    op.drop_index("ix_auth_sessions_user_id", "auth_sessions")
    op.drop_table("auth_sessions")
