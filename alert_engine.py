#!/usr/bin/env python3
"""
Air Raid Alert Engine for Omarchy Linux.

Fetches Ukraine air raid alert data from the free, account-less Ubilling /
Mørk Skogen endpoint, normalizes region data, manages persistent user
configuration, and dispatches desktop/audio notifications.

Security boundaries enforced here:
  * No credentials of any kind are accepted, stored, transmitted or logged.
  * The only outbound request is a plain HTTPS GET to a single pinned origin,
    with redirects refused outright.
  * Remote bodies are read under a fixed byte budget and validated against a
    bounded schema before anything is projected onto the fixed 27 regions.
  * Configuration is read and written through descriptor-relative, no-follow,
    owner-verified access and published atomically with 0600 permissions.
"""

import argparse
import errno
import json
import os
import stat
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
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

CANONICAL_NAMES: frozenset = frozenset(r["name"] for r in CANONICAL_REGIONS)

# ==========================================
# CONFIGURATION (no secrets are ever stored)
# ==========================================

# The complete, closed set of persisted settings. Anything else found on disk
# is dropped on load and purged from the file, so a legacy `apiKey` left over
# from an older version can never be read back, printed or handed to the UI.
DEFAULT_CONFIG: Dict[str, Any] = {
    "selectedOblast": "м. Київ",
    "provider": "ubilling",
    "notificationsEnabled": True,
    "soundEnabled": True,
    "refreshIntervalSec": 20,
    "lastKnownAlert": False,
    "lastKnownAlertTime": "",
    "showOblastInBar": True
}

MIN_INTERVAL_SEC = 5
MAX_INTERVAL_SEC = 3600
MAX_CONFIG_BYTES = 64 * 1024
MAX_TEXT_LEN = 128
CONFIG_FILE_MODE = 0o600
CONFIG_DIR_MODE = 0o700
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)

def _warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)

def _clean_text(value: Any, fallback: str = "", limit: int = MAX_TEXT_LEN) -> str:
    """Coerces a remotely supplied value to a bounded, control-character-free string."""
    if not isinstance(value, str):
        return fallback
    trimmed = value.strip()[:limit]
    cleaned = "".join(ch for ch in trimmed if unicodedata.category(ch)[0] != "C")
    return cleaned or fallback

def get_default_config_path() -> Path:
    """Returns ~/.config/omarchy/air-raid-alert.json."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    return base / "omarchy" / "air-raid-alert.json"

def _read_config_bytes(target: Path) -> Optional[bytes]:
    """
    Reads at most MAX_CONFIG_BYTES from `target` without following a final
    symlink, refusing anything that is not a regular file owned by this user.
    Returns None when there is nothing usable to read.
    """
    try:
        fd = os.open(str(target), os.O_RDONLY | os.O_NOFOLLOW | _O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.EMLINK):
            _warn(f"Refusing to read config through a symlink: {target}")
        elif e.errno != errno.ENOTDIR:
            _warn(f"Failed to open config {target}: {e}")
        return None

    try:
        with os.fdopen(fd, "rb") as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode):
                _warn(f"Refusing to read config that is not a regular file: {target}")
                return None
            if info.st_uid != os.getuid():
                _warn(f"Refusing to read config owned by another user: {target}")
                return None
            if info.st_size > MAX_CONFIG_BYTES:
                _warn(f"Refusing to read oversized config ({info.st_size} bytes): {target}")
                return None
            raw = f.read(MAX_CONFIG_BYTES + 1)
    except OSError as e:
        _warn(f"Failed to read config {target}: {e}")
        return None

    if len(raw) > MAX_CONFIG_BYTES:
        _warn(f"Refusing to parse oversized config: {target}")
        return None
    return raw

def _coerce_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Projects on-disk data onto the closed DEFAULT_CONFIG schema, by type."""
    cfg = dict(DEFAULT_CONFIG)
    for key, default in DEFAULT_CONFIG.items():
        if key not in data:
            continue
        value = data[key]
        if isinstance(default, bool):
            if isinstance(value, bool):
                cfg[key] = value
        elif isinstance(default, int):
            if isinstance(value, int) and not isinstance(value, bool):
                cfg[key] = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, value))
        elif isinstance(default, str):
            cleaned = _clean_text(value, default)
            cfg[key] = cleaned
    cfg["selectedOblast"] = normalize_region_name(cfg["selectedOblast"])
    if cfg["selectedOblast"] not in CANONICAL_NAMES:
        cfg["selectedOblast"] = DEFAULT_CONFIG["selectedOblast"]
    cfg["provider"] = "ubilling"
    return cfg

