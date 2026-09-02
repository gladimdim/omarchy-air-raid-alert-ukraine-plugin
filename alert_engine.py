#!/usr/bin/env python3
"""
Air Raid Alert Engine for Omarchy Linux.
Fetches Ukraine air raid alert data across multiple providers (Ubilling, alerts.in.ua, api.ukrainealarm.com),
normalizes region data, manages persistent user configuration, and dispatches desktop/audio notifications.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# All recognized administrative regions of Ukraine (24 oblasts + 2 cities with special status + Crimea)
CANONICAL_REGIONS: List[Dict[str, str]] = [
    {"name": "м. Київ", "nameEn": "Kyiv City", "code": "kyiv-city"},
    {"name": "Київська область", "nameEn": "Kyiv Oblast", "code": "kyiv-obl"},
    {"name": "Вінницька область", "nameEn": "Vinnytsia Oblast", "code": "vinnytsia"},
    {"name": "Волинська область", "nameEn": "Volyn Oblast", "code": "volyn"},
    {"name": "Дніпропетровська область", "nameEn": "Dnipropetrovsk Oblast", "code": "dnipro"},
    {"name": "Донецька область", "nameEn": "Donetsk Oblast", "code": "donetsk"},
    {"name": "Житомирська область", "nameEn": "Zhytomyr Oblast", "code": "zhytomyr"},
    {"name": "Закарпатська область", "nameEn": "Zakarpattia Oblast", "code": "zakarpattia"},
    {"name": "Запорізька область", "nameEn": "Zaporizhzhia Oblast", "code": "zaporizhzhia"},
    {"name": "Івано-Франківська область", "nameEn": "Ivano-Frankivsk Oblast", "code": "ivano-frankivsk"},
    {"name": "Кіровоградська область", "nameEn": "Kirovohrad Oblast", "code": "kirovohrad"},
    {"name": "Луганська область", "nameEn": "Luhansk Oblast", "code": "luhansk"},
    {"name": "Львівська область", "nameEn": "Lviv Oblast", "code": "lviv"},
    {"name": "Миколаївська область", "nameEn": "Mykolaiv Oblast", "code": "mykolaiv"},
    {"name": "Одеська область", "nameEn": "Odesa Oblast", "code": "odesa"},
    {"name": "Полтавська область", "nameEn": "Poltava Oblast", "code": "poltava"},
    {"name": "Рівненська область", "nameEn": "Rivne Oblast", "code": "rivne"},
    {"name": "Сумська область", "nameEn": "Sumy Oblast", "code": "sumy"},
    {"name": "Тернопільська область", "nameEn": "Ternopil Oblast", "code": "ternopil"},
    {"name": "Харківська область", "nameEn": "Kharkiv Oblast", "code": "kharkiv"},
    {"name": "Херсонська область", "nameEn": "Kherson Oblast", "code": "kherson"},
    {"name": "Хмельницька область", "nameEn": "Khmelnytskyi Oblast", "code": "khmelnytskyi"},
    {"name": "Черкаська область", "nameEn": "Cherkasy Oblast", "code": "cherkasy"},
    {"name": "Чернівецька область", "nameEn": "Chernivtsi Oblast", "code": "chernivtsi"},
    {"name": "Чернігівська область", "nameEn": "Chernihiv Oblast", "code": "chernihiv"},
    {"name": "АР Крим", "nameEn": "Crimea", "code": "crimea"},
    {"name": "м. Севастополь", "nameEn": "Sevastopol City", "code": "sevastopol"}
]

REGION_NAME_MAP: Dict[str, str] = {
    # Variations -> Canonical Ukrainian Name
    "м. київ": "м. Київ",
    "м.київ": "м. Київ",
    "київ": "м. Київ",
    "місто київ": "м. Київ",
    "kyiv": "м. Київ",
    "kyiv city": "м. Київ",
    "київська область": "Київська область",
    "київська": "Київська область",
    "kyiv oblast": "Київська область",
    "вінницька область": "Вінницька область",
    "вінницька": "Вінницька область",
    "волинська область": "Волинська область",
    "волинська": "Волинська область",
    "дніпропетровська область": "Дніпропетровська область",
    "дніпропетровська": "Дніпропетровська область",
    "дніпро": "Дніпропетровська область",
    "донецька область": "Донецька область",
    "донецька": "Донецька область",
    "житомирська область": "Житомирська область",
    "житомирська": "Житомирська область",
    "закарпатська область": "Закарпатська область",
    "закарпатська": "Закарпатська область",
    "запорізька область": "Запорізька область",
    "запорізька": "Запорізька область",
    "івано-франківська область": "Івано-Франківська область",
    "івано-франківська": "Івано-Франківська область",
    "кіровоградська область": "Кіровоградська область",
    "кіровоградська": "Кіровоградська область",
    "луганська область": "Луганська область",
    "луганська": "Луганська область",
    "львівська область": "Львівська область",
    "львівська": "Львівська область",
    "миколаївська область": "Миколаївська область",
    "миколаївська": "Миколаївська область",
    "одеська область": "Одеська область",
    "одеська": "Одеська область",
    "полтавська область": "Полтавська область",
    "полтавська": "Полтавська область",
    "рівненська область": "Рівненська область",
    "рівненська": "Рівненська область",
    "сумська область": "Сумська область",
    "сумська": "Сумська область",
    "тернопільська область": "Тернопільська область",
    "тернопільська": "Тернопільська область",
    "харківська область": "Харківська область",
    "харківська": "Харківська область",
    "херсонська область": "Херсонська область",
    "херсонська": "Херсонська область",
    "хмельницька область": "Хмельницька область",
    "хмельницька": "Хмельницька область",
    "черкаська область": "Черкаська область",
    "черкаська": "Черкаська область",
    "чернівецька область": "Чернівецька область",
    "чернівецька": "Чернівецька область",
    "чернігівська область": "Чернігівська область",
    "чернігівська": "Чернігівська область",
    "ар крим": "АР Крим",
    "крим": "АР Крим",
    "севастополь": "м. Севастополь",
    "м. севастополь": "м. Севастополь"
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "selectedOblast": "м. Київ",
    "provider": "ubilling",  # ubilling | alerts_in_ua | ukraine_alarm
    "apiKey": "",
    "notificationsEnabled": True,
    "soundEnabled": True,
    "refreshIntervalSec": 20,
    "fallbackToUbilling": True,
    "lastKnownAlert": False,
    "lastKnownAlertTime": "",
    "showOblastInBar": True
}

def get_default_config_path() -> Path:
    """Returns ~/.config/omarchy/air-raid-alert.json."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    return base / "omarchy" / "air-raid-alert.json"

