import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from cados.config import AppConfig
from cados.models.profile import UserProfile
from cados.models.session import WorkoutSessionRecord
from cados.services.workout_catalog import WorkoutCatalog
from cados.services.storage import DataStore
from cados.services.account_sync import AccountSync

try:
    from fastapi.testclient import TestClient
    from server.app.main import create_app
except ImportError:
    TestClient = None


class Adapter:
    base_url="http://testserver"
    def __init__(self, client): self.client=client
    def _request(self,path,method="GET",payload=None):
        response=self.client.request(method,path,json=payload)
        if response.status_code != 200: raise RuntimeError(response.text)
        return response.json()


@unittest.skipIf(TestClient is None,"Server dependencies required")
class AccountSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.client=self.enterContext(TestClient(create_app("sqlite:///"+str(self.root/"server.sqlite3"),"http://testserver",bootstrap=("a@test.test","password-test-123"))))
        self.client.headers["X-Cados-Request"]="1"
        self.client.post("/api/v1/auth/login",json={"email":"a@test.test","password":"password-test-123"})
        self.config=AppConfig.load(self.root)
        self.store=DataStore(self.root/"desktop.sqlite3")
        self.sync=AccountSync(self.store,Adapter(self.client),self.config)

    def test_local_upload_new_install_download_and_conflict_preservation(self):
        profile=UserProfile(name="Tobias",ftp=250)
        self.store.save_profile(profile)
        self.sync.run()
        fresh=DataStore(self.root/"fresh.sqlite3")
        AccountSync(fresh,Adapter(self.client),self.config).run()
        self.assertEqual(fresh.list_profiles()[0].ftp,250)
        remote=next(r for r in self.client.get("/api/v1/sync").json()["records"] if r["id"]==profile.id)
        remote["payload"]["ftp"]=280
        self.assertEqual(self.client.post("/api/v1/sync",json={"changes":[remote]}).status_code,200)
        profile.ftp=260;self.store.save_profile(profile)
        count,conflicts=self.sync.run()
        self.assertEqual(conflicts,1)
        self.assertEqual(self.store.list_profiles()[0].ftp,280)
        with self.store.connection() as db:
            self.assertIn('260',db.execute("SELECT payload FROM sync_conflicts").fetchone()[0])
        self.assertEqual(self.sync.run()[1],0)

    def test_different_account_cannot_claim_existing_local_data(self):
        self.sync.run()
        with self.assertRaises(ValueError):self.sync.bind({"id":str(uuid4())})

    def test_failed_upload_is_retried_and_samples_survive_reinstall(self):
        session=WorkoutSessionRecord(user_id=str(uuid4()),user_name="Tester",workout_name="Offline",
            duration_sec=60,status="completed",trainer_source="test",samples=[{"watts":220,"duration_sec":60}])
        self.store.save_session(session)
        request=self.sync.client._request
        def offline(path,method="GET",payload=None):
            if method=="POST":raise OSError("network unavailable")
            return request(path,method,payload)
        with patch.object(self.sync.client,"_request",side_effect=offline),self.assertRaises(OSError):self.sync.run()
        self.assertEqual(self.store.list_sessions()[0].samples,session.samples)
        self.sync.run()
        fresh=DataStore(self.root/"reinstalled.sqlite3")
        AccountSync(fresh,Adapter(self.client),self.config).run()
        self.assertEqual(fresh.list_sessions()[0].to_dict(),session.to_dict())

    def test_server_plan_is_saved_locally(self):
        plan = {"id": str(uuid4()), "kind": "plan", "revision": 1, "deleted": False,
                "shared": False, "payload": {"workout_id": str(uuid4()), "workout_name": "Heute",
                                                   "date": "2026-09-13"}}
        self.sync.apply(plan)
        self.assertEqual(self.store.list_plans("2026-09-13")[0]["workout_name"], "Heute")

    def test_unchanged_sync_does_not_rewrite_history(self):
        self.sync.run()
        with patch.object(self.sync,"apply") as apply:
            self.sync.run()
            apply.assert_not_called()

    def test_deleted_bundled_workout_stays_hidden(self):
        bundled=Path(__file__).parents[1]/"cados/assets/workouts"
        catalog=WorkoutCatalog(bundled,self.store)
        self.sync.run()
        record=next(r for r in self.client.get("/api/v1/sync").json()["records"] if r["kind"]=="workout")
        source=record["payload"]["source_name"]
        record["deleted"]=True
        self.client.post("/api/v1/sync",json={"changes":[record]})
        self.sync.run()
        self.assertNotIn(source,[w.source_path.name for w in catalog.scan()])
        self.sync.run()
        self.assertNotIn(source,[w.source_path.name for w in catalog.scan()])
