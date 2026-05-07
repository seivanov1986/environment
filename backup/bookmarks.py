#!/usr/bin/env python3
import json
import sqlite3
import time
import shutil
import tempfile
import plistlib
from pathlib import Path
from typing import List, Dict

HOME = Path.home()


def wait_for_unlocked(path: Path, desc: str, timeout: int = 300, interval: float = 2.0) -> bool:
    """
    Ждём, пока файл перестанет быть заблокирован sqlite (простая проверка через попытку connect).
    Используется для Firefox (places.sqlite). При timeout возвращает False.
    """
    start = time.time()
    while True:
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            conn.close()
            return True
        except sqlite3.OperationalError:
            elapsed = int(time.time() - start)
            if elapsed >= timeout:
                print(f"[WARN] {desc}: файл всё ещё заблокирован после {timeout} c, пропускаю.")
                return False
            print(f"[INFO] {desc}: файл заблокирован, закройте соответствующий браузер. "
                  f"Жду... ({elapsed} c)")
            time.sleep(interval)


def collect_chromium_like_bookmarks(profile_dir: Path, browser_name: str) -> List[Dict]:
    results = []
    bookmarks_file = profile_dir / "Bookmarks"
    if not bookmarks_file.is_file():
        return results

    data = json.loads(bookmarks_file.read_text(encoding="utf-8"))

    def walk(node, path=""):
        node_type = node.get("type")
        if node_type == "url":
            results.append({
                "title": node.get("name"),
                "url": node.get("url"),
                "folder": path,
                "browser": browser_name,
            })
        elif node_type == "folder":
            new_path = f"{path}/{node.get('name')}" if path else node.get("name")
            for child in node.get("children", []):
                walk(child, new_path)

    roots = data.get("roots", {})
    for root in roots.values():
        walk(root)
    return results


def collect_firefox_bookmarks(profile_dir: Path) -> List[Dict]:
    results = []
    db_path = profile_dir / "places.sqlite"
    if not db_path.is_file():
        return results

    # Ждём, пока Firefox освободит базу
    if not wait_for_unlocked(db_path, f"Firefox profile {profile_dir.name}"):
        return results

    # Работаем с копией, чтобы не трогать живую БД
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_db = tmp_dir / "places.sqlite"
    shutil.copy2(db_path, tmp_db)

    conn = sqlite3.connect(str(tmp_db))
    cur = conn.cursor()
    cur.execute("""
        SELECT b.title, p.url
        FROM moz_bookmarks b
        JOIN moz_places p ON b.fk = p.id
        WHERE p.url NOT NULL
    """)
    for title, url in cur.fetchall():
        results.append({
            "title": title,
            "url": url,
            "folder": "",
            "browser": "firefox",
        })
    conn.close()
    return results


def collect_safari_bookmarks() -> List[Dict]:
    results = []
    safari_paths = [
        HOME / "Library" / "Safari" / "Bookmarks.plist",
        HOME / "Library" / "Containers" / "com.apple.Safari" / "Data" / "Library" / "Safari" / "Bookmarks.plist",
    ]
    plist_path = next((p for p in safari_paths if p.is_file()), None)
    if not plist_path:
        return results

    with plist_path.open("rb") as f:
        data = plistlib.load(f)

    def walk(node, path=""):
        node_type = node.get("WebBookmarkType")
        if node_type == "WebBookmarkTypeLeaf":
            url = node.get("URLString")
            if url:
                results.append({
                    "title": node.get("URIDictionary", {}).get("title", ""),
                    "url": url,
                    "folder": path,
                    "browser": "safari",
                })
        elif node_type == "WebBookmarkTypeList":
            title = node.get("Title") or ""
            new_path = f"{path}/{title}" if title and path else (title or path)
            for child in node.get("Children", []):
                walk(child, new_path)

    walk(data)
    return results


def main():
    all_bookmarks: List[Dict] = []

    # Chrome / Brave / Chromium-like на macOS
    chromium_profiles = {
        "chrome":   HOME / "Library" / "Application Support" / "Google" / "Chrome" / "Default",
        "chromium": HOME / "Library" / "Application Support" / "Chromium" / "Default",
        "brave":    HOME / "Library" / "Application Support" / "BraveSoftware" / "Brave-Browser" / "Default",
    }
    for browser_name, path in chromium_profiles.items():
        if path.is_dir():
            all_bookmarks.extend(collect_chromium_like_bookmarks(path, browser_name))

    # Firefox
    firefox_profiles_root = HOME / "Library" / "Application Support" / "Firefox" / "Profiles"
    if firefox_profiles_root.is_dir():
        for prof in firefox_profiles_root.iterdir():
            if prof.is_dir() and (prof.name.endswith(".default") or ".default-" in prof.name):
                all_bookmarks.extend(collect_firefox_bookmarks(prof))

    # Safari
    all_bookmarks.extend(collect_safari_bookmarks())

    out_file = Path("all_bookmarks.tsv")
    with out_file.open("w", encoding="utf-8") as f:
        f.write("browser\tfolder\ttitle\turl\n")
        for bm in all_bookmarks:
            browser = bm.get("browser", "")
            folder = bm.get("folder", "") or ""
            title = (bm.get("title") or "").replace("\t", " ")
            url = bm.get("url") or ""
            if not url:
                continue
            f.write(f"{browser}\t{folder}\t{title}\t{url}\n")

    print(f"Collected {len(all_bookmarks)} bookmarks into {out_file}")


if __name__ == "__main__":
    main()
