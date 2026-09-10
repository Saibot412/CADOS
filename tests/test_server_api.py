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

    def test_publisher_is_server_owned_and_admin_can_delete_shared_workouts(self):
        profile = self.change()
        profile["payload"]["name"] = "Tobias"
        self.assertEqual(self.save(profile).status_code, 200)
        account = self.login()["user"]
        change = {"id": str(uuid4()), "kind": "workout", "revision": 0, "shared": True,
                  "publisher": {"name": "Forged", "user_id": "wrong"},
                  "payload": {"name": "Published", "blocks": [{"type": "steady", "duration_sec": 60, "target_watts": 200}]}}
        response = self.save(change)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()["records"][0]
        self.assertEqual(saved["publisher"], {"name": "Tobias", "user_id": account["id"]})
        modified = {**saved, "publisher": {"name": "Changed"}, "payload": {**saved["payload"], "name": "Edited"}}
        saved = self.save(modified).json()["records"][0]
        self.assertEqual(saved["publisher"]["name"], "Tobias")
        private_copy = {**saved, "id": str(uuid4()), "revision": 0, "shared": False}
        self.assertIsNone(self.save(private_copy).json()["records"][0]["publisher"])
        self.client.post("/api/v1/users", json={"email": "friend@example.test", "password": "test-password-123"})
        self.login("friend@example.test")
        visible = self.client.get("/api/v1/sync").json()["records"]
        self.assertEqual(next(r for r in visible if r["id"] == saved["id"])["publisher"]["name"], "Tobias")
        self.assertEqual(self.save({**saved, "deleted": True}).status_code, 403)
        self.assertEqual(self.save({**saved, "shared": False, "deleted": True}).status_code, 403)
        self.login()
        self.assertEqual(self.save({**saved, "deleted": True}).status_code, 200)
        self.assertTrue(next(r for r in self.client.get("/api/v1/sync").json()["records"] if r["id"] == saved["id"])["deleted"])

    def test_session_peak_hr_is_automatic_but_ftp_requires_confirmation(self):
        from test_session_analysis import test_session
        profile = self.change();profile["payload"].update(ftp=300,max_hr=180)
        saved_profile = self.save(profile).json()["records"][0]
        data = {**test_session(), "duration_sec":120,"status":"stopped","trainer_source":"test"}
        change = {"id":str(uuid4()),"kind":"session","revision":0,"payload":data}
        response = self.save(change)
        self.assertEqual(response.status_code,200,response.text)
        session=response.json()["records"][0]
        snapshot=self.client.get("/api/v1/sync").json()["records"]
        current=next(r for r in snapshot if r["id"]==profile["id"])
        self.assertEqual(current["payload"]["max_hr"],190)
        self.assertEqual(current["payload"]["ftp"],300)
        self.assertEqual(session["payload"]["ftp_test_result"]["estimated_ftp"],330)
        url="/api/v1/sessions/"+session["id"]+"/ftp"
        self.assertEqual(self.client.post(url,json={"profile_revision":saved_profile["revision"]}).status_code,409)
        self.assertEqual(self.client.post(url,json={"profile_revision":current["revision"]}).status_code,200)
        self.assertEqual(self.client.post(url,json={"profile_revision":current["revision"]}).status_code,409)
        updated=next(r for r in self.client.get("/api/v1/sync").json()["records"] if r["id"]==profile["id"])
        self.assertEqual(updated["payload"]["ftp"],330)
        self.assertEqual(updated["payload"]["max_hr"],190)
        # A later lower peak never decreases the stored maximum.
        lower={**data,"samples":[{"heart_rate":160}]}
        self.assertEqual(self.save({**change,"id":str(uuid4()),"payload":lower}).status_code,200)
        updated=next(r for r in self.client.get("/api/v1/sync").json()["records"] if r["id"]==profile["id"])
        self.assertEqual(updated["payload"]["max_hr"],190)
        self.client.post("/api/v1/users",json={"email":"friend@example.test","password":"test-password-123"})
        self.login("friend@example.test")
        self.assertEqual(self.client.post(url,json={"profile_revision":1}).status_code,404)

    def test_batch_is_atomic(self):
        record=self.change()
        bad=self.change();bad["kind"]="unknown"
        result=self.client.post("/api/v1/sync",json={"changes":[record,bad]})
        self.assertEqual(result.status_code,422)
        self.assertNotIn(record["id"],[r["id"] for r in self.client.get("/api/v1/sync").json()["records"]])

    def test_training_plan_is_private_and_validated(self):
        plan = {"id": str(uuid4()), "kind": "plan", "revision": 0, "payload": {
            "workout_id": str(uuid4()), "workout_name": "Intervalle", "date": "2026-09-13"}}
        self.assertEqual(self.save(plan).status_code, 200)
        self.assertIn(plan["id"], [record["id"] for record in self.client.get("/api/v1/sync").json()["records"]])
        invalid = {**plan, "id": str(uuid4()), "payload": {**plan["payload"], "date": "kein-datum"}}
        self.assertEqual(self.save(invalid).status_code, 422)

    def test_password_change_revokes_existing_tokens(self):
        self.assertEqual(self.client.post("/api/v1/auth/password",json={"email":"", "password":"different-password-456"}).status_code,200)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code,401)

    def test_live_connector_routes_telemetry_and_commands_to_the_same_account(self):
        token = self.login()["token"]
        with self.client.websocket_connect("/api/v1/live/browser") as browser:
            self.assertEqual(browser.receive_json(), {"type": "connector", "connected": False})
            with self.client.websocket_connect("/api/v1/live/connector", headers={"Authorization": "Bearer " + token}) as connector:
                self.assertEqual(connector.receive_json(), {"type": "browser", "connected": True})
                self.assertEqual(browser.receive_json(), {"type": "connector", "connected": True})
                connector.send_json({"type": "telemetry", "payload": {"current_watts": 250}})
                self.assertEqual(browser.receive_json(), {"type": "telemetry", "payload": {"current_watts": 250}})
                browser.send_json({"type": "command", "command": {"name": "pause"}})
                self.assertEqual(connector.receive_json(), {"name": "pause"})

    def test_web_and_bundled_assets_are_served(self):
        self.assertEqual(self.client.get("/").status_code,200)
        self.assertEqual(self.client.get("/static/app.js").status_code,200)
        self.assertEqual(self.client.get("/static/live-focus.js").status_code,200)
        self.assertEqual(self.client.get("/static/live-focus.css").status_code,200)
        release = self.client.get("/static/connector-release.json")
        self.assertEqual(release.status_code, 200)
        from cados import __version__
        self.assertEqual(release.json()["version"], __version__)
        self.assertIn("/v" + __version__ + "/", release.json()["macos"]["url"])
        self.assertEqual(self.client.get("/static/experience.js").status_code, 200)
        self.assertEqual(self.client.get("/static/experience.css").status_code, 200)
        self.assertEqual(len(self.client.get("/api/v1/sync").json()["records"]),26)

    def test_connector_pairing_is_approved_once_and_redeemed_once(self):
        begin = self.client.post('/api/v1/connector/pair/begin', json={}).json()
        pending = self.client.post('/api/v1/connector/pair/poll', json={'secret': begin['secret']})
        self.assertEqual(pending.json(), {'pending': True})
        self.assertEqual(self.client.post('/api/v1/connector/pair/approve', json={'code': begin['code']}).status_code, 200)
        self.assertEqual(self.client.post('/api/v1/connector/pair/approve', json={'code': begin['code']}).status_code, 409)
        result = self.client.post('/api/v1/connector/pair/poll', json={'secret': begin['secret']}).json()
        self.assertEqual(result['user']['email'], 'admin@example.test')
        self.assertEqual(self.client.post('/api/v1/connector/pair/poll', json={'secret': begin['secret']}).status_code, 410)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer '+result['token']}).status_code, 200)

    def test_connector_pairing_requires_login_and_rejects_expired_secrets(self):
        import sqlalchemy as sa
        from server.app.database import pairings
        begin = self.client.post('/api/v1/connector/pair/begin', json={}).json()
        self.client.cookies.clear()
        self.assertEqual(self.client.post('/api/v1/connector/pair/approve', json={'code': begin['code']}).status_code, 401)
        with self.app.state.engine.begin() as db:
            db.execute(pairings.update().values(expires=0))
        self.assertEqual(self.client.post('/api/v1/connector/pair/poll', json={'secret': begin['secret']}).status_code, 410)
