import tempfile
import unittest
from pathlib import Path
from cados.services.storage import DataStore
from cados.services.training_journal import TrainingJournal
from cados.core.workout_engine import WorkoutEngine
from cados.models.workout import WorkoutTemplate, WorkoutTemplateBlock
from fakes import FakeTrainer


class TrainingJournalTests(unittest.TestCase):
    def test_crash_restore_preserves_time_samples_and_session_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DataStore(Path(directory)/'test.sqlite3')
            journal = TrainingJournal(store)
            engine = WorkoutEngine(FakeTrainer())
            workout = WorkoutTemplate(name='Recovery test',description='',author='',ftp_reference=None,
                blocks=(WorkoutTemplateBlock(kind='steady', label='Step 1', duration_sec=120, target_watts=300),), source_path=Path('test.json'))
            engine.load_workout(workout)
            engine.start()
            engine.tick(.2)
            for _ in range(30):
                engine.tick(1)
            journal.save(engine.checkpoint(), engine.metrics.samples)
            for _ in range(5):
                engine.tick(1)
            journal.save(engine.checkpoint(), engine.metrics.samples)
            draft = TrainingJournal(store).load()
            self.assertEqual(len(draft['samples']), 35)
            recovered = WorkoutEngine(FakeTrainer())
            recovered.restore_checkpoint(draft, workout)
            self.assertEqual(recovered.state, 'paused')
            self.assertFalse(recovered.snapshot().auto_paused)
            recovered.tick(1)
            self.assertEqual(recovered.elapsed_sec, 35)
            self.assertEqual(recovered.metrics.summary(250), engine.metrics.summary(250))
            recovered.stop()
            self.assertEqual(recovered.pending_session.id, draft['session_id'])
            store.save_session(recovered.pending_session)
            # Simulated second crash before the draft was cleared.
            self.assertIsNone(TrainingJournal(store).load())
