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

def full_path(path):
    return os.path.join(BASE_PATH, path)

def stream_backup(server, path, passphrase):
    abs_path = full_path(path)
    base_name = os.path.basename(abs_path.rstrip("/"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_name = f"{base_name}_{timestamp}.tar.gz.gpg"

    print(f"📦🔐📤 {abs_path} → {server}:~/{remote_name}")

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
        ["ssh", server, f"cat > ~/{remote_name}"],
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

    for server, paths in config.items():
        for path in paths:
            for attempt in range(1, RETRIES + 1):
                try:
                    stream_backup(server, path, passphrase)
                    break
                except subprocess.CalledProcessError as e:
                    if attempt < RETRIES:
                        print(f"⚠️  Попытка {attempt}/{RETRIES} не удалась ({path}): {e}. Повтор через {RETRY_DELAY}с...")
                        time.sleep(RETRY_DELAY)
                    else:
                        print(f"❌ Ошибка обработки {path} после {RETRIES} попыток: {e}")

if __name__ == "__main__":
    main()
