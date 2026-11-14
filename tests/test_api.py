import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app, requests_by_session

TABLE = "station,timestamp,pollutant,value,unit,duration_hours\nTEST North,2026-11-01,PM2.5,24,ug/m3,24\nTEST North,2026-11-02,PM2.5,30,ug/m3,24"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ, {"AIRLEDGER_DB": self.temp.name + "/test.sqlite3", "GEMINI_API_KEY": ""}
        )
        self.env.start()
        requests_by_session.clear()
        self.client = TestClient(app)
        self.client.get("/api/status")

    def tearDown(self):
        self.client.close()
        self.env.stop()
        self.temp.cleanup()

    def import_and_analyze(self, text=TABLE):
        result = self.client.post("/api/paste", json={"text": text})
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        analyzed = self.client.post(
            f"/api/datasets/{data['id']}/analyze",
            json={"mapping": data["mapping"], "options": {"date_order": "DMY"}},
        )
        self.assertEqual(analyzed.status_code, 200, analyzed.text)
        return data

    def create_brief(self, dataset, role="ward", language="en", use_ai=False):
        result = self.client.post(
            "/api/briefs",
            json={
                "dataset_id": dataset["id"],
                "role": role,
                "language": language,
                "reading_level": "simple",
                "use_ai": use_ai,
            },
        )
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_complete_workflow_export_and_snapshot_comparison(self):
        dataset = self.import_and_analyze()
        first = self.create_brief(dataset)
        self.assertEqual(first["comparison"]["status"], "no_baseline")
        second_dataset = self.import_and_analyze(
            TABLE.replace(",24,ug", ",48,ug").replace(",30,ug", ",60,ug")
        )
        second = self.create_brief(second_dataset, language="hi")
        self.assertEqual(second["previous_brief_id"], first["id"])
        self.assertEqual(second["comparison"]["changes"][0]["delta"], 27)
        pack = self.client.get(f"/api/briefs/{first['id']}/export")
        self.assertEqual(pack.status_code, 200)
        self.assertEqual(pack.json()["source_rows"][0]["value"], 24)
        self.assertEqual(pack.json()["source_sha256"], dataset["sha256"])
        rows = self.client.get(f"/api/briefs/{first['id']}/rows?ids=R2").json()
        self.assertEqual(rows["rows"][0]["raw"]["value"], "24")
        self.assertEqual(len(self.client.get("/api/briefs").json()), 2)

    def test_csv_upload_endpoint(self):
        result = self.client.post(
            "/api/import", files={"file": ("readings.csv", TABLE, "text/csv")}
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["row_count"], 2)

    def test_other_browser_cannot_read_or_mutate_records(self):
        dataset = self.import_and_analyze()
        brief = self.create_brief(dataset)
        other = TestClient(app)
        for route in [
            f"/api/datasets/{dataset['id']}/rows",
            f"/api/datasets/{dataset['id']}/export",
            f"/api/briefs/{brief['id']}",
            f"/api/briefs/{brief['id']}/export",
            f"/api/briefs/{brief['id']}/rows?ids=R2",
        ]:
            self.assertEqual(other.get(route).status_code, 404)
        self.assertEqual(other.get("/api/briefs").json(), [])
        self.assertEqual(
            other.post(
                f"/api/datasets/{dataset['id']}/analyze",
                json={"mapping": dataset["mapping"], "options": {}},
            ).status_code,
            404,
        )
        other.close()

    def test_csrf_blocked_and_security_headers(self):
        result = self.client.post(
            "/api/paste", json={"text": TABLE}, headers={"Origin": "https://evil.example"}
        )
        self.assertEqual(result.status_code, 403)
        result = self.client.get("/")
        self.assertEqual(result.status_code, 200)
        self.assertIn("script-src 'self'", result.headers["content-security-policy"])
        self.assertEqual(result.headers["x-content-type-options"], "nosniff")
        self.assertNotIn("unsafe-inline", result.headers["content-security-policy"])
        cookies = self.client.get("/api/status").request.headers["cookie"]
        self.assertIn("airledger_session", cookies)

    def test_formula_injection_defused_in_export(self):
        dataset = self.import_and_analyze(TABLE.replace("TEST North", "=HYPERLINK(1)"))
        export = self.client.get(f"/api/datasets/{dataset['id']}/export")
        self.assertIn("'=HYPERLINK(1)", export.text)

    def test_xss_payload_stays_plain_data(self):
        dataset = self.import_and_analyze(TABLE.replace("TEST North", "<script>alert(1)</script>"))
        brief = self.create_brief(dataset)
        self.assertIn("<script>", brief["rendered"]["findings"][0]["text"])
        javascript = self.client.get("/static/app.js").text
        self.assertNotIn("innerHTML", javascript)
        self.assertNotIn("eval(", javascript)

    def test_failed_ai_does_not_save_fake_brief(self):
        dataset = self.import_and_analyze()
        result = self.client.post(
            "/api/briefs",
            json={
                "dataset_id": dataset["id"],
                "role": "ward",
                "language": "en",
                "reading_level": "simple",
                "use_ai": True,
            },
        )
        self.assertEqual(result.status_code, 502)
        self.assertEqual(self.client.get("/api/briefs").json(), [])

    def test_malformed_ai_mapping_rejected(self):
        dataset = self.import_and_analyze()
        with patch("app.main.generate_json", AsyncMock(return_value={"station": "imaginary"})):
            result = self.client.post(f"/api/datasets/{dataset['id']}/suggest-mapping")
        self.assertEqual(result.status_code, 502)

    def test_role_specific_baseline(self):
        dataset = self.import_and_analyze()
        self.create_brief(dataset, "ward")
        school = self.create_brief(dataset, "school")
        self.assertEqual(school["comparison"]["status"], "no_baseline")
        self.assertIn("school_check", school["plan"]["action_ids"])
        self.assertNotIn("ward_check", school["plan"]["action_ids"])

    def test_clear_and_pagination(self):
        dataset = self.import_and_analyze()
        self.create_brief(dataset)
        self.assertEqual(
            self.client.get(f"/api/datasets/{dataset['id']}/rows?offset=1000").json()["rows"], []
        )
        self.assertEqual(self.client.delete("/api/workspace").status_code, 200)
        self.assertEqual(self.client.get("/api/briefs").json(), [])
        self.assertEqual(self.client.get(f"/api/datasets/{dataset['id']}/rows").status_code, 404)

    def test_rate_limit(self):
        statuses = [
            self.client.post("/api/paste", json={"text": "invalid"}).status_code for _ in range(21)
        ]
        self.assertEqual(statuses[-1], 429)

    def test_request_limit_and_invalid_enums(self):
        response = self.client.post(
            "/api/paste", content=b"{}", headers={"Content-Length": str(7 * 1024 * 1024)}
        )
        self.assertEqual(response.status_code, 413)
        result = self.client.post(
            "/api/briefs",
            json={
                "dataset_id": "unknown",
                "role": "doctor",
                "language": "zz",
                "reading_level": "simple",
            },
        )
        self.assertEqual(result.status_code, 422)

    def test_static_assets_and_no_seeded_observations(self):
        for route in ["/", "/static/app.js", "/static/styles.css", "/static/mark.svg"]:
            self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(self.client.get("/api/briefs").json(), [])
        self.assertFalse(self.client.get("/api/status").json()["ai_configured"])
