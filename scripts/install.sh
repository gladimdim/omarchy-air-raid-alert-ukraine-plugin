#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${HOME}/.config/omarchy/plugins/gladimdim.air-raid-alert"
SHELL_CONFIG="${HOME}/.config/omarchy/shell.json"

echo "=== Installing Omarchy Air Raid Alert Plugin ==="
mkdir -p "${HOME}/.config/omarchy/plugins"

if [ -L "$TARGET_DIR" ] || [ -d "$TARGET_DIR" ]; then
  echo "Removing existing link/folder at $TARGET_DIR..."
  rm -rf "$TARGET_DIR"
fi

echo "Creating symlink from $SCRIPT_DIR to $TARGET_DIR..."
ln -s "$SCRIPT_DIR" "$TARGET_DIR"

if [ -f "$SHELL_CONFIG" ]; then
  echo "Checking $SHELL_CONFIG..."
  if ! grep -q "gladimdim.air-raid-alert" "$SHELL_CONFIG"; then
    echo "Adding 'gladimdim.air-raid-alert' to $SHELL_CONFIG bar layout..."
    python3 - <<EOF
import json
from pathlib import Path

p = Path("${SHELL_CONFIG}")
try:
    data = json.loads(p.read_text(encoding="utf-8"))
    right_list = data.get("bar", {}).get("layout", {}).get("right", [])
    if not any(item.get("id") == "gladimdim.air-raid-alert" for item in right_list):
        # Insert before clock if exists, else append
        clock_idx = next((i for i, item in enumerate(right_list) if item.get("id") == "omarchy.clock"), -1)
        new_entry = {"id": "gladimdim.air-raid-alert"}
        if clock_idx != -1:
            right_list.insert(clock_idx, new_entry)
        else:
            right_list.append(new_entry)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Successfully added gladimdim.air-raid-alert to bar.layout.right in shell.json")
except Exception as e:
    print(f"Notice: Could not automatically update shell.json: {e}")
EOF
  else
    echo "'gladimdim.air-raid-alert' is already in $SHELL_CONFIG."
  fi
fi

echo ""
echo "Installation complete!"
echo "To activate immediately, run:"
echo "  omarchy restart shell"
