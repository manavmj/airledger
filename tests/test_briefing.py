import os
import unittest
from unittest.mock import AsyncMock, patch

from app.briefing import GenerationError, generate_json, plan_brief, render_brief, validate_plan
from tests.test_analysis import analyzed


class BriefingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _, self.analysis = analyzed(
            "station,timestamp,pollutant,value,unit,duration_hours\nTEST,2026-11-01,PM2.5,24,ug/m3,24\nTEST,2026-11-02,PM2.5,30,ug/m3,24"
        )

    async def test_rules_mode_explicit_and_translations_preserve_evidence(self):
        plan, mode = await plan_brief(self.analysis, "school", False)
        self.assertEqual(mode, "rules")
        for language in ("en", "hi", "mr"):
            for level in ("simple", "standard"):
                brief = render_brief(plan, self.analysis, language, level)
                self.assertEqual(brief["findings"][0]["evidence"], ["R2", "R3"])
                self.assertIn("27", brief["findings"][0]["text"])
                self.assertTrue(brief["care"])
                self.assertTrue(brief["review"])

    async def test_missing_ai_key_does_not_fake_ai(self):
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": ""}),
            self.assertRaisesRegex(GenerationError, "not configured"),
        ):
            await plan_brief(self.analysis, "ward", True)

    async def test_valid_ai_plan_and_untrusted_raw_cells_never_sent(self):
        provider = AsyncMock(
            return_value={"fact_ids": ["F1"], "action_ids": ["school_check", "verify"]}
        )
        with patch("app.briefing.generate_json", provider):
            plan, mode = await plan_brief(self.analysis, "school", True)
        self.assertEqual(mode, "gemini")
        self.assertEqual(plan["action_ids"][0], "verify")
        payload = provider.call_args.args[1]
        self.assertNotIn("raw", str(payload))
        self.assertNotIn("evidence", payload["facts"][0])

    async def test_hallucinated_ids_extra_prose_and_wrong_role_rejected(self):
        invalid_plans = [
            {"fact_ids": ["F999"], "action_ids": ["verify"]},
            {"fact_ids": ["F1"], "action_ids": ["school_gate"]},
            {"fact_ids": ["F1", "F1"], "action_ids": ["verify"]},
            {"fact_ids": ["F1"], "action_ids": ["verify"], "invented_text": "Safe air"},
            {"fact_ids": [], "action_ids": ["verify"]},
            {"fact_ids": [42], "action_ids": ["verify"]},
        ]
        for plan in invalid_plans:
            with self.subTest(plan=plan), self.assertRaises(GenerationError):
                validate_plan(plan, self.analysis, "ward")

    async def test_no_valid_readings_blocks_generation(self):
        with self.assertRaisesRegex(ValueError, "No valid evidence"):
            await plan_brief({"facts": []}, "ward", False)

    async def test_http_provider_error_sanitized(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("sensitive internal detail")
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "TEST-NOT-A-REAL-KEY"}),
            patch("app.briefing.httpx.AsyncClient") as client,
        ):
            client.return_value.__aenter__.return_value = mock_client
            with self.assertRaisesRegex(GenerationError, "usable response") as raised:
                await generate_json("test", {}, {})
            self.assertNotIn("sensitive", str(raised.exception))
