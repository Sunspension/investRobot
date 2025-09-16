#!/usr/bin/env python3
"""
Мастер-скрипт управления investRobot.

Функции:
- Запуск торговой системы (обычный и с ограничением по времени)
- Управление многоаккаунтным режимом
- Сбор рыночных данных → SQLite
- Загрузка исторических данных
- Запуск оптимизации
- Запуск тестов (pytest)
- Операции песочницы (пополнение)

Рекомендуется запускать в активированном виртуальном окружении (env).
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_subprocess(
    args: list[str],
    cwd: Optional[Path] = None,
) -> int:
    """Запускает внешнюю команду и возвращает код возврата."""
    proc = subprocess.run(args, cwd=str(cwd or PROJECT_ROOT))
    return proc.returncode


def _input_nonempty(prompt: str, default: Optional[str] = None) -> str:
    while True:
        raw = input(prompt).strip()
        if raw:
            return raw
        if default is not None:
            return default
        print("Поле не может быть пустым.")


async def _start_trading():
    """Запуск торговой системы (интерактивные параметры)."""
    figi = _input_nonempty("FIGI [FUTIMOEXF000]: ", default="FUTIMOEXF000")
    host = _input_nonempty("Host [127.0.0.1]: ", default="127.0.0.1")
    port = int(_input_nonempty("Port [8050]: ", default="8050"))
    enable_vis = _input_nonempty("Визуализация? (y/n) [y]: ", default="y").lower() == "y"
    start_server = _input_nonempty("Запуск веб-сервера? (y/n) [y]: ", default="y").lower() == "y"

    sys.path.insert(0, str(PROJECT_ROOT))
    from run_trading_system import run_trading_system  # type: ignore

    await run_trading_system(
        figi=figi,
        enable_visualization=enable_vis,
        host=host,
        port=port,
        start_server=start_server,
    )


async def _start_trading_limited():
    figi = _input_nonempty("FIGI [FUTIMOEXF000]: ", default="FUTIMOEXF000")
    host = _input_nonempty("Host [127.0.0.1]: ", default="127.0.0.1")
    port = int(_input_nonempty("Port [8050]: ", default="8050"))
    enable_vis = _input_nonempty("Визуализация? (y/n) [y]: ", default="y").lower() == "y"
    start_server = _input_nonempty("Запуск веб-сервера? (y/n) [y]: ", default="y").lower() == "y"
    duration = int(_input_nonempty("Длительность, сек [60]: ", default="60"))

    sys.path.insert(0, str(PROJECT_ROOT))
    from run_trading_system_limited import run_trading_system_limited  # type: ignore

    await run_trading_system_limited(
        figi=figi,
        enable_visualization=enable_vis,
        host=host,
        port=port,
        start_server=start_server,
        run_duration=duration,
    )


def _multi_account_menu():
    print("\nМногоаккаунтный режим:")
    print("  1) Создать пример конфигурации")
    print("  2) Запустить интерактивный режим")
    print("  3) Запустить в daemon-режиме (фон)")
    print("  4) Остановить daemon")
    print("  5) Статус daemon")
    print("  0) Назад")

    choice = input("> ").strip()
    if choice == "1":
        return _run_subprocess([sys.executable, "run_multi_account.py", "--create-config"])  # type: ignore[arg-type]
    if choice == "2":
        config = _input_nonempty("Путь к accounts_config.json [./accounts_config.json]: ", default="./accounts_config.json")
        return _run_subprocess([sys.executable, "run_multi_account.py", "--config", config, "--interactive"])  # type: ignore[arg-type]
    if choice == "3":
        config = _input_nonempty("Путь к accounts_config.json [./accounts_config.json]: ", default="./accounts_config.json")
        return _run_subprocess([sys.executable, "run_multi_account.py", "--config", config, "--daemon"])  # type: ignore[arg-type]
    if choice == "4":
        pid_file = PROJECT_ROOT / "data" / "multi_robot.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 15)
                print("✔ SIGTERM отправлен. Подождите несколько секунд.")
            except Exception as e:
                print(f"Не удалось остановить: {e}")
        else:
            print("PID-файл не найден: data/multi_robot.pid")
        return 0
    if choice == "5":
        pid_file = PROJECT_ROOT / "data" / "multi_robot.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                print(f"✔ Daemon запущен (PID {pid})")
            except Exception:
                print("⚠ PID-файл есть, но процесс не найден")
        else:
            print("Daemon не запущен (PID-файл отсутствует)")
        return 0
    return 0


def _run_market_ingestor():
    figi = _input_nonempty("FIGI [FUTIMOEXF000]: ", default="FUTIMOEXF000")
    db = _input_nonempty("Путь к БД [data/market.db]: ", default="data/market.db")
    seconds = _input_nonempty("Секунд работать [0=беск.] [0]: ", default="0")
    return _run_subprocess([sys.executable, "run_market_ingestor.py", "--figi", figi, "--db", db, "--seconds", seconds])  # type: ignore[arg-type]


def _load_historical():
    return _run_subprocess([sys.executable, "load_historical_data.py"])  # type: ignore[arg-type]


def _run_optimization():
    return _run_subprocess([sys.executable, "optimization/optimizer.py", "--all"])  # type: ignore[arg-type]


def _run_tests_pytest():
    return _run_subprocess([sys.executable, "-m", "pytest", "-q"])  # type: ignore[arg-type]


def _view_db_summary():
    import sqlite3
    db = _input_nonempty("Путь к БД [data/market.db]: ", default="data/market.db")
    if not Path(db).exists():
        print(f"БД не найдена: {db}")
        return 1
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        print("\nТаблицы:")
        for (name,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table';"):
            print(f" - {name}")
        def _count(table: str) -> int:
            try:
                return cur.execute(f"SELECT COUNT(1) FROM {table};").fetchone()[0]
            except Exception:
                return 0
        print(f"\nCandles: {_count('candles')} записей")
        try:
            rows = cur.execute(
                "SELECT figi, time, open, high, low, close, volume FROM candles ORDER BY time DESC LIMIT 5;"
            ).fetchall()
            if rows:
                print("Последние 5 свечей:")
                for r in rows:
                    print(r)
        except Exception:
            pass
        print(f"\nOrders: {_count('orders')} записей")
        try:
            rows = cur.execute(
                "SELECT order_id, figi, time, type, price, quantity, status, strategy FROM orders ORDER BY time DESC LIMIT 10;"
            ).fetchall()
            if rows:
                print("Последние 10 ордеров:")
                for r in rows:
                    print(r)
        except Exception:
            pass
        conn.close()
        return 0
    except Exception as e:
        print(f"Ошибка чтения БД: {e}")
        return 1


def _run_market_ingestor_daemon():
    figi = _input_nonempty("FIGI [FUTIMOEXF000]: ", default="FUTIMOEXF000")
    db = _input_nonempty("Путь к БД [data/market.db]: ", default="data/market.db")
    logs_dir = PROJECT_ROOT / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "market_recorder.log"
    pid_path = PROJECT_ROOT / "data" / "market_recorder.pid"

    args = [
        sys.executable,
        "run_market_ingestor.py",
        "--figi", figi,
        "--db", db,
        "--seconds", "0",
    ]
    print(f"Стартуем сбор рыночных данных в фоне: {' '.join(args)}")
    with open(log_path, "ab", buffering=0) as logf:
        proc = subprocess.Popen(
            args,
            cwd=str(PROJECT_ROOT),
            stdout=logf,
            stderr=logf,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
            close_fds=True,
        )
    pid_path.write_text(str(proc.pid))
    print(f"✔ Сбор данных запущен в фоне. PID={proc.pid}. Логи: {log_path}")
    return 0


def _stop_market_ingestor_daemon():
    pid_path = PROJECT_ROOT / "data" / "market_recorder.pid"
    if not pid_path.exists():
        print("Фоновый сбор данных не запущен (PID-файл отсутствует)")
        return 0
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 15)
        print(f"✔ SIGTERM отправлен процессу {pid}. Подождите несколько секунд.")
        return 0
    except Exception as e:
        print(f"Не удалось остановить: {e}")
        return 1


def _status_market_ingestor_daemon():
    pid_path = PROJECT_ROOT / "data" / "market_recorder.pid"
    if not pid_path.exists():
        print("Статус: не запущен (PID-файл отсутствует)")
        return 0
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        print(f"Статус: запущен (PID {pid})")
        log_path = PROJECT_ROOT / "data" / "logs" / "market_recorder.log"
        if log_path.exists():
            try:
                print("Последние строки лога:")
                with open(log_path, 'rb') as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 4000))
                    print(f.read().decode(errors='ignore')[-1000:])
            except Exception:
                pass
        return 0
    except Exception:
        print("Статус: PID-файл есть, но процесс не найден")
        return 1


def _run_outbox_daemon():
    db = _input_nonempty("Путь к БД [data/market.db]: ", default="data/market.db")
    logs_dir = PROJECT_ROOT / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "outbox_dispatcher.log"
    pid_path = PROJECT_ROOT / "data" / "outbox_dispatcher.pid"

    args = [
        sys.executable,
        "tools/outbox_dispatcher.py",
        "--db", db,
        "--interval", "1.0",
    ]
    print(f"Стартуем outbox-доставку в фоне: {' '.join(args)}")
    with open(log_path, "ab", buffering=0) as logf:
        proc = subprocess.Popen(
            args,
            cwd=str(PROJECT_ROOT),
            stdout=logf,
            stderr=logf,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None,
            close_fds=True,
        )
    pid_path.write_text(str(proc.pid))
    print(f"✔ Outbox worker запущен. PID={proc.pid}. Логи: {log_path}")
    return 0


def _stop_outbox_daemon():
    pid_path = PROJECT_ROOT / "data" / "outbox_dispatcher.pid"
    if not pid_path.exists():
        print("Outbox worker не запущен (PID-файл отсутствует)")
        return 0
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 15)
        print(f"✔ SIGTERM отправлен Outbox worker (PID {pid})")
        return 0
    except Exception as e:
        print(f"Не удалось остановить Outbox worker: {e}")
        return 1


def _status_outbox_daemon():
    pid_path = PROJECT_ROOT / "data" / "outbox_dispatcher.pid"
    if not pid_path.exists():
        print("Outbox worker: не запущен (PID-файл отсутствует)")
        return 0
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        print(f"Outbox worker: запущен (PID {pid})")
        log_path = PROJECT_ROOT / "data" / "logs" / "outbox_dispatcher.log"
        if log_path.exists():
            try:
                print("Последние строки лога outbox:")
                with open(log_path, 'rb') as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 4000))
                    print(f.read().decode(errors='ignore')[-1000:])
            except Exception:
                pass
        return 0
    except Exception:
        print("Outbox worker: PID-файл есть, но процесс не найден")
        return 1

def _sandbox_payin():
    amount = _input_nonempty("Сумма пополнения (RUB) [100000]: ", default="100000")
    return _run_subprocess([sys.executable, "tools/sandbox_cli.py", "payin", "--amount", amount])  # type: ignore[arg-type]


def _systemd_menu():
    print("\nLinux systemd помощник:")
    print("  1) Установить user‑юниты (market+outbox)")
    print("  2) Статус market‑recorder")
    print("  3) Статус outbox")
    print("  4) Запустить market‑recorder")
    print("  5) Остановить market‑recorder")
    print("  6) Запустить outbox")
    print("  7) Остановить outbox")
    print("  8) Показать логи market‑recorder (последние строки)")
    print("  9) Показать логи outbox (последние строки)")
    print("  0) Назад")

    choice = input("> ").strip()
    if choice == "1":
        return _run_subprocess(["bash", "tools/systemd/install_systemd_units.sh"])  # type: ignore[arg-type]
    if choice == "2":
        return _run_subprocess(["systemctl", "--user", "status", "investrobot-market-recorder.service"])  # type: ignore[arg-type]
    if choice == "3":
        return _run_subprocess(["systemctl", "--user", "status", "investrobot-outbox.service"])  # type: ignore[arg-type]
    if choice == "4":
        return _run_subprocess(["systemctl", "--user", "start", "investrobot-market-recorder.service"])  # type: ignore[arg-type]
    if choice == "5":
        return _run_subprocess(["systemctl", "--user", "stop", "investrobot-market-recorder.service"])  # type: ignore[arg-type]
    if choice == "6":
        return _run_subprocess(["systemctl", "--user", "start", "investrobot-outbox.service"])  # type: ignore[arg-type]
    if choice == "7":
        return _run_subprocess(["systemctl", "--user", "stop", "investrobot-outbox.service"])  # type: ignore[arg-type]
    if choice == "8":
        return _run_subprocess(["journalctl", "--user", "-u", "investrobot-market-recorder", "-n", "100", "-e"])  # type: ignore[arg-type]
    if choice == "9":
        return _run_subprocess(["journalctl", "--user", "-u", "investrobot-outbox", "-n", "100", "-e"])  # type: ignore[arg-type]
    return 0


def main() -> int:
    while True:
        print("\n=== investRobot — Мастер-скрипт ===")
        print("  1) Запустить торговую систему")
        print("  2) Запустить торговую систему (ограниченное время)")
        print("  3) Многоаккаунтный режим")
        print("  4) Сбор рыночных данных → SQLite")
        print("  5) Сбор данных → запустить в фоне (detached)")
        print("  6) Оптимизация параметров")
        print("  7) Тесты (pytest)")
        print("  8) Песочница: пополнение счёта")
        print("  9) Просмотр БД (последние записи)")
        print("  10) Загрузка исторических данных")
        print("  11) Сбор данных → остановить (stop)")
        print("  12) Сбор данных → статус")
        print("  13) Outbox → запустить в фоне")
        print("  14) Outbox → остановить")
        print("  15) Outbox → статус")
        print("  16) Linux: сервисы (systemd)")
        print("  0) Выход")

        choice = input("> ").strip()
        try:
            if choice == "1":
                return asyncio.run(_start_trading()) or 0
            if choice == "2":
                return asyncio.run(_start_trading_limited()) or 0
            if choice == "3":
                _multi_account_menu()
            elif choice == "4":
                _run_market_ingestor()
            elif choice == "5":
                _run_market_ingestor_daemon()
            elif choice == "6":
                _run_optimization()
            elif choice == "7":
                _run_tests_pytest()
            elif choice == "8":
                _sandbox_payin()
            elif choice == "9":
                _view_db_summary()
            elif choice == "10":
                _load_historical()
            elif choice == "11":
                _stop_market_ingestor_daemon()
            elif choice == "12":
                _status_market_ingestor_daemon()
            elif choice == "13":
                _run_outbox_daemon()
            elif choice == "14":
                _stop_outbox_daemon()
            elif choice == "15":
                _status_outbox_daemon()
            elif choice == "16":
                _systemd_menu()
            elif choice == "0":
                return 0
            else:
                print("Неизвестная команда")
        except KeyboardInterrupt:
            print("\nОстановка по запросу пользователя")
            return 130
        except Exception as e:
            print(f"Ошибка: {e}")


if __name__ == "__main__":
    raise SystemExit(main())


