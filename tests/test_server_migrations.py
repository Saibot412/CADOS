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

    def test_version_two_adds_publisher_without_losing_workouts(self):
        import sqlalchemy as sa
        from server.app.database import migrate, records, versions
        with tempfile.TemporaryDirectory() as directory:
            engine = sa.create_engine("sqlite:///" + str(Path(directory)/"v2.sqlite3"))
            with engine.begin() as db:
                db.execute(sa.text("CREATE TABLE cados_schema_versions (version INTEGER PRIMARY KEY)"))
                db.execute(sa.text("INSERT INTO cados_schema_versions VALUES (2)"))
                db.execute(sa.text("CREATE TABLE cados_sync_records (id TEXT PRIMARY KEY, owner TEXT, kind TEXT, revision INTEGER, deleted BOOLEAN, payload JSON)"))
                db.execute(sa.text("INSERT INTO cados_sync_records VALUES ('old', NULL, 'workout', 4, FALSE, '{}')"))
            migrate(engine)
            migrate(engine)
            with engine.connect() as db:
                row = db.execute(sa.select(records)).mappings().one()
                self.assertEqual(row["id"], "old")
                self.assertEqual(row["revision"], 4)
                self.assertIsNone(row["publisher"])
                self.assertEqual(db.execute(sa.select(sa.func.max(versions.c.version))).scalar(), 3)
            engine.dispose()
