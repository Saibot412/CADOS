"""Incremental crash recovery journal stored separately from completed sessions."""
import json
from cados.services.storage import encode


class TrainingJournal:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS training_draft (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS training_draft_samples (position INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            ''')

    def save(self, payload, samples):
        with self.store.connection() as db:
            old = db.execute('SELECT payload FROM training_draft WHERE id=1').fetchone()
            if old is None or json.loads(old[0])['session_id'] != payload['session_id']:
                db.execute('DELETE FROM training_draft_samples')
            count = db.execute('SELECT count(*) FROM training_draft_samples').fetchone()[0]
            db.executemany('INSERT INTO training_draft_samples VALUES (?, ?)',
                           ((i, encode(sample)) for i, sample in enumerate(samples[count:], start=count)))
            db.execute('INSERT OR REPLACE INTO training_draft VALUES (1, ?)', (encode(payload),))

    def load(self):
        with self.store.connection() as db:
            row = db.execute('SELECT payload FROM training_draft WHERE id=1').fetchone()
            if row is None:
                return None
            payload = json.loads(row[0])
            # A crash between saving the final session and clearing its draft
            # must never offer that session a second time.
            if db.execute('SELECT 1 FROM sessions WHERE id=?', (payload['session_id'],)).fetchone():
                return None
            payload['samples'] = [json.loads(r[0]) for r in db.execute('SELECT payload FROM training_draft_samples ORDER BY position')]
            return payload

    def clear(self):
        with self.store.connection() as db:
            db.execute('DELETE FROM training_draft')
            db.execute('DELETE FROM training_draft_samples')
