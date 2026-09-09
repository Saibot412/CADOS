"""Exercise actual control while network and synchronization are unavailable."""
import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from cados.connector import ConnectorService
from cados.models.session import WorkoutSessionRecord
from cados.models.workout import WorkoutTemplate, WorkoutTemplateBlock
try:
    from server.app.main import validate_record, ConnectorHub
except ImportError:
    validate_record = ConnectorHub = None
from fakes import FakeTrainer, FakeHRMonitor


class ConnectorResilienceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        config = SimpleNamespace(paths=SimpleNamespace(database_path=Path(self.temp.name)/'data.sqlite3',
            bundled_workouts_dir=Path('cados/assets/workouts')),trainer_scan_timeout_sec=1,
            workout_library_url='http://127.0.0.1:1',workout_library_token='test')
        with patch('cados.connector.TrainerController',return_value=FakeTrainer()), patch('cados.connector.HRMonitorService',return_value=FakeHRMonitor()):
            self.service=ConnectorService(config)
        self.service.engine.load_workout(WorkoutTemplate(name='Offline',description='',author='',ftp_reference=None,
            blocks=(WorkoutTemplateBlock(kind='steady',label='Steady',duration_sec=30,target_watts=200,target_cadence=90),),source_path=Path('offline.json')))
        self.service.engine.start()

    async def test_control_and_local_stop_continue_during_failed_network_and_slow_sync(self):
        started=asyncio.Event()
        async def unavailable_network():
            started.set()
            await asyncio.Event().wait()
        async def slow_sync():
            await asyncio.Event().wait()
        self.service._network_loop=unavailable_network
        self.service._sync_loop=slow_sync
        task=asyncio.create_task(self.service.run())
        await started.wait()
        try:
            await asyncio.sleep(.65)
            self.assertGreater(self.service.engine.elapsed_sec,.4)
            self.service.submit_local_command('pause')
            await asyncio.sleep(.25)
            self.assertEqual(self.service.engine.state,'paused')
            elapsed=self.service.engine.elapsed_sec
            await asyncio.sleep(.25)
            self.assertEqual(self.service.engine.elapsed_sec,elapsed)
            self.service.submit_local_command('resume')
            await asyncio.sleep(.5)
            self.assertEqual(self.service.engine.state,'running')
            self.service.submit_local_command('stop')
            await asyncio.sleep(.25)
            sessions=self.service.store.list_sessions()
            self.assertEqual(len(sessions),1)
            self.assertTrue(self.service._sync_needed)
            self.assertEqual(sessions[0].status,'stopped')
        finally:
            self.service.close()
            await asyncio.wait_for(task,2)
        self.assertEqual(len(self.service.store.list_sessions()),1)

    async def test_slow_sync_worker_does_not_block_local_controls(self):
        entered, release = threading.Event(), threading.Event()
        def slow_sync():
            entered.set()
            release.wait(3)
        self.service._sync_completed_data = slow_sync
        local = asyncio.create_task(self.service._local_loop())
        sync = asyncio.create_task(self.service._sync_loop())
        try:
            await asyncio.wait_for(asyncio.to_thread(entered.wait), 1)
            await asyncio.sleep(.25)
            self.service.submit_local_command('pause')
            await asyncio.sleep(.25)
            self.assertEqual(self.service.engine.state, 'paused')
            self.assertFalse(release.is_set())
            self.assertGreater(self.service.engine.elapsed_sec, 0)
        finally:
            release.set()
            self.service.close()
            await asyncio.wait_for(asyncio.gather(local, sync), 2)

    async def test_bluetooth_disconnect_freezes_time_and_reconnect_ramps(self):
        engine=self.service.engine
        engine.tick(.2);engine.tick(1)
        elapsed=engine.elapsed_sec
        self.service.trainer.telemetry.connected=False
        engine.tick(1);engine.tick(1)
        self.assertEqual(engine.state,'paused')
        self.assertEqual(engine.elapsed_sec,elapsed)
        self.service.trainer.telemetry.connected=True
        snapshot=engine.tick(.2)
        self.assertEqual(snapshot.state,'running')
        self.assertTrue(snapshot.ramping)

    async def test_sleep_gap_requires_explicit_resume_without_counting_sleep(self):
        engine=self.service.engine;engine.tick(.2);engine.tick(1)
        elapsed=engine.elapsed_sec
        engine.tick(60);engine.tick(.2)
        self.assertEqual(engine.state,'paused')
        self.assertEqual(engine.elapsed_sec,elapsed)
        engine.resume();self.assertEqual(engine.tick(.2).state,'running')

    async def test_recovery_keeps_workout_and_measurements_and_completion_plan(self):
        engine=self.service.engine;engine.tick(.2)
        for _ in range(10):engine.tick(1)
        recovery=self.service._recovery()['payload']
        self.assertEqual(recovery['workout']['name'],'Offline')
        self.assertEqual(recovery['history'][-1]['elapsed'],10)
        self.assertEqual(recovery['telemetry']['elapsed_sec'],10)
        self.service._plan_id=str(uuid4())
        for _ in range(20):engine.tick(1)
        self.service._save_pending_session()
        session=self.service.store.list_sessions()[0]
        self.assertEqual(session.status,'completed')
        self.assertEqual(session.plan_id,self.service._plan_id)
        self.assertEqual(self.service._telemetry()['payload']['session_id'],session.id)

    @unittest.skipIf(ConnectorHub is None, "Server dependencies not installed")
    async def test_old_connector_disconnect_does_not_mark_replacement_offline(self):
        hub=ConnectorHub();old=object();new=object();hub.connectors['u']=new
        await hub.remove_connector('u',old)
        self.assertIs(hub.connectors['u'],new)


@unittest.skipIf(validate_record is None, "Server dependencies not installed")
class SessionFeedbackTests(unittest.TestCase):
    def test_feedback_and_plan_survive_roundtrip_and_invalid_values_are_rejected(self):
        session=WorkoutSessionRecord(user_id='test',user_name='Tester',workout_name='Workout',duration_sec=10,
            status='completed',trainer_source='test',plan_id=str(uuid4()),perceived_exertion=7)
        payload=session.to_dict()
        validate_record('session',payload,False)
        self.assertEqual(WorkoutSessionRecord.from_dict(payload).to_dict(),payload)
        for value in (0,11,True,4.5,'7'):
            with self.assertRaises(ValueError):validate_record('session',{**payload,'perceived_exertion':value},False)