def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads JSON configuration, populating defaults if missing."""
    target = path or get_default_config_path()
    cfg = dict(DEFAULT_CONFIG)
    if target.exists():
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception as e:
            print(f"Warning: Failed to load config from {target}: {e}", file=sys.stderr)
    return cfg

def save_config(cfg: Dict[str, Any], path: Optional[Path] = None) -> None:
    """Saves JSON configuration."""
    target = path or get_default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def normalize_region_name(raw_name: str) -> str:
    """Normalizes raw location string to canonical Ukrainian region name."""
    s = raw_name.strip().lower()
    if s in REGION_NAME_MAP:
        return REGION_NAME_MAP[s]
    # Check prefixes/substrings
    for key, canonical in REGION_NAME_MAP.items():
        if key in s or s in key:
            return canonical
    return raw_name.strip()

# ==========================================
# PROVIDER IMPLEMENTATIONS
# ==========================================

def fetch_ubilling(timeout: float = 6.0) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Fetches air raid status from Ubilling / Mørk Skogen API.
    Zero-config, no API key required.
    """
    url = "https://ubilling.net.ua/aerialalerts/"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "omarchy-air-raid-alert-plugin/1.0",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)

    states_raw = data.get("states", {})
    source_name = data.get("source", "Ubilling / Mørk Skogen API")
    results: Dict[str, Dict[str, Any]] = {}

    for raw_name, info in states_raw.items():
        canonical = normalize_region_name(raw_name)
        is_alert = bool(info.get("alertnow", False))
        changed = str(info.get("changed", ""))
        results[canonical] = {
            "alert": is_alert,
            "changed": changed
        }
    return results, source_name

