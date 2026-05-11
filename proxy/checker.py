#!/usr/bin/env python3
import argparse
import requests

TARGET_URL = "https://example.com"
TIMEOUT = 10


def check_http(host, port, user, password):
    print("=== Проверка HTTP-прокси ===")
    proxies = {
        "http": f"http://{user}:{password}@{host}:{port}",
        "https": f"http://{user}:{password}@{host}:{port}",
    }
    try:
        r = requests.get(TARGET_URL, proxies=proxies, timeout=TIMEOUT)
        print("HTTP код:", r.status_code)
        print("HTTP-прокси: OK" if r.ok else "HTTP-прокси: ОТВЕТ С ОШИБКОЙ")
    except Exception as e:
        print("HTTP-прокси: НЕ РАБОТАЕТ:", e)
    print()


def check_https(host, port, user, password):
    print("=== Проверка HTTPS-прокси ===")
    proxies = {
        "http": f"https://{user}:{password}@{host}:{port}",
        "https": f"https://{user}:{password}@{host}:{port}",
    }
    try:
        r = requests.get(TARGET_URL, proxies=proxies, timeout=TIMEOUT)
        print("HTTP код:", r.status_code)
        print("HTTPS-прокси: OK" if r.ok else "HTTPS-прокси: ОТВЕТ С ОШИБКОЙ")
    except Exception as e:
        print("HTTPS-прокси: НЕ РАБОТАЕТ:", e)
    print()


def check_socks5(host, port, user, password):
    print("=== Проверка SOCKS5-прокси ===")
    # socks5h — резолв доменов на стороне прокси
    proxies = {
        "http": f"socks5h://{user}:{password}@{host}:{port}",
        "https": f"socks5h://{user}:{password}@{host}:{port}",
    }
    try:
        r = requests.get(TARGET_URL, proxies=proxies, timeout=TIMEOUT)
        print("HTTP код:", r.status_code)
        print("SOCKS5-прокси: OK" if r.ok else "SOCKS5-прокси: ОТВЕТ С ОШИБКОЙ")
    except Exception as e:
        print("SOCKS5-прокси: НЕ РАБОТАЕТ:", e)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Проверка HTTP/HTTPS/SOCKS5-прокси с авторизацией"
    )
    parser.add_argument("host", help="адрес прокси")
    parser.add_argument("port", type=int, help="порт прокси")
    parser.add_argument("username", help="логин")
    parser.add_argument("password", help="пароль")
    args = parser.parse_args()

    host = args.host
    port = args.port
    user = args.username
    password = args.password

    check_http(host, port, user, password)
    check_https(host, port, user, password)
    check_socks5(host, port, user, password)


if __name__ == "__main__":
    main()
