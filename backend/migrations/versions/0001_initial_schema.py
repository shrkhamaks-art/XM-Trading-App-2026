"""Initial XM backend schema."""
from alembic import op
import sqlalchemy as sa
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())

def _indexes(table):
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}

def upgrade():
    tables = _tables()
    if "users" not in tables:
        op.create_table("users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("role", sa.String(30), nullable=False, server_default="investor"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    if "ix_users_email" not in _indexes("users"):
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    if "otp_challenges" not in tables:
        op.create_table("otp_challenges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("code_hash", sa.String(255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    otp_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("otp_challenges")}
    if "attempts" not in otp_columns:
        op.add_column("otp_challenges", sa.Column("attempts", sa.Integer(), nullable=True, server_default="0"))
        op.execute("UPDATE otp_challenges SET attempts = 0 WHERE attempts IS NULL")
        op.alter_column("otp_challenges", "attempts", nullable=False, server_default="0")
    if "created_at" not in otp_columns:
        op.add_column("otp_challenges", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        op.execute("UPDATE otp_challenges SET created_at = expires_at WHERE created_at IS NULL")
        op.alter_column("otp_challenges", "created_at", nullable=False)
    if "ix_otp_challenges_email" not in _indexes("otp_challenges"):
        op.create_index("ix_otp_challenges_email", "otp_challenges", ["email"])
    if "ix_otp_email_created" not in _indexes("otp_challenges"):
        op.create_index("ix_otp_email_created", "otp_challenges", ["email", "created_at"])
    if "audit_events" not in tables:
        op.create_table("audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_email", sa.String(255), nullable=False),
            sa.Column("event", sa.String(100), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    if "ix_audit_actor_created" not in _indexes("audit_events"):
        op.create_index("ix_audit_actor_created", "audit_events", ["actor_email", "created_at"])
    if "kyc_cases" not in tables:
        op.create_table("kyc_cases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("provider_reference", sa.String(255), nullable=True))

def downgrade():
    op.drop_table("kyc_cases")
    op.drop_index("ix_audit_actor_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_otp_email_created", table_name="otp_challenges")
    op.drop_index("ix_otp_challenges_email", table_name="otp_challenges")
    op.drop_table("otp_challenges")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