def fetch_alerts_in_ua(token: str, timeout: float = 6.0) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Fetches air raid alerts from alerts.in.ua API.
    Requires Bearer token from https://devs.alerts.in.ua.
    """
    if not token or not token.strip():
        raise ValueError("API token is empty. Please obtain a token at https://devs.alerts.in.ua")

    url = "https://api.alerts.in.ua/v1/alerts/active.json"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "User-Agent": "omarchy-air-raid-alert-plugin/1.0",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)

    # Initialize all canonical regions as False
    results: Dict[str, Dict[str, Any]] = {
        r["name"]: {"alert": False, "changed": ""} for r in CANONICAL_REGIONS
    }

    # alerts list can be array or dict
    alerts_raw = data.get("alerts", [])
    if isinstance(alerts_raw, dict):
        alerts_list = list(alerts_raw.values())
    elif isinstance(alerts_raw, list):
        alerts_list = alerts_raw
    else:
        alerts_list = []

    for item in alerts_list:
        if not isinstance(item, dict):
            continue
        # Check alert type (air_raid, artillery, etc.)
        alert_type = item.get("alert_type") or item.get("type", "air_raid")
        # Title can be in location_title or location_oblast or region_title
        loc_title = item.get("location_title") or item.get("location_oblast") or item.get("region_title") or ""
        started = item.get("started_at") or item.get("last_update") or ""
        canonical = normalize_region_name(loc_title)
        if canonical:
            results[canonical] = {
                "alert": True,
                "changed": started,
                "type": alert_type
            }

    return results, "Alerts.in.ua API"

def fetch_ukraine_alarm(api_key: str, timeout: float = 6.0) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Fetches air raid alerts from api.ukrainealarm.com (Stfalcon/Ajax Systems).
    Requires API key from https://api.ukrainealarm.com.
    """
    if not api_key or not api_key.strip():
        raise ValueError("API key is empty. Please obtain access at https://api.ukrainealarm.com")

    url = "https://api.ukrainealarm.com/api/v3/alerts"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": api_key.strip(),
            "User-Agent": "Mozilla/5.0 (compatible; OmarchyAirAlert/1.0)",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)

    results: Dict[str, Dict[str, Any]] = {
        r["name"]: {"alert": False, "changed": ""} for r in CANONICAL_REGIONS
    }

    # data is usually a list of regions: [{"regionId": "...", "regionName": "...", "activeAlerts": [...]}]
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("regionName", "")
            canonical = normalize_region_name(name)
            active_alerts = item.get("activeAlerts", [])
            has_alert = len(active_alerts) > 0
            changed = ""
            if has_alert and isinstance(active_alerts[0], dict):
                changed = active_alerts[0].get("lastUpdate") or active_alerts[0].get("startedAt", "")
            if canonical:
                results[canonical] = {
                    "alert": has_alert,
                    "changed": changed
                }

    return results, "UkraineAlarm (api.ukrainealarm.com)"

# ==========================================
# HIGH-LEVEL DATA AGGREGATION
# ==========================================

