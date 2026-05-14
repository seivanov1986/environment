#!/usr/bin/env python3
"""
image-importer — pure Python version.
Walks a source directory, optionally filters images with YOLO,
deduplicates by SHA-256, and organises files as dest/YYYY/MM/DD/.
Videos go to dest/video/YYYY/MM/DD/.
"""

import argparse
import hashlib
import json
import logging
import os
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".cr2", ".nef", ".arw", ".dng", ".raf"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".hevc", ".avi", ".mkv", ".wmv", ".3gp"}


def detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


class DB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS images (
                hash        TEXT PRIMARY KEY,
                path        TEXT NOT NULL,
                imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        self._lock = threading.Lock()

    def try_insert(self, file_hash: str, path: str) -> bool:
        with self._lock:
            # Filenames with invalid UTF-8 bytes are represented as surrogate
            # characters by Python's surrogateescape handler; encode back to
            # bytes then decode as latin-1 so SQLite can store the path.
            safe_path = path.encode("utf-8", errors="surrogateescape").decode("latin-1")
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO images (hash, path) VALUES (?, ?)", (file_hash, safe_path)
            )
            self.conn.commit()
            return cur.rowcount > 0

    def close(self):
        self.conn.close()


class YOLOFilter:
    def __init__(self, model_path: str = "yolov8n.pt", keep_classes: Optional[set] = None, device: str = "auto"):
        try:
            from ultralytics import YOLO
        except ImportError:
            sys.exit("ERROR: ultralytics not installed. Run: pip install ultralytics")

        if keep_classes is None:
            keep_classes = {"person", "dog", "cat", "horse", "sheep", "cow", "bird"}
        self.keep_classes = keep_classes
        self.device = detect_device() if device == "auto" else device
        self._lock = threading.Lock()

        log.info(f"Loading YOLO model {model_path} on {self.device}...")
        self.model = YOLO(model_path)
        self.model.to(self.device)
        log.info("YOLO ready")

    def _reload_on_cpu(self):
        """Переинициализирует модель на CPU после CUDA-ошибки."""
        from ultralytics import YOLO
        log.warning("[WARN]  CUDA error detected — switching to CPU for all remaining files")
        self.device = "cpu"
        self.model = YOLO(self.model.ckpt_path)
        self.model.to("cpu")

    def should_keep(self, image_path: str) -> bool:
        with self._lock:
            try:
                results = self.model.predict(image_path, imgsz=640, verbose=False, device=self.device)[0]
            except Exception as e:
                if self.device != "cpu":
                    log.warning(f"[WARN]  YOLO GPU error on {Path(image_path).name}: {e}")
                    self._reload_on_cpu()
                    try:
                        results = self.model.predict(image_path, imgsz=640, verbose=False, device="cpu")[0]
                    except Exception as e2:
                        log.warning(f"[WARN]  YOLO error on {Path(image_path).name}: {e2} — importing anyway")
                        return True
                else:
                    log.warning(f"[WARN]  YOLO error on {Path(image_path).name}: {e} — importing anyway")
                    return True
            names = self.model.names
            detected = {names[int(box.cls)] for box in results.boxes}
            return bool(detected & self.keep_classes)


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def image_date(path: str) -> Optional[datetime]:
    try:
        import exifread
        with open(path, "rb") as f:
            tags = exifread.process_file(f, stop_tag="EXIF DateTimeOriginal", details=False)
        tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
        if tag:
            return datetime.strptime(str(tag), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def video_date(path: str) -> Optional[datetime]:
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_entries", "format_tags=creation_time", path
        ], stderr=subprocess.DEVNULL)
        data = json.loads(out)
        raw = data.get("format", {}).get("tags", {}).get("creation_time", "")
        if raw:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
    except Exception:
        pass
    return None


