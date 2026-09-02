#!/usr/bin/env bash
set -euo pipefail

PLUGIN_ID="gladimdim.air-raid-alert"
TARGET_DIR="${HOME}/.config/omarchy/plugins/${PLUGIN_ID}"
SHELL_CONFIG="${HOME}/.config/omarchy/shell.json"
STATE_CONFIG="${HOME}/.config/omarchy/air-raid-alert.json"

echo "=== Uninstalling Omarchy Air Raid Alert Plugin ==="

# 1. Disable via omarchy CLI if available
if command -v omarchy >/dev/null 2>&1; then
  echo "Disabling plugin via omarchy CLI..."
  omarchy plugin disable "$PLUGIN_ID" 2>/dev/null || true
fi

# 2. Clean from shell.json layout
if [ -f "$SHELL_CONFIG" ]; then
  echo "Removing '${PLUGIN_ID}' from $SHELL_CONFIG..."
  python3 - <<EOF
import json
from pathlib import Path

p = Path("${SHELL_CONFIG}")
try:
    data = json.loads(p.read_text(encoding="utf-8"))
    bar_layout = data.get("bar", {}).get("layout", {})
    modified = False
    for section in ["left", "center", "right"]:
        items = bar_layout.get(section, [])
        new_items = [i for i in items if i.get("id") != "${PLUGIN_ID}"]
        if len(new_items) != len(items):
            bar_layout[section] = new_items
            modified = True
    if modified:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Removed from bar layout in shell.json")
except Exception as e:
    print(f"Notice: Failed to update shell.json: {e}")
EOF
fi

# 3. Remove plugin directory or symlink
if [ -L "$TARGET_DIR" ] || [ -d "$TARGET_DIR" ]; then
  echo "Removing plugin files at $TARGET_DIR..."
  rm -rf "$TARGET_DIR"
fi

# 4. Optional state cleanup
if [ -f "$STATE_CONFIG" ]; then
  read -p "Do you want to delete user configuration ($STATE_CONFIG)? [y/N] " -n 1 -r || true
  echo
  if [[ ${REPLY:-n} =~ ^[Yy]$ ]]; then
    rm -f "$STATE_CONFIG"
    echo "Removed $STATE_CONFIG"
  fi
fi

# 5. Reload shell
if command -v omarchy >/dev/null 2>&1; then
  echo "Restarting Omarchy shell..."
  omarchy restart shell 2>/dev/null || true
fi

echo ""
echo "=== Successfully uninstalled ${PLUGIN_ID} ==="