def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Loads configuration, filling in defaults. Only keys in DEFAULT_CONFIG are
    ever returned; any legacy field (including an `apiKey` written by an older
    release) is dropped and, best-effort, erased from disk.
    """
    target = path or get_default_config_path()
    raw = _read_config_bytes(target)
    if raw is None:
        return dict(DEFAULT_CONFIG)

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        _warn(f"Failed to parse config {target}: {e}")
        return dict(DEFAULT_CONFIG)

    if not isinstance(data, dict):
        _warn(f"Ignoring config {target}: expected a JSON object")
        return dict(DEFAULT_CONFIG)

    cfg = _coerce_config(data)
    if set(data) - set(DEFAULT_CONFIG):
        # Legacy fields present (e.g. a stored API token): rewrite the file
        # without them so the value stops living on disk.
        try:
            save_config(cfg, target)
        except OSError as e:
            _warn(f"Failed to purge legacy fields from {target}: {e}")
    return cfg

def _ensure_config_dir(directory: Path) -> None:
    """Creates the config directory 0700 when absent; verifies it when present."""
    try:
        info = os.lstat(str(directory))
    except FileNotFoundError:
        directory.mkdir(parents=True, exist_ok=True, mode=CONFIG_DIR_MODE)
        return
    if stat.S_ISLNK(info.st_mode):
        raise OSError(f"Refusing to use a symlinked config directory: {directory}")
    if not stat.S_ISDIR(info.st_mode):
        raise OSError(f"Config directory path is not a directory: {directory}")
    if info.st_uid != os.getuid():
        raise OSError(f"Refusing to use a config directory owned by another user: {directory}")

def save_config(cfg: Dict[str, Any], path: Optional[Path] = None) -> None:
    """
    Writes the whitelisted settings atomically: a fresh, exclusively created
    0600 regular file in the destination directory, fsynced and then renamed
    over the target, so no reader ever sees a partial file and no pre-planted
    symlink or foreign file is written through.
    """
    target = path or get_default_config_path()
    directory = target.parent
    _ensure_config_dir(directory)

    payload = json.dumps(
        {key: cfg.get(key, default) for key, default in DEFAULT_CONFIG.items()},
        ensure_ascii=False,
        indent=2
    ).encode("utf-8")

    tmp_path = directory / f".{target.name}.{os.getpid()}.{os.urandom(6).hex()}.tmp"
    fd = os.open(
        str(tmp_path),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | _O_CLOEXEC,
        CONFIG_FILE_MODE
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(str(tmp_path), CONFIG_FILE_MODE)
        os.replace(str(tmp_path), str(target))
    except BaseException:
        try:
            os.unlink(str(tmp_path))
        except OSError:
            pass
        raise

    try:
        dir_fd = os.open(str(directory), os.O_RDONLY | _O_CLOEXEC)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass

def normalize_region_name(raw_name: str) -> str:
    """Normalizes a raw location string to a canonical Ukrainian region name."""
    if not isinstance(raw_name, str):
        return ""
    s = raw_name.strip()[:MAX_TEXT_LEN].lower()
    if not s:
        return ""
    if s in REGION_NAME_MAP:
        return REGION_NAME_MAP[s]
    # Check prefixes/substrings
    for key, canonical in REGION_NAME_MAP.items():
        if key in s or s in key:
            return canonical
    return raw_name.strip()[:MAX_TEXT_LEN]

# ==========================================
# PROVIDER (single pinned, account-less origin)
# ==========================================

UBILLING_URL = "https://ubilling.net.ua/aerialalerts/"
UBILLING_HOST = "ubilling.net.ua"
UBILLING_SOURCE = "Ubilling / Mørk Skogen API"
USER_AGENT = "omarchy-air-raid-alert-plugin/1.1"
# The live payload is ~4 KB; 64 KiB is a generous ceiling that still bounds a
# hostile or compromised endpoint well below anything the shell would notice.
MAX_RESPONSE_BYTES = 64 * 1024
MAX_STATES = 256
JSON_CONTENT_TYPES = frozenset({"application/json", "text/json"})

class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect instead of silently re-issuing the request elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            req.full_url, code,
            f"Refusing redirect ({code}) away from the pinned alert origin",
            headers, fp
        )

_OPENER = urllib.request.build_opener(_RefuseRedirects)

def _assert_pinned(url: str, what: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != UBILLING_HOST:
        raise ValueError(f"{what} is not the pinned https://{UBILLING_HOST} origin")

def _fetch_json(url: str, timeout: float) -> Any:
    """
    Performs one credential-free HTTPS GET against the pinned origin, refusing
    redirects, non-JSON content types and bodies over MAX_RESPONSE_BYTES.
    """
    _assert_pinned(url, "Request URL")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        },
        method="GET"
    )
    with _OPENER.open(req, timeout=timeout) as resp:
        _assert_pinned(resp.geturl(), "Response URL")
        content_type = (resp.headers.get_content_type() or "").lower()
        if content_type not in JSON_CONTENT_TYPES and not content_type.endswith("+json"):
            raise ValueError(f"Unexpected content type from provider: {content_type or 'unset'}")
        declared = resp.headers.get("Content-Length")
        if declared is not None and declared.strip().isdigit() and int(declared) > MAX_RESPONSE_BYTES:
            raise ValueError(f"Provider declared {declared} bytes, over the {MAX_RESPONSE_BYTES} byte budget")
        # One sentinel byte past the budget tells us the stream was too long.
        body = resp.read(MAX_RESPONSE_BYTES + 1)

    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Provider response exceeds the {MAX_RESPONSE_BYTES} byte budget")
    return json.loads(body.decode("utf-8"))

def fetch_ubilling(timeout: float = 6.0) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """
    Fetches air raid status from the Ubilling / Mørk Skogen API.
    Zero-config: no account, no API key, no credentials on the wire.
    """
    data = _fetch_json(UBILLING_URL, timeout)
    if not isinstance(data, dict):
        raise ValueError("Provider payload is not a JSON object")

    states_raw = data.get("states")
    if not isinstance(states_raw, dict):
        raise ValueError("Provider payload has no 'states' object")
    if len(states_raw) > MAX_STATES:
        raise ValueError(f"Provider reported {len(states_raw)} regions, over the {MAX_STATES} cap")

    source_name = _clean_text(data.get("source"), UBILLING_SOURCE)

    # Start from the fixed 27 regions; remote keys can only ever update one of
    # these entries, never grow the result.
    results: Dict[str, Dict[str, Any]] = {
        r["name"]: {"alert": False, "changed": ""} for r in CANONICAL_REGIONS
    }
    for raw_name, info in states_raw.items():
        if not isinstance(raw_name, str) or not isinstance(info, dict):
            continue
        canonical = normalize_region_name(raw_name)
        if canonical not in results:
            continue
        results[canonical] = {
            "alert": bool(info.get("alertnow", False)),
            "changed": _clean_text(info.get("changed"), "")
        }
    return results, source_name

# ==========================================
# HIGH-LEVEL DATA AGGREGATION
# ==========================================

def get_alerts_data(config: Dict[str, Any]) -> Dict[str, Any]:
    """Fetches current alerts and returns a structured summary for UI consumption."""
    selected_oblast = config.get("selectedOblast", DEFAULT_CONFIG["selectedOblast"])

    results_map: Dict[str, Dict[str, Any]] = {}
    source_title = ""
    error_message: Optional[str] = None

    try:
        results_map, source_title = fetch_ubilling()
    except Exception as e:
        error_message = f"Error fetching from ubilling: {e}"

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
        "status": "ok" if not error_message else "error",
        "provider": "ubilling",
        "sourceName": source_title or UBILLING_SOURCE,
        "timestamp": datetime.now().isoformat(),
        "selectedOblast": canonical_selected,
        "alertActive": selected_alert,
        "alertChanged": selected_changed,
        "activeCount": active_count,
        "totalCount": len(CANONICAL_REGIONS),
        "fallbackUsed": False,
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
        canonical = normalize_region_name(args.set_oblast)
        if canonical not in CANONICAL_NAMES:
            print(json.dumps({"status": "error", "message": "Unknown oblast"}, ensure_ascii=False))
            sys.exit(2)
        cfg["selectedOblast"] = canonical
        config_changed = True
    if args.set_notifications:
        cfg["notificationsEnabled"] = args.set_notifications.lower() == "true"
        config_changed = True
    if args.set_sound:
        cfg["soundEnabled"] = args.set_sound.lower() == "true"
        config_changed = True
    if args.set_interval:
        cfg["refreshIntervalSec"] = max(MIN_INTERVAL_SEC, min(MAX_INTERVAL_SEC, args.set_interval))
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
