import subprocess
import os
import sys

def decrypt_gpg_file(gpg_file_path, output_path=None, passphrase=None):
    if not os.path.exists(gpg_file_path):
        print(f"❌ Файл не найден: {gpg_file_path}")
        return

    if output_path is None:
        output_path = gpg_file_path.replace(".gpg", "")

    if passphrase is None:
        passphrase = input("🔑 Введите пароль для расшифровки: ")

    try:
        subprocess.run([
            "gpg", "--batch", "--yes",
            "--passphrase", passphrase,
            "--output", output_path,
            "--decrypt", gpg_file_path
        ], check=True)
        print(f"✅ Расшифрованный файл сохранён как: {output_path}")
    except subprocess.CalledProcessError:
        print("❌ Ошибка расшифровки. Проверьте пароль или файл.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python decrypt_file.py <путь_к_файлу.gpg> [выходной_файл]")
        sys.exit(1)

    gpg_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else None

    decrypt_gpg_file(gpg_file, output_path=out_file)
