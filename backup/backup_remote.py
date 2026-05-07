import os
import yaml
import subprocess
import tempfile
from datetime import datetime
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()
BASE_PATH = os.getenv("BASE_PATH", "/tmp")
passphrase = os.getenv("GPG_PASSPHRASE")

CONFIG_PATH = "config.yaml"

def full_path(path):
    return os.path.join(BASE_PATH, path)

def archive_and_encrypt(path, output_dir, passphrase):
    abs_path = full_path(path)
    base_name = os.path.basename(abs_path.rstrip("/"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tar_path = os.path.join(output_dir, f"{base_name}_{timestamp}.tar.gz")
    enc_path = tar_path + ".gpg"

    print(f"📦 Архивация: {abs_path} → {tar_path}")
    subprocess.run(["tar", "-czf", tar_path, abs_path], check=True)

    print(f"🔐 Шифрование (симметрично): {tar_path} → {enc_path}")
    subprocess.run([
        "gpg", "--symmetric", "--cipher-algo", "AES256",
        "--batch", "--yes", "--passphrase", passphrase,
        "--output", enc_path, tar_path
    ], check=True)

    os.remove(tar_path)
    return enc_path

def send_file(server, file_path):
    print(f"📤 Отправка на {server}")
    subprocess.run(["scp", file_path, f"{server}:~/"], check=True)

def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    with tempfile.TemporaryDirectory() as tmpdir:
        for server, paths in config.items():
            for path in paths:
                try:
                    enc_file = archive_and_encrypt(path, tmpdir, passphrase)
                    send_file(server, enc_file)
                except subprocess.CalledProcessError as e:
                    print(f"❌ Ошибка обработки {path}: {e}")

if __name__ == "__main__":
    main()
