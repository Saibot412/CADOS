import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

metadata = sa.MetaData()
json_type = sa.JSON().with_variant(JSONB(), "postgresql")
users = sa.Table("cados_users", metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("email", sa.String(254), unique=True, nullable=False),
    sa.Column("password", sa.Text, nullable=False),
    sa.Column("admin", sa.Boolean, nullable=False, default=False),
    sa.Column("active", sa.Boolean, nullable=False, default=True, server_default=sa.true()))
tokens = sa.Table("cados_auth_sessions", metadata,
    sa.Column("hash", sa.String(64), primary_key=True),
    sa.Column("user_id", sa.String(36), sa.ForeignKey(users.c.id), nullable=False),
    sa.Column("expires", sa.Float, nullable=False))
records = sa.Table("cados_sync_records", metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("owner", sa.String(36), sa.ForeignKey(users.c.id), nullable=True, index=True),
    sa.Column("kind", sa.String(16), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("deleted", sa.Boolean, nullable=False, default=False),
    sa.Column("payload", json_type, nullable=False))
versions = sa.Table("cados_schema_versions", metadata,
    sa.Column("version", sa.Integer, primary_key=True))

def migrate(engine):
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(sa.text("SELECT pg_advisory_xact_lock(73461209)"))
        metadata.create_all(connection)
        latest = connection.execute(sa.select(sa.func.max(versions.c.version))).scalar() or 0
        if latest > 2:
            raise RuntimeError("CADOS database requires a newer server version")
        if latest == 0:
            connection.execute(versions.insert().values(version=2))
        elif latest == 1:
            connection.execute(sa.text("ALTER TABLE cados_users ADD COLUMN active BOOLEAN NOT NULL DEFAULT TRUE"))
            connection.execute(versions.insert().values(version=2))
