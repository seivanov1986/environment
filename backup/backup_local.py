import os
import yaml
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()
BASE_PATH = os.getenv("BASE_PATH", "/tmp")

CONFIG_PATH = "config.yaml"

def full_path(path):
    return os.path.join(BASE_PATH, path)

def archive_and_backup(path, backup_dir):
    abs_path = full_path(path)
    base_name = os.path.basename(abs_path.rstrip("/"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tar_path = os.path.join(backup_dir, f"{base_name}_{timestamp}.tar.gz")

    print(f"📦 Архивация: {abs_path} → {tar_path}")
    subprocess.run(["tar", "-czf", tar_path, abs_path], check=True)
    return tar_path

def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    backup_date = datetime.now().strftime("%Y-%m-%d")
    backup_dir = f"/Volumes/Backup/daily/{backup_date}"
    os.makedirs(backup_dir, exist_ok=True)

    for server, paths in config.items():
        for path in paths:
            try:
                archive_and_backup(path, backup_dir)
            except subprocess.CalledProcessError as e:
                print(f"❌ Ошибка обработки {path}: {e}")

if __name__ == "__main__":
    main()
