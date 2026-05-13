import os
import time
import yaml
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()
BASE_PATH = os.getenv("BASE_PATH", "/tmp")
passphrase = os.getenv("GPG_PASSPHRASE")

CONFIG_PATH = "config.yaml"

def full_path(path, src=None):
    return os.path.join(src or BASE_PATH, path)

def stream_backup(server, path, passphrase, dest="~", src=None):
    abs_path = full_path(path, src)
    base_name = os.path.basename(abs_path.rstrip("/"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_name = f"{base_name}_{timestamp}.tar.gz.gpg"
    remote_path = f"{dest}/{remote_name}"

    print(f"📦🔐📤 {abs_path} → {server}:{remote_path}")

    tar = subprocess.Popen(
        ["tar", "-czf", "-", abs_path],
        stdout=subprocess.PIPE,
    )
    gpg = subprocess.Popen(
        ["gpg", "--symmetric", "--cipher-algo", "AES256",
         "--batch", "--yes", "--passphrase", passphrase, "--output", "-"],
        stdin=tar.stdout,
        stdout=subprocess.PIPE,
    )
    tar.stdout.close()
    ssh = subprocess.Popen(
        ["ssh", server, f"cat > '{remote_path}'"],
        stdin=gpg.stdout,
    )
    gpg.stdout.close()

    ssh.wait()
    gpg.wait()
    tar.wait()

    for proc, name in [(tar, "tar"), (gpg, "gpg"), (ssh, "ssh")]:
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, name)

RETRIES = 3
RETRY_DELAY = 10  # секунд

def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for server, server_config in config.items():
        if isinstance(server_config, dict):
            dest = server_config.get("dest", "~")
            raw_paths = server_config["paths"]
        else:
            dest = "~"
            raw_paths = server_config

        # Разворачиваем пути: строка → (path, BASE_PATH), dict с src/dirs → группа, file → абсолютный путь
        entries = []
        for item in raw_paths:
            if isinstance(item, dict) and "file" in item:
                abs_file = item["file"]
                entries.append((os.path.basename(abs_file), os.path.dirname(abs_file)))
            elif isinstance(item, dict):
                src = item["src"]
                for d in item["dirs"]:
                    entries.append((d, src))
            else:
                entries.append((item, None))

        for path, src in entries:
            for attempt in range(1, RETRIES + 1):
                try:
                    stream_backup(server, path, passphrase, dest=dest, src=src)
                    break
                except subprocess.CalledProcessError as e:
                    if attempt < RETRIES:
                        print(f"⚠️  Попытка {attempt}/{RETRIES} не удалась ({path}): {e}. Повтор через {RETRY_DELAY}с...")
                        time.sleep(RETRY_DELAY)
                    else:
                        print(f"❌ Ошибка обработки {path} после {RETRIES} попыток: {e}")

if __name__ == "__main__":
    main()
