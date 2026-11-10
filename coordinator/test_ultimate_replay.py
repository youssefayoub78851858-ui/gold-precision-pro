import json
import pathlib
import sqlite3
import tempfile
import unittest
from ultimate_replay import replay

class AuditReplay(unittest.TestCase):
    def test_restart_idempotence_and_reproducible_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            db = pathlib.Path(directory) / 'audit.sqlite3'
            fixture = pathlib.Path(__file__).parent / 'fixtures/ultimate-synthetic.json'
            first = replay(fixture, db)
            second = replay(fixture, db)
            self.assertEqual(first, second)
            with sqlite3.connect(db) as connection:
                rows = connection.execute('SELECT input_json,report_json FROM ultimate_audit').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0][0]), json.loads(fixture.read_text()))
            self.assertFalse(json.loads(rows[0][1])['executable'])