def get_alerts_data(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches request according to configured provider with fallback.
    Returns structured summary for UI consumption.
    """
    provider = config.get("provider", "ubilling")
    api_key = config.get("apiKey", "")
    selected_oblast = config.get("selectedOblast", "м. Київ")
    fallback_enabled = config.get("fallbackToUbilling", True)

    results_map: Dict[str, Dict[str, Any]] = {}
    source_title = ""
    error_message: Optional[str] = None
    fallback_used = False

    try:
        if provider == "alerts_in_ua":
            results_map, source_title = fetch_alerts_in_ua(api_key)
        elif provider == "ukraine_alarm":
            results_map, source_title = fetch_ukraine_alarm(api_key)
        else:
            # Default: ubilling
            results_map, source_title = fetch_ubilling()
    except Exception as e:
        error_message = str(e)
        if fallback_enabled and provider != "ubilling":
            try:
                results_map, fallback_source = fetch_ubilling()
                source_title = f"{fallback_source} (Резервний канал)"
                fallback_used = True
            except Exception as fb_err:
                error_message = f"Primary ({provider}) failed: {e}. Fallback failed: {fb_err}"
        else:
            error_message = f"Error fetching from {provider}: {e}"

    # Build canonical regions list
    active_count = 0
    regions_list: List[Dict[str, Any]] = []

    for reg in CANONICAL_REGIONS:
        name = reg["name"]
        info = results_map.get(name, {"alert": False, "changed": ""})
        is_alert = bool(info.get("alert", False))
        if is_alert:
            active_count += 1
        regions_list.append({
            "name": name,
            "nameEn": reg["nameEn"],
            "code": reg["code"],
            "alert": is_alert,
            "changed": info.get("changed", "")
        })

    # Find status of user's selected oblast
    canonical_selected = normalize_region_name(selected_oblast)
    selected_info = results_map.get(canonical_selected, {"alert": False, "changed": ""})
    selected_alert = bool(selected_info.get("alert", False))
    selected_changed = str(selected_info.get("changed", ""))

    return {
        "status": "ok" if (results_map or not error_message) else "error",
        "provider": provider,
        "sourceName": source_title or provider,
        "timestamp": datetime.now().isoformat(),
        "selectedOblast": canonical_selected,
        "alertActive": selected_alert,
        "alertChanged": selected_changed,
        "activeCount": active_count,
        "totalCount": len(CANONICAL_REGIONS),
        "fallbackUsed": fallback_used,
        "errorMessage": error_message,
        "notificationsEnabled": bool(config.get("notificationsEnabled", True)),
        "soundEnabled": bool(config.get("soundEnabled", True)),
        "refreshIntervalSec": int(config.get("refreshIntervalSec", 20)),
        "regions": regions_list
    }

# ==========================================
# NOTIFICATIONS & AUDIO DISPATCH
# ==========================================

def dispatch_notification(headline: str, description: str, urgency: str = "critical", glyph: str = "󰞏") -> None:
    """Dispatches a desktop notification via omarchy-notification-send."""
    cmd = [
        "omarchy-notification-send",
        "-g", glyph,
        "-u", urgency,
        "-t", "15000",
        headline,
        description
    ]
    try:
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        # Fallback to standard notify-send if running outside full Omarchy shell
        notify_cmd = ["notify-send", "-u", urgency, headline, description]
        try:
            subprocess.run(notify_cmd, check=False)
        except Exception:
            pass

def play_audio(sound_file: str) -> None:
    """Plays audio via pw-play or paplay."""
    plugin_dir = Path(__file__).resolve().parent
    sound_path = plugin_dir / "assets" / sound_file
    if not sound_path.exists():
        return

    # Try pw-play first (PipeWire native), fallback to paplay / aplay
    for player in [["pw-play", "--volume=0.85"], ["paplay"], ["aplay", "-q"]]:
        cmd = player + [str(sound_path)]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            break
        except FileNotFoundError:
            continue

def trigger_test_notification() -> Dict[str, str]:
    """Fires a test air raid notification and siren audio."""
    dispatch_notification(
        headline="ТЕСТОВЕ СПОВІЩЕННЯ: Повітряна тривога!",
        description="Перевірка роботи сповіщень та звуку плагіна Omarchy Air Raid Alert.",
        urgency="critical",
        glyph="󰚌"
    )
    play_audio("siren.wav")
    return {"status": "ok", "message": "Test notification dispatched"}

# ==========================================
# CLI ENTRY POINT
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Omarchy Air Raid Alert Engine for Ukraine")
    parser.add_argument("--fetch", action="store_true", help="Fetch alerts and output JSON for UI")
    parser.add_argument("--config-path", type=str, help="Path to config file")
    parser.add_argument("--load-config", action="store_true", help="Print current configuration JSON")
    parser.add_argument("--set-oblast", type=str, help="Set selected oblast")
    parser.add_argument("--set-provider", type=str, choices=["ubilling", "alerts_in_ua", "ukraine_alarm"], help="Set API provider")
    parser.add_argument("--set-api-key", type=str, help="Set API key / token")
    parser.add_argument("--set-notifications", type=str, choices=["true", "false"], help="Toggle notifications")
    parser.add_argument("--set-sound", type=str, choices=["true", "false"], help="Toggle sound")
    parser.add_argument("--set-interval", type=int, help="Set refresh interval (seconds)")
    parser.add_argument("--list-regions", action="store_true", help="List all canonical regions")
    parser.add_argument("--test-notification", action="store_true", help="Fire test notification and sound")
    parser.add_argument("--play-siren", action="store_true", help="Play alarm sound")
    parser.add_argument("--play-clear", action="store_true", help="Play all-clear sound")

    args = parser.parse_args()
    config_path = Path(args.config_path) if args.config_path else get_default_config_path()
    cfg = load_config(config_path)

    # Modifications to config
    config_changed = False
    if args.set_oblast:
        cfg["selectedOblast"] = normalize_region_name(args.set_oblast)
        config_changed = True
    if args.set_provider:
        cfg["provider"] = args.set_provider
        config_changed = True
    if args.set_api_key is not None:
        cfg["apiKey"] = args.set_api_key
        config_changed = True
    if args.set_notifications:
        cfg["notificationsEnabled"] = args.set_notifications.lower() == "true"
        config_changed = True
    if args.set_sound:
        cfg["soundEnabled"] = args.set_sound.lower() == "true"
        config_changed = True
    if args.set_interval:
        cfg["refreshIntervalSec"] = max(5, args.set_interval)
        config_changed = True

    if config_changed:
        save_config(cfg, config_path)

    # Actions
    if args.list_regions:
        print(json.dumps(CANONICAL_REGIONS, ensure_ascii=False, indent=2))
        return

    if args.load_config:
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return

    if args.test_notification:
        res = trigger_test_notification()
        print(json.dumps(res, ensure_ascii=False))
        return

    if args.play_siren:
        play_audio("siren.wav")
        print(json.dumps({"status": "ok", "played": "siren.wav"}))
        return

    if args.play_clear:
        play_audio("clear.wav")
        print(json.dumps({"status": "ok", "played": "clear.wav"}))
        return

    # Default action: Fetch
    data = get_alerts_data(cfg)
    print(json.dumps(data, ensure_ascii=False))

if __name__ == "__main__":
    main()
