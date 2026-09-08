import tempfile
import unittest
import os
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4

try:
    from fastapi.testclient import TestClient
    from server.app.main import create_app
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "Server test dependencies not installed")
class ServerApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        url = os.getenv("CADOS_TEST_DATABASE_URL")
        if url:
            import sqlalchemy as sa
            schema = "cados_test_" + uuid4().hex
            base_engine = sa.create_engine(url)
            with base_engine.begin() as db:
                db.execute(sa.schema.CreateSchema(schema))
            def cleanup():
                with base_engine.begin() as db:
                    db.execute(sa.schema.DropSchema(schema, cascade=True))
                base_engine.dispose()
            self.addCleanup(cleanup)
            engine = base_engine.execution_options(schema_translate_map={None: schema})
            with patch("server.app.main.sa.create_engine", return_value=engine):
                self.app = create_app(url, "http://testserver", bootstrap=("admin@example.test", "test-password-123"))
        else:
            self.app = create_app("sqlite:///" + str(Path(self.temp.name)/"server.sqlite3"),
                "http://testserver", bootstrap=("admin@example.test", "test-password-123"))
        self.client = self.enterContext(TestClient(self.app))
        self.client.headers["X-Cados-Request"] = "1"
        self.login()

    def login(self, email="admin@example.test"):
        response = self.client.post("/api/v1/auth/login", json={"email": email,"password":"test-password-123"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def change(self, kind="profile"):
        identifier = str(uuid4())
        return {"id":identifier,"kind":kind,"revision":0,"payload":{"id":identifier,"name":"Tester","ftp":250}}

    def save(self, record):
        return self.client.post("/api/v1/sync", json={"changes":[record]})

    def test_login_cookie_logout_and_origin_protection(self):
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code,200)
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers={"origin":"https://evil.test"}).status_code,403)
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code,200)
        self.assertEqual(self.client.get("/api/v1/sync").status_code,401)

    def test_anyone_can_register_with_matching_passwords(self):
        payload = {"email": "new@example.test", "password": "new-password-123",
                   "password_confirmation": "new-password-123", "name": "Neue Person",
                   "ftp": 245, "weight_kg": 67.5}
        self.assertEqual(self.client.post("/api/v1/auth/register", json=payload).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={
            "email": payload["email"], "password": payload["password"]}).status_code, 200)
        profiles = [r["payload"] for r in self.client.get("/api/v1/sync").json()["records"] if r["kind"] == "profile"]
        self.assertEqual(profiles, [{"id": profiles[0]["id"], "name": "Neue Person", "ftp": 245,
                                    "weight_kg": 67.5, "max_hr": None,
                                    "created_at": profiles[0]["created_at"], "updated_at": profiles[0]["updated_at"]}])
        self.assertEqual(self.client.post("/api/v1/auth/register", json={
            **payload, "password_confirmation": "different-password-456"}).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/auth/register", json=payload).status_code, 409)

    def test_profiles_are_private_and_stale_revisions_rejected(self):
        record=self.change()
        self.assertEqual(self.save(record).status_code,200)
        self.assertEqual(self.save(record).status_code,409)
        self.assertEqual(self.client.post("/api/v1/users",json={"email":"friend@example.test","password":"test-password-123"}).status_code,200)
        self.login("friend@example.test")
        visible=self.client.get("/api/v1/sync").json()["records"]
        self.assertNotIn(record["id"],[r["id"] for r in visible])
        record["revision"]=1
        self.assertEqual(self.save(record).status_code,403)
        self.assertEqual(self.client.post("/api/v1/users",json={"email":"other@example.test","password":"test-password-123"}).status_code,403)

    def test_admin_can_disable_reactivate_and_delete_other_users(self):
        created = self.client.post("/api/v1/users", json={"email": "friend@example.test", "password": "test-password-123"})
        self.assertEqual(created.status_code, 200)
        friend = next(item for item in self.client.get("/api/v1/users").json()["users"] if item["email"] == "friend@example.test")
        self.assertTrue(friend["active"])
        self.assertEqual(self.client.patch("/api/v1/users/" + friend["id"], json={"active": False}).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"email": friend["email"], "password": "test-password-123"}).status_code, 401)
        self.login()
        self.assertEqual(self.client.patch("/api/v1/users/" + friend["id"], json={"active": True}).status_code, 200)
        self.assertEqual(self.client.delete("/api/v1/users/" + friend["id"]).status_code, 200)
        self.assertNotIn(friend["id"], [item["id"] for item in self.client.get("/api/v1/users").json()["users"]])

    def test_workout_import_delete_and_shared_library(self):
        raw=b'<workout_file><name>Import</name><workout><SteadyState Duration="60" Power="0.8"/></workout></workout_file>'
        result=self.client.post("/api/v1/import?filename=test.zwo&shared=true",content=raw)
        self.assertEqual(result.status_code,200,result.text)
        record=result.json()["records"][0]
        self.assertEqual(record["payload"]["blocks"][0]["target_pct_ftp"],0.8)
        record["deleted"]=True
        self.assertEqual(self.save(record).status_code,200)
        result=self.client.get("/api/v1/sync").json()["records"]
        self.assertTrue(next(r for r in result if r["id"]==record["id"])["deleted"])

    def test_batch_is_atomic(self):
        record=self.change()
        bad=self.change();bad["kind"]="unknown"
        result=self.client.post("/api/v1/sync",json={"changes":[record,bad]})
        self.assertEqual(result.status_code,422)
        self.assertNotIn(record["id"],[r["id"] for r in self.client.get("/api/v1/sync").json()["records"]])

    def test_password_change_revokes_existing_tokens(self):
        self.assertEqual(self.client.post("/api/v1/auth/password",json={"email":"", "password":"different-password-456"}).status_code,200)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code,401)

    def test_web_and_bundled_assets_are_served(self):
        self.assertEqual(self.client.get("/").status_code,200)
        self.assertEqual(self.client.get("/static/app.js").status_code,200)
        self.assertEqual(len(self.client.get("/api/v1/sync").json()["records"]),26)
