#!/usr/bin/env python3
"""Unit tests for Omarchy Air Raid Alert Engine."""

import io
import json
import os
import stat
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import alert_engine


def _mock_response(payload, content_type="application/json", content_length=None, raw=None):
    body = raw if raw is not None else json.dumps(payload).encode("utf-8")
    resp = MagicMock()
    resp.read.side_effect = lambda n=None: body if n is None else body[:n]
    resp.geturl.return_value = alert_engine.UBILLING_URL
    resp.headers.get_content_type.return_value = content_type
    resp.headers.get.side_effect = lambda k, d=None: (
        content_length if k == "Content-Length" else d
    )
    resp.__enter__.return_value = resp
    return resp


class TestRegions(unittest.TestCase):
    def test_region_normalization(self):
        self.assertEqual(alert_engine.normalize_region_name("м. Київ"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("м.київ"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("київ"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("Kyiv City"), "м. Київ")
        self.assertEqual(alert_engine.normalize_region_name("Київська область"), "Київська область")
        self.assertEqual(alert_engine.normalize_region_name("львівська"), "Львівська область")
        self.assertEqual(alert_engine.normalize_region_name("Одеська область"), "Одеська область")

    def test_normalization_is_length_bounded(self):
        hostile = "щ" * 10000
        self.assertLessEqual(len(alert_engine.normalize_region_name(hostile)), alert_engine.MAX_TEXT_LEN)
        self.assertEqual(alert_engine.normalize_region_name(None), "")

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


class TestConfig(unittest.TestCase):
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

    def test_config_file_is_owner_only_and_atomic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "perm_config.json"
            alert_engine.save_config(dict(alert_engine.DEFAULT_CONFIG), tmp_path)
            mode = stat.S_IMODE(os.stat(tmp_path).st_mode)
            self.assertEqual(mode, 0o600)
            # No temporary leftovers beside the published file.
            self.assertEqual([p.name for p in Path(tmpdir).iterdir()], ["perm_config.json"])

    def test_unknown_and_legacy_fields_are_dropped_and_purged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "legacy_config.json"
            tmp_path.write_text(json.dumps({
                "selectedOblast": "Львівська область",
                "apiKey": "super-secret-token",
                "provider": "alerts_in_ua",
                "somethingElse": {"nested": True}
            }), encoding="utf-8")

            cfg = alert_engine.load_config(tmp_path)
            self.assertNotIn("apiKey", cfg)
            self.assertNotIn("somethingElse", cfg)
            self.assertEqual(cfg["provider"], "ubilling")
            self.assertEqual(cfg["selectedOblast"], "Львівська область")

            # The token is erased from disk, not merely hidden from the caller.
            on_disk = tmp_path.read_text(encoding="utf-8")
            self.assertNotIn("super-secret-token", on_disk)
            self.assertNotIn("apiKey", json.loads(on_disk))

    def test_symlinked_config_is_refused(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            real = Path(tmpdir) / "real.json"
            real.write_text(json.dumps({"selectedOblast": "Одеська область"}), encoding="utf-8")
            link = Path(tmpdir) / "link.json"
            link.symlink_to(real)

            cfg = alert_engine.load_config(link)
            self.assertEqual(cfg["selectedOblast"], alert_engine.DEFAULT_CONFIG["selectedOblast"])

    def test_oversized_config_is_refused(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            big = Path(tmpdir) / "big.json"
            big.write_text(json.dumps({
                "selectedOblast": "Одеська область",
                "pad": "x" * (alert_engine.MAX_CONFIG_BYTES + 10)
            }), encoding="utf-8")

            cfg = alert_engine.load_config(big)
            self.assertEqual(cfg["selectedOblast"], alert_engine.DEFAULT_CONFIG["selectedOblast"])

    def test_interval_is_clamped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "interval.json"
            tmp_path.write_text(json.dumps({"refreshIntervalSec": 10 ** 9}), encoding="utf-8")
            self.assertEqual(
                alert_engine.load_config(tmp_path)["refreshIntervalSec"],
                alert_engine.MAX_INTERVAL_SEC
            )


class TestFetch(unittest.TestCase):
    @patch.object(alert_engine._OPENER, "open")
    def test_fetch_ubilling_success(self, mock_open):
        mock_open.return_value = _mock_response({
            "source": "Mocked Ubilling",
            "cachedat": "2026-09-02 21:00:00",
            "states": {
                "Київська область": {"alertnow": True, "changed": "2026-09-02 20:00:00"},
                "Львівська область": {"alertnow": False, "changed": "1970-01-01 03:00:00"}
            }
        })

        results, source = alert_engine.fetch_ubilling()
        self.assertEqual(source, "Mocked Ubilling")
        self.assertTrue(results["Київська область"]["alert"])
        self.assertFalse(results["Львівська область"]["alert"])
        # Only the fixed 27 regions are ever produced.
        self.assertEqual(len(results), len(alert_engine.CANONICAL_REGIONS))

    @patch.object(alert_engine._OPENER, "open")
    def test_unknown_remote_regions_cannot_grow_the_result(self, mock_open):
        mock_open.return_value = _mock_response({
            "source": "Mocked Ubilling",
            "states": {"Atlantis": {"alertnow": True}, "": {"alertnow": True}}
        })
        results, _ = alert_engine.fetch_ubilling()
        self.assertEqual(len(results), len(alert_engine.CANONICAL_REGIONS))
        self.assertNotIn("Atlantis", results)

    @patch.object(alert_engine._OPENER, "open")
    def test_oversized_body_is_refused(self, mock_open):
        payload = b'{"states": {}, "pad": "' + b"x" * (alert_engine.MAX_RESPONSE_BYTES + 1024) + b'"}'
        mock_open.return_value = _mock_response(None, raw=payload)
        with self.assertRaises(ValueError):
            alert_engine.fetch_ubilling()

    @patch.object(alert_engine._OPENER, "open")
    def test_declared_oversize_is_refused_before_reading(self, mock_open):
        mock_open.return_value = _mock_response(
            {"states": {}},
            content_length=str(alert_engine.MAX_RESPONSE_BYTES + 1)
        )
        with self.assertRaises(ValueError):
            alert_engine.fetch_ubilling()

    @patch.object(alert_engine._OPENER, "open")
    def test_non_json_content_type_is_refused(self, mock_open):
        mock_open.return_value = _mock_response({"states": {}}, content_type="text/html")
        with self.assertRaises(ValueError):
            alert_engine.fetch_ubilling()

    @patch.object(alert_engine._OPENER, "open")
    def test_offorigin_final_url_is_refused(self, mock_open):
        resp = _mock_response({"states": {}})
        resp.geturl.return_value = "https://evil.example.com/aerialalerts/"
        mock_open.return_value = resp
        with self.assertRaises(ValueError):
            alert_engine.fetch_ubilling()

    @patch.object(alert_engine._OPENER, "open")
    def test_too_many_states_is_refused(self, mock_open):
        mock_open.return_value = _mock_response({
            "states": {f"region-{i}": {"alertnow": False} for i in range(alert_engine.MAX_STATES + 1)}
        })
        with self.assertRaises(ValueError):
            alert_engine.fetch_ubilling()

    def test_redirects_are_refused(self):
        handler = alert_engine._RefuseRedirects()
        req = MagicMock()
        req.full_url = alert_engine.UBILLING_URL
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "https://evil.example.com/")

    def test_non_pinned_url_is_refused(self):
        with self.assertRaises(ValueError):
            alert_engine._fetch_json("http://ubilling.net.ua/aerialalerts/", timeout=1)
        with self.assertRaises(ValueError):
            alert_engine._fetch_json("https://ubilling.net.ua.evil.example/", timeout=1)


class TestAggregation(unittest.TestCase):
    @patch("alert_engine.fetch_ubilling")
    def test_error_is_surfaced_without_crashing(self, mock_ubilling):
        mock_ubilling.side_effect = Exception("network down")
        res = alert_engine.get_alerts_data({"selectedOblast": "м. Київ"})
        self.assertEqual(res["status"], "error")
        self.assertFalse(res["alertActive"])
        self.assertEqual(len(res["regions"]), len(alert_engine.CANONICAL_REGIONS))
        self.assertIn("network down", res["errorMessage"])

    @patch("alert_engine.fetch_ubilling")
    def test_selected_region_alert(self, mock_ubilling):
        mock_ubilling.return_value = (
            {"м. Київ": {"alert": True, "changed": "2026-09-02 21:20:00"}},
            "Ubilling"
        )
        res = alert_engine.get_alerts_data({"selectedOblast": "київ"})
        self.assertTrue(res["alertActive"])
        self.assertEqual(res["selectedOblast"], "м. Київ")
        self.assertEqual(res["activeCount"], 1)
        self.assertIsNone(res["errorMessage"])


if __name__ == "__main__":
    unittest.main()
