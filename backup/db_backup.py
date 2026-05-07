# db_backup.py
import os
import subprocess
import yaml
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = "config.yaml"
BACKUP_BASE = os.getenv("DB_BACKUP_DIR", "/Volumes/Backup/db")

# ----------------- helpers -----------------

def run(cmd: str):
    print("▶", cmd)
    subprocess.run(cmd, shell=True, check=True)

def check_output(cmd: str) -> str:
    print("▶", cmd)
    out = subprocess.check_output(cmd, shell=True, text=True)
    return out.strip()

# ----------------- swarm detection & container resolution -----------------

def is_swarm_node(host: str) -> bool:
    """
    Проверяем, в swarm ли нода: docker info --format '{{.Swarm.LocalNodeState}}'.
    active   -> нода в Swarm
    inactive -> не в Swarm
    """
    cmd = f"ssh {host} \"docker info --format '{{{{.Swarm.LocalNodeState}}}}' 2>/dev/null\""
    try:
        state = check_output(cmd)
    except subprocess.CalledProcessError:
        # docker может быть недоступен; считаем, что не swarm
        return False
    return state == "active"  # active/inactive.[web:255]

def find_container_standalone(host: str, name: str) -> str:
    """
    Ищем контейнер по точному имени на обычном Docker‑хосте.
    """
    cmd = (
        f"ssh {host} "
        f"\"docker ps --filter 'name=^{name}$' --format '{{{{.Names}}}}'\""
    )
    out = check_output(cmd)
    if not out:
        raise RuntimeError(f"container '{name}' not found on {host}")
    return out.splitlines()[0]  # берём первый, если вдруг несколько.[web:247]

def find_container_swarm(host: str, service_name: str) -> str:
    """
    В Swarm контейнеры сервиса помечены label com.docker.swarm.service.name=service_name.
    Берём имя одного из контейнеров этого сервиса.
    """
    cmd = (
        f"ssh {host} "
        f"\"docker ps --filter 'label=com.docker.swarm.service.name={service_name}' "
        f\"--format '{{{{.Names}}}}'\""
    )
    out = check_output(cmd)
    if not out:
        raise RuntimeError(
            f\"service '{service_name}' container not found on {host}\"
        )
    # Если несколько реплик — берём первую. Можно добавить логику выбора конкретной.
    return out.splitlines()[0]  # имена вида service.1.taskid.[web:253][web:254]

def resolve_container_name(host: str, name: str) -> str:
    """
    name — значение из config.yaml:
      - если host не в Swarm: считаем это именем контейнера;
      - если host в Swarm: считаем это именем сервиса и берём один из контейнеров.
    """
    if is_swarm_node(host):
        print(f"{host}: Swarm node → '{name}' трактуем как имя сервиса")
        return find_container_swarm(host, name)
    else:
        print(f"{host}: standalone Docker → ищем контейнер '{name}'")
        return find_container_standalone(host, name)

# ----------------- backup functions -----------------

def backup_postgres(name: str, cfg: dict, backup_dir: str):
    host = cfg["host"]
    service_or_container = cfg["container"]
    user = cfg["user"]
    db = cfg["database"]
    password = cfg.get("password")  # опционально, можно хранить в .env

    container = resolve_container_name(host, service_or_container)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_path = os.path.join(backup_dir, f"{name}_postgres_{db}_{ts}.sql.gz")

    print(f"🐘 PostgreSQL dump {name}: {host} / {container} / {db} → {dump_path}")

    if password:
        pg_cmd = f'PGPASSWORD="{password}" pg_dump -U "{user}" "{db}"'
    else:
        pg_cmd = f'pg_dump -U "{user}" "{db}"'

    # ssh host "docker exec -i container bash -lc 'PGPASSWORD=... pg_dump ...'" | gzip > dump.sql.gz.[web:228][web:231][web:235]
    ssh_cmd = (
        f'ssh {host} '
        f'"docker exec -i {container} bash -lc \'{pg_cmd}\'" '
        f'| gzip > "{dump_path}"'
    )

    run(ssh_cmd)

def backup_mysql(name: str, cfg: dict, backup_dir: str):
    host = cfg["host"]
    service_or_container = cfg["container"]
    user = cfg["user"]
    password = cfg["password"]
    db = cfg["database"]

    container = resolve_container_name(host, service_or_container)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_path = os.path.join(backup_dir, f"{name}_mysql_{db}_{ts}.sql.gz")

    print(f"🐬 MySQL dump {name}: {host} / {container} / {db} → {dump_path}")

    # mysqldump -u 'user' -p'pass' 'db'. Пароль в одинарных кавычках, чтобы не разорвало shell.[web:233][web:236]
    mysql_cmd = f"mysqldump -u '{user}' -p'{password}' '{db}'"

    ssh_cmd = (
        f'ssh {host} '
        f'"docker exec -i {container} bash -lc \\"{mysql_cmd}\\"" '
        f'| gzip > "{dump_path}"'
    )

    run(ssh_cmd)

# ----------------- main -----------------

def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    date_str = datetime.now().strftime("%Y-%m-%d")
    backup_dir = os.path.join(BACKUP_BASE, date_str)
    os.makedirs(backup_dir, exist_ok=True)

    for name, cfg in config.items():
        sql_type = cfg.get("sql")
        try:
            if sql_type == "postgres":
                backup_postgres(name, cfg, backup_dir)
            elif sql_type == "mysql":
                backup_mysql(name, cfg, backup_dir)
            else:
                print(f"⚠ {name}: неизвестный тип sql='{sql_type}'")
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка бэкапа {name}: {e}")
        except Exception as e:
            print(f"❌ Ошибка бэкапа {name}: {e}")

if __name__ == "__main__":
    main()
