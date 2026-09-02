#!/usr/bin/env python3
"""Unit tests for Omarchy Air Raid Alert Engine."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import alert_engine

class TestAlertEngine(unittest.TestCase):
    def test_region_normalization(self):
        self.assertEqual(alert_engine.normalize_region_name("м. Київ"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("м.київ"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("київ"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("Kyiv City"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("Київська область"), "Київська область")
        self.assertEqual(alert_engine.normalize_region_name("львівська"), "Львівська область")
        self.assertEqual(alert_engine.normalize_region_name("Одеська область"), "Одеська область")

    def test_canonical_regions_count(self):
        # Must contain at least 25 administrative regions (24 oblasts + Kyiv city)
        self.assertGreaterEqual(len(alert_engine.CANONICAL_REGIONS), 25)
        names = [r["name"] for r in alert_engine.CANONICAL_REGIONS]
        self.assertIn("м. Київ", names)
        self.assertIn("Київська область", names)
        self.assertIn("Львівська область", names)
        self.assertIn("Харківська область", names)
        self.assertIn("Одеська область", names)
        self.assertIn("Дніпропетровська область", names)

    def test_load_save_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "test_config.json"
            cfg = alert_engine.load_config(tmp_path)
            self.assertEqual(cfg["provider"], "ubilling")

            cfg["selectedOblast"] = "Одеська область"
            cfg["refreshIntervalSec"] = 45
            alert_engine.save_config(cfg, tmp_path)

            loaded = alert_engine.load_config(tmp_path)
            self.assertEqual(loaded["selectedOblast"], "Одеська область")
            self.assertEqual(loaded["refreshIntervalSec"], 45)

    @patch("urllib.request.urlopen")
    def test_fetch_ubilling_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "source": "Mocked Ubilling",
            "cachedat": "2026-09-02 21:00:00",
            "states": {
                "Київська область": {"alertnow": True, "changed": "2026-09-02 20:00:00"},
                "Львівська область": {"alertnow": False, "changed": "1970-01-01 03:00:00"}
            }
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        results, source = alert_engine.fetch_ubilling()
        self.assertEqual(source, "Mocked Ubilling")
        self.assertTrue(results["Київська область"]["alert"])
        self.assertFalse(results["Львівська область"]["alert"])

    @patch("urllib.request.urlopen")
    def test_fetch_alerts_in_ua_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "alerts": [
                {
                    "location_title": "м. Київ",
                    "alert_type": "air_raid",
                    "started_at": "2026-09-02T21:15:00Z"
                }
            ]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        results, source = alert_engine.fetch_alerts_in_ua(token="valid_token_123")
        self.assertEqual(source, "Alerts.in.ua API")
        self.assertTrue(results["м. Київ"]["alert"])
        self.assertFalse(results["Львівська область"]["alert"])

    def test_fetch_alerts_in_ua_empty_token(self):
        with self.assertRaises(ValueError):
            alert_engine.fetch_alerts_in_ua(token="")

    @patch("urllib.request.urlopen")
    def test_fetch_ukraine_alarm_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([
            {
                "regionName": "Харківська область",
                "activeAlerts": [{"type": "AIR", "startedAt": "2026-09-02T21:00:00Z"}]
            },
            {
                "regionName": "Львівська область",
                "activeAlerts": []
            }
        ]).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        results, source = alert_engine.fetch_ukraine_alarm(api_key="valid_key_123")
        self.assertIn("UkraineAlarm", source)
        self.assertTrue(results["Харківська область"]["alert"])
        self.assertFalse(results["Львівська область"]["alert"])

    def test_fetch_ukraine_alarm_empty_key(self):
        with self.assertRaises(ValueError):
            alert_engine.fetch_ukraine_alarm(api_key="")

    @patch("alert_engine.fetch_alerts_in_ua")
    @patch("alert_engine.fetch_ubilling")
    def test_fallback_behavior(self, mock_ubilling, mock_alerts_in_ua):
        mock_alerts_in_ua.side_effect = Exception("API rate limit exceeded")
        mock_ubilling.return_value = (
            {"м. Київ": {"alert": True, "changed": "2026-09-02 21:20:00"}},
            "Ubilling Fallback"
        )

        cfg = {
            "provider": "alerts_in_ua",
            "apiKey": "expired_token",
            "selectedOblast": "м. Київ",
            "fallbackToUbilling": True
        }
        res = alert_engine.get_alerts_data(cfg)
        self.assertTrue(res["fallbackUsed"])
        self.assertTrue(res["alertActive"])
        self.assertIn("Резервний канал", res["sourceName"])

if __name__ == "__main__":
    unittest.main()
