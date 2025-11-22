import yaml
import subprocess
import os
import sys

BASE_DIR = "/Users/seivanov/Storage/shop"   # ← укажи актуальный путь
BACKUP_DEST = "/Volumes/Backup/shop_backup"
KEY = "hetzner3"  # ключ из YAML-файла

def run_rsync(src, dest):
    try:
        subprocess.run(
            ["rsync", "-avzP", src, dest],
            check=True
        )
        print(f"✅ Копировано: {src} → {dest}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при копировании {src}: {e}")

def main():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    projects = config.get(KEY, [])
    if not projects:
        print(f"⚠️ Нет проектов в ключе '{KEY}'")
        return

    for project in projects:
        src = os.path.join(BASE_DIR, project) + "/"  # важно: закрывающий `/` нужен
        dest = os.path.join(BACKUP_DEST, project)

        print(src, dest)

        if not os.path.exists(src):
            print(f"⚠️ Пропущено (нет директории): {src}")
            continue

        run_rsync(src, dest)

if __name__ == "__main__":
        main()
