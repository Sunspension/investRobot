#!/usr/bin/env python3
"""
Мастер-скрипт управления investRobot.

Функции:
- Запуск торговой системы (обычный и с ограничением по времени)
- Управление многоаккаунтным режимом
- Инжестор рыночных данных → SQLite
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
    db = _input_nonempty("Путь к БД [data/candles.db]: ", default="data/candles.db")
    seconds = _input_nonempty("Секунд работать [0=беск.] [0]: ", default="0")
    return _run_subprocess([sys.executable, "run_market_ingestor.py", "--figi", figi, "--db", db, "--seconds", seconds])  # type: ignore[arg-type]


def _load_historical():
    return _run_subprocess([sys.executable, "load_historical_data.py"])  # type: ignore[arg-type]


def _run_optimization():
    return _run_subprocess([sys.executable, "optimization/optimizer.py", "--all"])  # type: ignore[arg-type]


def _run_tests_pytest():
    return _run_subprocess([sys.executable, "-m", "pytest", "-q"])  # type: ignore[arg-type]


def _sandbox_payin():
    amount = _input_nonempty("Сумма пополнения (RUB) [100000]: ", default="100000")
    return _run_subprocess([sys.executable, "tools/sandbox_cli.py", "payin", "--amount", amount])  # type: ignore[arg-type]


def main() -> int:
    while True:
        print("\n=== investRobot — Мастер-скрипт ===")
        print("  1) Запустить торговую систему")
        print("  2) Запустить торговую систему (ограниченное время)")
        print("  3) Многоаккаунтный режим")
        print("  4) Инжестор рыночных данных → SQLite")
        print("  5) Загрузка исторических данных")
        print("  6) Оптимизация параметров")
        print("  7) Тесты (pytest)")
        print("  8) Песочница: пополнение счёта")
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
                _load_historical()
            elif choice == "6":
                _run_optimization()
            elif choice == "7":
                _run_tests_pytest()
            elif choice == "8":
                _sandbox_payin()
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


