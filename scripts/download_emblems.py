#!/usr/bin/env python3
"""
Downloads official SVG Coats of Arms for all 27 Ukrainian administrative regions
from Wikimedia Commons using browser headers to respect rate limits.
"""

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REGION_FILES = {
    "kyiv-city": "COA_of_Kyiv_Kurovskyi.svg",
    "kyiv-obl": "Coat_of_Arms_of_Kiev_Oblast.svg",
    "vinnytsia": "Coat_of_Arms_of_Vinnytsa_Oblast.svg",
    "volyn": "Volyn_coat_of_arms.svg",
    "dnipro": "Large_Coat_of_Arms_of_Dnipropetrovsk_Oblast.svg",
    "donetsk": "Coat_of_Arms_of_Donetsk_Oblast_1999.svg",
    "zhytomyr": "Coat_of_Arms_of_Zhytomyr_Oblast.svg",
    "zakarpattia": "Karpatska_Ukraina-2_COA.svg",
    "zaporizhzhia": "Coat_of_arms_of_Zaporizhia_Oblast.svg",
    "ivano-frankivsk": "Ivano-Frankivsk_Oblast-COA.svg",
    "kirovohrad": "Coat_of_Arms_of_Kirovohrad_Oblast.svg",
    "luhansk": "Coat_of_Arms_Luhansk_Oblast.svg",
    "lviv": "Coat_of_Arms_of_Lviv_Oblast.svg",
    "mykolaiv": "Coat_of_Arms_of_Mykolaiv_Oblast.svg",
    "odesa": "Coat_of_Arms_of_Odesa_Oblast.svg",
    "poltava": "Large_Coat_of_Arms_of_Poltava_Oblast.svg",
    "rivne": "Coat_of_Arms_of_Rivne_Oblast.svg",
    "sumy": "Coat_of_Arms_of_Sumy_Oblast.svg",
    "ternopil": "Coat_of_Arms_of_Ternopil_Oblast.svg",
    "kharkiv": "COA_of_Kharkiv_Oblast.svg",
    "kherson": "Coat_of_Arms_of_Kherson_Oblast.svg",
    "khmelnytskyi": "Coat_of_Arms_of_Khmelnytskyi_Oblast.svg",
    "cherkasy": "Coat_of_Arms_of_Cherkasy_Oblast.svg",
    "chernivtsi": "Coat_of_Arms_of_Chernivtsi_Oblast.svg",
    "chernihiv": "Coat_of_Arms_of_Chernihiv_Oblast.svg",
    "crimea": "Emblem_of_Crimea.svg",
    "sevastopol": "COA_of_Sevastopol.svg"
}

def get_wikimedia_direct_urls(titles):
    titles_param = "|".join("File:" + t for t in titles)
    api_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&titles="
        + urllib.parse.quote(titles_param)
        + "&prop=imageinfo&iiprop=url&format=json"
    )
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0.0.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    
    url_map = {}
    pages = data.get("query", {}).get("pages", {})
    for pid, p in pages.items():
        title = p.get("title", "").replace("File:", "").replace(" ", "_")
        if "imageinfo" in p and p["imageinfo"]:
            url_map[title] = p["imageinfo"][0]["url"]
    return url_map

def download_file(url, target_path):
    cmd = [
        "curl", "-s", "-L",
        "--max-time", "15",
        "-H", "User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
        url,
        "-o", str(target_path)
    ]
    subprocess.run(cmd, check=True)

def main():
    target_dir = Path(__file__).resolve().parent.parent / "assets" / "emblems"
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching direct URLs for {len(REGION_FILES)} coats of arms...")
    title_list = list(REGION_FILES.values())
    url_map = get_wikimedia_direct_urls(title_list)

    success_count = 0
    for code, filename in REGION_FILES.items():
        target_file = target_dir / f"{code}.svg"
        if target_file.exists() and target_file.stat().st_size > 500:
            print(f"Already downloaded {code}.")
            success_count += 1
            continue

        clean_name = filename.replace(" ", "_")
        url = url_map.get(clean_name)
        if not url:
            for k, v in url_map.items():
                if k.lower() == clean_name.lower():
                    url = v
                    break

        if not url:
            print(f"FAILED to find URL for {code}: {filename}", file=sys.stderr)
            continue

        print(f"Downloading {code} ({filename})...")
        try:
            download_file(url, target_file)
            if target_file.exists() and target_file.stat().st_size > 500:
                success_count += 1
            else:
                print(f"Warning: File {target_file} too small or invalid.")
            time.sleep(0.3)
        except Exception as e:
            print(f"Error downloading {code}: {e}", file=sys.stderr)

    print(f"\nDone! Successfully downloaded {success_count}/{len(REGION_FILES)} coats of arms into {target_dir}")

if __name__ == "__main__":
    main()
