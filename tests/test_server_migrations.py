import importlib.util
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("sqlalchemy"), "Server dependencies required")
class ServerMigrationTests(unittest.TestCase):
    def test_version_one_database_gets_active_user_column(self):
        import sqlalchemy as sa
        from server.app.database import migrate, users

        with tempfile.TemporaryDirectory() as directory:
            engine = sa.create_engine("sqlite:///" + str(Path(directory) / "old.sqlite3"))
            with engine.begin() as connection:
                connection.execute(sa.text("""
                    CREATE TABLE cados_users (
                        id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) UNIQUE NOT NULL,
                        password TEXT NOT NULL, admin BOOLEAN NOT NULL
                    )
                """))
                connection.execute(sa.text("CREATE TABLE cados_schema_versions (version INTEGER PRIMARY KEY)"))
                connection.execute(sa.text("INSERT INTO cados_schema_versions (version) VALUES (1)"))
                connection.execute(sa.text("""
                    INSERT INTO cados_users (id, email, password, admin)
                    VALUES ('user-1', 'old@example.test', 'hash', 0)
                """))
            migrate(engine)
            with engine.connect() as connection:
                self.assertTrue(connection.execute(sa.select(users.c.active)).scalar())
            engine.dispose()
