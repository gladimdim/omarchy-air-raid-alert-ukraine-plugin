# Omarchy Air Raid Alert Plugin for Ukraine 🇺🇦

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Omarchy%20Linux%20%7C%20Hyprland-brightgreen.svg)](https://omarchy.org/)

An official-grade **Omarchy Linux status bar (dock) plugin** providing real-time air raid alarm (**Повітряна тривога**) monitoring, oblast selection, popout details panel, and urgent desktop + audio siren notifications for Ukraine.

<p align="center">
  <img src="preview.png" alt="Omarchy Air Raid Alert Plugin Preview" width="460">
</p>

---

## ⚡ Features

- **Dock / Bar Widget**: Real-time status icon in the Omarchy bar:
  - 🇺🇦 **Ukrainian Trident (Тризуб)**:
    - 🟢 **All-Clear State**: Solid vibrant emerald green (`#22c55e`). Tooltip displays your selected oblast and safe status.
    - 🚨 **Urgent Alert State**: Turns crimson red (`#ef4444`) and **blinks continuously** with a pulsing alert badge whenever an air raid alarm is active in your oblast.
- **Rich Popup Panel**: Click the dock icon to open a sleek Quickshell popout card:
  - **Hero Status Banner**: Displays the Ukrainian Trident and the **official Coat of Arms** of your selected oblast with real-time status and shelter warnings.
  - **Oblast Selector with Official Emblems**: Choose which oblast you live in (all 24 oblasts + Kyiv City + Crimea/Sevastopol), featuring the **official SVG Coat of Arms** for every single region and live search filtering.
  - **National Overview**: Live count of active alerts across Ukraine, with active oblasts highlighted on top.
  - **Provider & Settings Manager**: Switch API providers, enter API tokens, configure polling intervals (15s, 30s, 60s), and toggle notifications or sound.
- **Desktop Notifications**: Automatic urgent notifications triggered via `omarchy-notification-send`:
  - `🚨 ПОВІТРЯНА ТРИВОГА!` when an alert starts in your region.
  - `🟢 ВІДБІЙ ТРИВОГИ` when an alert is cleared.
- **Sound Alerts**: Built-in sound effects played via PipeWire (`pw-play`):
  - Attention-grabbing two-tone siren (`assets/siren.wav`) when an alarm begins.
  - Ascending harmonic chime (`assets/clear.wav`) on all-clear.
- **Multi-Provider API Architecture**: Supports 3 major Ukrainian alert providers with zero-configuration defaults and automatic fallback.

---

## 📡 Supported API Providers & Key Comparison

| Provider | Endpoint | Requires API Key? | Cost | Description & Registration |
| :--- | :--- | :---: | :---: | :--- |
| **Ubilling / Mørk Skogen API** *(Default)* | `https://ubilling.net.ua/aerialalerts/` | **No** (Zero-config) | **Free** | Public JSON aggregator widely used across Ukrainian ISPs and communities since 2022. Works immediately out-of-the-box without registration. |
| **Alerts.in.ua** | `https://api.alerts.in.ua/v1/alerts/active.json` | **Yes** (Bearer Token) | **Free** | Fast, high-reliability community API. Register and request your personal token at [devs.alerts.in.ua](https://devs.alerts.in.ua). |
| **UkraineAlarm** | `https://api.ukrainealarm.com/api/v3/alerts` | **Yes** (API Key) | **Free / Reg.** | Official backend for the "Повітряна тривога" mobile app by Ajax Systems & Stfalcon in cooperation with the Ministry of Digital Transformation. Apply at [api.ukrainealarm.com](https://api.ukrainealarm.com). |

> [!TIP]
> By default, the plugin uses **Ubilling / Mørk Skogen API**, which requires **no registration or API key**. It works the moment you install the plugin! If you already have or wish to create an API key from **alerts.in.ua** or **api.ukrainealarm.com**, you can switch the provider in the plugin's "Налаштування" tab and paste your token.

---

## 🚀 Installation

### 1. Run the automatic installer
From this directory:

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

This will:
1. Symlink this folder to `~/.config/omarchy/plugins/gladimdim.air-raid-alert`.
2. Automatically add `gladimdim.air-raid-alert` to `bar.layout.right` in `~/.config/omarchy/shell.json`.

### 2. Restart the Omarchy Shell
```bash
omarchy restart shell
```

The air raid alert icon (`󰂚` / `󰚌`) will appear in your status bar!

---

## 🖥️ Usage

### Mouse Actions on Dock Icon
- **Left Click**: Toggles the interactive Popup Monitor.
- **Right Click**: Triggers an instant data refresh from the active API provider.

### Inside the Popup Panel
- **Tab 1: Мій регіон (My Region)**:
  - Use the search box to find your oblast (e.g. `Київ`, `Львів`, `Харків`, `Одеса`, `Дніпро`).
  - Click any oblast row to immediately set it as your monitored region.
  - Toggle desktop notifications and audio siren.
  - Click **"Надіслати тестове сповіщення та звук"** to test your setup.
- **Tab 2: Україна (National Status)**:
  - View how many oblasts are currently under alert across the entire country.
  - Check active alerts and start timestamps in other regions.
- **Tab 3: Налаштування (Settings)**:
  - Choose between **Ubilling**, **Alerts.in.ua**, and **UkraineAlarm**.
  - Enter and save your API token if using alerts.in.ua or UkraineAlarm.
  - Set polling frequency (15s, 30s, or 60s).
  - Test siren or all-clear sound clips.

---

## ⚙️ Configuration File

Settings are saved automatically to `~/.config/omarchy/air-raid-alert.json`:

```json
{
  "selectedOblast": "м. Київ",
  "provider": "ubilling",
  "apiKey": "",
  "notificationsEnabled": true,
  "soundEnabled": true,
  "refreshIntervalSec": 20,
  "fallbackToUbilling": true,
  "showOblastInBar": true
}
```

---

## 🛠️ CLI & Headless Usage

The included `alert_engine.py` can also be run independently from the command line:

```bash
# Fetch latest status across Ukraine and print normalized JSON
python3 alert_engine.py --fetch

# Change your monitored oblast to Lviv
python3 alert_engine.py --set-oblast "Львівська область"

# Switch provider to alerts.in.ua and provide a token
python3 alert_engine.py --set-provider alerts_in_ua --set-api-key "YOUR_TOKEN"

# Send a test desktop notification and play siren
python3 alert_engine.py --test-notification

# Play sound directly
python3 alert_engine.py --play-siren
python3 alert_engine.py --play-clear
```

---

## 🧪 Unit Tests

Run test suite:

```bash
python3 -m unittest discover -s tests
```

Tests cover:
- Region name normalization (Cyrillic, Latin, abbreviations).
- Configuration loading and persistence.
- Mock API parsing for Ubilling, alerts.in.ua, and UkraineAlarm.
- Automatic fallback handling when primary API token fails or expires.

---

## 📜 License

MIT License. Developed for [Omarchy Linux](https://omarchy.org/).
Author: **Dmytro Gladkyi**
