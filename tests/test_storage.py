import os
import tempfile
import time
import unittest
from unittest.mock import patch

from app import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"AIRLEDGER_DB": self.directory.name + "/db.sqlite3"}
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_expiry_is_enforced_on_read(self):
        with patch("app.storage.time.time", return_value=time.time() - 86401):
            record_id = storage.save("owner", "dataset", {"table": "TEST"})
        self.assertIsNone(storage.get("owner", "dataset", record_id))

    def test_session_limits_and_scoped_clear(self):
        for _ in range(10):
            storage.save("owner", "dataset", {})
        with self.assertRaisesRegex(ValueError, "limit"):
            storage.save("owner", "dataset", {})
        other = storage.save("other", "dataset", {"retained": True})
        storage.clear("owner")
        self.assertEqual(storage.get("other", "dataset", other), {"retained": True})

    def test_metadata_projection_and_latest_matching_audience(self):
        def payload(role):
            return {
                "created_at": "2026-11-14T00:00:00Z",
                "role": role,
                "filename": "TEST.csv",
                "mode": "rules",
                "language": "en",
                "analysis": {"total": 2},
                "source_sha256": "test-fingerprint",
                "source_rows": [{"raw": "private test cells"}],
            }

        ward = storage.save("owner", "brief", payload("ward"))
        storage.save("owner", "brief", payload("school"))
        history = storage.brief_history("owner")
        self.assertEqual(len(history), 2)
        self.assertNotIn("source_rows", history[0])
        self.assertNotIn("analysis", history[0])
        self.assertEqual(storage.previous_brief("owner", "ward")["id"], ward)
        self.assertIsNone(storage.previous_brief("other", "ward"))
