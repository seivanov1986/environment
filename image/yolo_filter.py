#!/usr/bin/env python3
"""
YOLO sidecar filter.
Reads image paths from stdin (one per line), writes "keep" or "skip" to stdout.
The model is loaded once at startup.
"""
import sys
import os

# Save the original stdout for our keep/skip protocol BEFORE importing anything.
# YOLO and PyTorch print progress/warnings to stdout — redirect those to stderr
# so they don't corrupt the Go <-> Python line protocol.
_proto = sys.stdout
sys.stdout = sys.stderr

def main():
    try:
        from ultralytics import YOLO
    except ImportError:
        sys.stderr.write("ERROR: ultralytics not installed. Run: pip install ultralytics\n")
        sys.exit(1)

    model_path = os.environ.get("YOLO_MODEL", "yolov8n.pt")
    keep_classes = set(os.environ.get(
        "YOLO_KEEP_CLASSES",
        "person,dog,cat,horse,sheep,cow,bird"
    ).split(","))

    sys.stderr.write(f"[yolo] loading model {model_path}...\n")
    sys.stderr.flush()
    model = YOLO(model_path)
    model.to('cpu')
    sys.stderr.write("[yolo] ready\n")
    sys.stderr.flush()

    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        try:
            results = model.predict(path, imgsz=640, verbose=False, device='cpu')[0]
            names = model.names
            detected = {names[int(box.cls)] for box in results.boxes}
            if any(cls in keep_classes for cls in detected):
                _proto.write("keep\n")
            else:
                _proto.write("skip\n")
            _proto.flush()
        except Exception as e:
            sys.stderr.write(f"[yolo] error on {path}: {e}\n")
            sys.stderr.flush()
            _proto.write("keep\n")
            _proto.flush()

if __name__ == "__main__":
    main()