def unique_path(directory: str, filename: str) -> str:
    candidate = os.path.join(directory, filename)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(filename)
    i = 1
    while True:
        candidate = os.path.join(directory, f"{stem}_{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1


class Importer:
    def __init__(self, db: DB, dest: str, filtered_dir: str, workers: int, yolo: Optional[YOLOFilter]):
        self.db = db
        self.dest = dest
        self.filtered_dir = filtered_dir
        self.workers = workers
        self.yolo = yolo
        self.imported = 0
        self.imported_videos = 0
        self.skipped = 0
        self.filtered = 0
        self.errors = 0
        self._lock = threading.Lock()

    def _inc(self, field: str):
        with self._lock:
            setattr(self, field, getattr(self, field) + 1)

    def process_file(self, path: str):
        is_video = Path(path).suffix.lower() in VIDEO_EXTS

        # 1. YOLO filter (photos only)
        if not is_video and self.yolo:
            if not self.yolo.should_keep(path):
                if self.filtered_dir:
                    dest = unique_path(self.filtered_dir, Path(path).name)
                    try:
                        shutil.copy2(path, dest)
                        log.info(f"[TECH]  {Path(path).name} -> {dest}")
                    except Exception as e:
                        log.warning(f"[WARN]  filtered copy failed {Path(path).name}: {e}")
                else:
                    log.info(f"[TECH]  {Path(path).name}")
                self._inc("filtered")
                return

        # 2. Hash
        try:
            h = hash_file(path)
        except Exception as e:
            log.error(f"[ERROR] hash {path}: {e}")
            self._inc("errors")
            return

        # 3. Date
        date = None
        current_year = datetime.now().year
        try:
            date = video_date(path) if is_video else image_date(path)
        except Exception:
            pass

        if date is None or date.year > current_year:
            if date is not None:
                log.warning(f"[WARN]  future EXIF date ({date.year}) for {Path(path).name}, using mtime")
            else:
                log.warning(f"[WARN]  no metadata date for {Path(path).name}, using mtime")
            date = datetime.fromtimestamp(os.path.getmtime(path))

        # 4. Destination path
        base_dir = os.path.join(self.dest, "video") if is_video else self.dest
        dest_dir = os.path.join(base_dir, f"{date.year:04d}", f"{date.month:02d}", f"{date.day:02d}")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = unique_path(dest_dir, Path(path).name)

        # 5. Copy
        try:
            shutil.copy2(path, dest_path)
        except Exception as e:
            log.error(f"[ERROR] copy {path}: {e}")
            self._inc("errors")
            return

        # 6. DB insert (dedup)
        if not self.db.try_insert(h, dest_path):
            os.remove(dest_path)
            log.info(f"[SKIP]  duplicate: {Path(path).name}")
            self._inc("skipped")
            return

        log.info(f"[OK]    {Path(path).name} -> {dest_path}")
        self._inc("imported_videos" if is_video else "imported")

    def run(self, source: str):
        abs_source = os.path.abspath(source)
        abs_dest = os.path.abspath(self.dest)
        skip_dirs = {abs_dest}
        if self.filtered_dir:
            skip_dirs.add(os.path.abspath(self.filtered_dir))

        q: queue.Queue = queue.Queue(maxsize=self.workers * 4)
        _sentinel = object()

        def scanner():
            log.info(f"Scanning {source} ...")
            for dirpath, dirnames, filenames in os.walk(abs_source, topdown=True):
                dirnames[:] = [
                    d for d in dirnames
                    if os.path.abspath(os.path.join(dirpath, d)) not in skip_dirs
                ]
                log.info(f"Scanning dir: {dirpath}")
                for filename in filenames:
                    if Path(filename).suffix.lower() in IMAGE_EXTS | VIDEO_EXTS:
                        q.put(os.path.join(dirpath, filename))
            q.put(_sentinel)

        scan_thread = threading.Thread(target=scanner, daemon=True)
        scan_thread.start()

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = []
            while True:
                item = q.get()
                if item is _sentinel:
                    break
                futures.append(executor.submit(self.process_file, item))
            for f in futures:
                f.result()


def main():
    parser = argparse.ArgumentParser(description="Image/video importer with optional YOLO filtering")
    parser.add_argument("-source", required=True, help="Source directory with images")
    parser.add_argument("-dest", required=True, help="Destination storage directory")
    parser.add_argument("-workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("-filter", action="store_true", help="Enable YOLO filter (skip photos without people/animals)")
    parser.add_argument("-yolo-model", default="yolov8n.pt", dest="yolo_model", help="YOLOv8 model file")
    parser.add_argument("-yolo-classes", default="person,dog,cat,horse,sheep,cow,bird", dest="yolo_classes",
                        help="Comma-separated YOLO classes to keep")
    parser.add_argument("-device", default="auto",
                        help="Device for YOLO: auto (default), cpu, cuda, mps, cuda:0, etc.")
    args = parser.parse_args()

    os.makedirs(args.dest, exist_ok=True)
    db = DB(os.path.join(args.dest, ".index.db"))

    yolo = None
    filtered_dir = ""
    if args.filter:
        keep_classes = set(args.yolo_classes.split(","))
        yolo = YOLOFilter(model_path=args.yolo_model, keep_classes=keep_classes, device=args.device)
        filtered_dir = os.path.join(args.dest, "filtered")
        os.makedirs(filtered_dir, exist_ok=True)

    imp = Importer(db, args.dest, filtered_dir, args.workers, yolo)
    imp.run(args.source)
    db.close()

    print(f"\nResults:")
    print(f"  Imported : {imp.imported} photos")
    print(f"  Imported : {imp.imported_videos} videos")
    print(f"  Skipped  : {imp.skipped} (duplicates)")
    print(f"  Filtered : {imp.filtered} (no people/animals)")
    print(f"  Errors   : {imp.errors}")


if __name__ == "__main__":
    main()
