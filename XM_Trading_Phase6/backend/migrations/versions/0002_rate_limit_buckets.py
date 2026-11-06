"""Add shared database-backed API rate-limit buckets."""
from alembic import op
import sqlalchemy as sa

revision = "0002_rate_limits"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "rate_limit_buckets" not in inspector.get_table_names():
        op.create_table(
            "rate_limit_buckets",
            sa.Column("bucket_key", sa.String(length=255), primary_key=True),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade():
    if "rate_limit_buckets" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("rate_limit_buckets")
