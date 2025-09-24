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
import sqlite3
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PY = PROJECT_ROOT / "env" / "bin" / "python"

# Гарантируем, что корень проекта доступен для импорта модулей конфигурации/клиентов
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config_data.config import load_config  # noqa: E402
from robotlib.utils.money import Money  # noqa: E402

# Избегаем импорта внутренних торговых модулей здесь, чтобы не тянуть лишние зависимости


def _python_executable() -> str:
    """Возвращает путь к python из venv, если он существует, иначе текущий интерпретатор."""
    try:
        if VENV_PY.exists():
            return str(VENV_PY)
    except Exception:
        pass
    return sys.executable


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

    args = [
        _python_executable(),
        "run_trading_system.py",
        "--figi", figi,
        "--host", host,
        "--port", str(port),
    ]
    if not enable_vis:
        args.append("--no-visualization")
    if not start_server:
        args.append("--no-server")

    return _run_subprocess(args)


async def _start_trading_limited():
    """Запуск торговой системы на ограниченное время через venv Python."""
    figi = _input_nonempty("FIGI [FUTIMOEXF000]: ", default="FUTIMOEXF000")
    host = _input_nonempty("Host [127.0.0.1]: ", default="127.0.0.1")
    port = int(_input_nonempty("Port [8050]: ", default="8050"))
    enable_vis = _input_nonempty("Визуализация? (y/n) [y]: ", default="y").lower() == "y"
    start_server = _input_nonempty("Запуск веб-сервера? (y/n) [y]: ", default="y").lower() == "y"
    duration = int(_input_nonempty("Длительность, сек [60]: ", default="60"))

    args = [
        _python_executable(),
        "run_trading_system_limited.py",
        "--figi", figi,
        "--host", host,
        "--port", str(port),
        "--seconds", str(duration),
    ]
    if not enable_vis:
        args.append("--no-visualization")
    if not start_server:
        args.append("--no-server")

    return _run_subprocess(args)


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
        return _run_subprocess([_python_executable(), "run_multi_account.py", "--create-config"])  # type: ignore[arg-type]
    if choice == "2":
        config = _input_nonempty("Путь к accounts_config.json [./accounts_config.json]: ", default="./accounts_config.json")
        return _run_subprocess([_python_executable(), "run_multi_account.py", "--config", config, "--interactive"])  # type: ignore[arg-type]
    if choice == "3":
        config = _input_nonempty("Путь к accounts_config.json [./accounts_config.json]: ", default="./accounts_config.json")
        return _run_subprocess([_python_executable(), "run_multi_account.py", "--config", config, "--daemon"])  # type: ignore[arg-type]
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
    # Предохранитель: не запускаем второй экземпляр, если уже есть инжестор
    try:
        found = False
        try:
            p = subprocess.run(["pgrep", "-fl", "run_market_ingestor.py"], capture_output=True, text=True)
            if p.returncode == 0 and p.stdout.strip():
                lines = [ln for ln in p.stdout.splitlines() if "run_market_ingestor.py" in ln]
                if lines:
                    print("⚠ Обнаружен уже запущенный инжестор:")
                    for ln in lines:
                        print("  ", ln)
                    found = True
        except Exception:
            pass

        # Проверяем PID-файл фонового режима
        pid_path = PROJECT_ROOT / "data" / "market_recorder.pid"
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text().strip())
                os.kill(pid, 0)
                print(f"⚠ Найден активный PID из фонового режима: {pid} (data/market_recorder.pid)")
                found = True
            except Exception:
                # PID-файл устаревший — игнорируем
                pass

        if found:
            print("Не буду запускать второй экземпляр. Остановите существующий через пункт 11 и попробуйте снова.")
            return 1
    except Exception:
        pass

    figi = _input_nonempty("FIGI [FUTIMOEXF000]: ", default="FUTIMOEXF000")
    db = _input_nonempty("Путь к БД [data/market.db]: ", default="data/market.db")
    seconds = _input_nonempty("Секунд работать [0=беск.] [0]: ", default="0")
    return _run_subprocess([_python_executable(), "run_market_ingestor.py", "--figi", figi, "--db", db, "--seconds", seconds])  # type: ignore[arg-type]


def _load_historical():
    return _run_subprocess([_python_executable(), "load_historical_data.py"])  # type: ignore[arg-type]


def _run_optimization():
    return _run_subprocess([_python_executable(), "optimization/optimizer.py", "--all"])  # type: ignore[arg-type]


def _run_tests_pytest():
    return _run_subprocess([_python_executable(), "-m", "pytest", "-q"])  # type: ignore[arg-type]


def _view_db_summary():
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
    # Предохранитель: не запускаем второй экземпляр в фоне, если уже есть инжестор
    try:
        found = False
        try:
            p = subprocess.run(["pgrep", "-fl", "run_market_ingestor.py"], capture_output=True, text=True)
            if p.returncode == 0 and p.stdout.strip():
                lines = [ln for ln in p.stdout.splitlines() if "run_market_ingestor.py" in ln]
                if lines:
                    print("⚠ Обнаружен уже запущенный инжестор:")
                    for ln in lines:
                        print("  ", ln)
                    found = True
        except Exception:
            pass

        pid_path_check = PROJECT_ROOT / "data" / "market_recorder.pid"
        if pid_path_check.exists():
            try:
                pid = int(pid_path_check.read_text().strip())
                os.kill(pid, 0)
                print(f"⚠ Найден активный PID из фонового режима: {pid} (data/market_recorder.pid)")
                found = True
            except Exception:
                pass  # устаревший PID-файл — игнорируем

        if found:
            print("Не буду запускать второй экземпляр. Сначала остановите текущий (пункт 11).")
            return 1
    except Exception:
        pass

    figi = _input_nonempty("FIGI [FUTIMOEXF000]: ", default="FUTIMOEXF000")
    db = _input_nonempty("Путь к БД [data/market.db]: ", default="data/market.db")
    logs_dir = PROJECT_ROOT / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "market_recorder.log"
    pid_path = PROJECT_ROOT / "data" / "market_recorder.pid"

    args = [
        _python_executable(),
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
        _python_executable(),
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
    return _run_subprocess([_python_executable(), "tools/sandbox_cli.py", "payin", "--amount", amount])  # type: ignore[arg-type]


async def _show_portfolio() -> int:
    """Печатает сводку портфеля и позиций напрямую через tinkoff.invest AsyncClient.
    Избегаем импорта торговых модулей проекта, чтобы не тянуть лишние зависимости.
    """
    try:
        from tinkoff.invest import AsyncClient  # локальный импорт
        cfg = load_config()
        async with AsyncClient(token=cfg.tcs_client.token, sandbox_token=cfg.tcs_client.sandbox_token) as client:
            if cfg.tcs_client.sandbox_token:
                pf = await client.sandbox.get_sandbox_portfolio(account_id=cfg.tcs_client.account_id)
            else:
                pf = await client.operations.get_portfolio(account_id=cfg.tcs_client.account_id)
            print("\n=== ПОРТФЕЛЬ ===")
            # В operations.get_portfolio используем total_amount_portfolio
            total_raw = getattr(pf, 'total_amount_portfolio', None) or getattr(pf, 'total_amount', None)
            try:
                total = Money(total_raw).to_float()
            except Exception:
                total = 0.0
            # Свободные деньги (RUB) по Positions API
            try:
                if cfg.tcs_client.sandbox_token:
                    pos = await client.sandbox.get_sandbox_positions(account_id=cfg.tcs_client.account_id)
                else:
                    pos = await client.operations.get_positions(account_id=cfg.tcs_client.account_id)
            except Exception:
                pos = None
            free_cash_rub = 0.0
            try:
                monies = getattr(pos, 'money', []) or getattr(pos, 'money_positions', [])
                for m in monies or []:
                    mv = getattr(m, 'amount', None) or m
                    currency = (getattr(m, 'currency', '') or getattr(mv, 'currency', '') or '').lower()
                    if currency in ('rub', 'rur'):
                        try:
                            free_cash_rub += Money(mv).to_float()
                        except Exception:
                            units = getattr(mv, 'units', None)
                            nano = getattr(mv, 'nano', 0) or 0
                            if units is not None:
                                free_cash_rub += float(units) + float(nano) / 1e9
            except Exception:
                pass

            # Оценим ГО как сумму по открытым фьючерсным позициям (initial margin × лоты)
            positions = getattr(pf, 'positions', []) or []
            go_sum = 0.0
            for p in positions:
                figi = getattr(p, 'figi', '')
                q = getattr(p, 'quantity', None)
                qty = getattr(q, 'units', q) or 0
                try:
                    qty = int(qty)
                except Exception:
                    continue
                if not figi or qty == 0:
                    continue
                # Считаем ГО только для фьючерсов (FIGI обычно начинается с "FUT")
                if not str(figi).startswith('FUT'):
                    continue
                try:
                    fm = await client.instruments.get_futures_margin(figi=figi)
                    buy_mv = getattr(fm, 'initial_margin_on_buy', None)
                    sell_mv = getattr(fm, 'initial_margin_on_sell', None)
                    per_lot = 0.0
                    if buy_mv is not None:
                        per_lot = max(per_lot, Money(buy_mv).to_float())
                    if sell_mv is not None:
                        per_lot = max(per_lot, Money(sell_mv).to_float())
                    if per_lot > 0.0:
                        go_sum += abs(qty) * per_lot
                except Exception:
                    continue

            # ГО по активным заявкам (оценка)
            go_active = 0.0
            try:
                if cfg.tcs_client.sandbox_token:
                    orders_resp = await client.sandbox.get_sandbox_orders(account_id=cfg.tcs_client.account_id)
                    orders = getattr(orders_resp, 'orders', [])
                else:
                    orders_resp = await client.orders.get_orders(account_id=cfg.tcs_client.account_id)
                    orders = getattr(orders_resp, 'orders', [])
                for o in orders or []:
                    ofigi = getattr(o, 'figi', '')
                    lots_req = getattr(o, 'lots_requested', 0)
                    lots = getattr(lots_req, 'units', lots_req) or 0
                    try:
                        lots = int(lots)
                    except Exception:
                        lots = 0
                    if not ofigi or lots <= 0:
                        continue
                    # ГО только для фьючерсов
                    if not str(ofigi).startswith('FUT'):
                        continue
                    try:
                        fm = await client.instruments.get_futures_margin(figi=ofigi)
                        buy_mv = getattr(fm, 'initial_margin_on_buy', None)
                        sell_mv = getattr(fm, 'initial_margin_on_sell', None)
                        per_lot = 0.0
                        if buy_mv is not None:
                            per_lot = max(per_lot, Money(buy_mv).to_float())
                        if sell_mv is not None:
                            per_lot = max(per_lot, Money(sell_mv).to_float())
                        if per_lot > 0.0:
                            go_active += lots * per_lot
                    except Exception:
                        continue
            except Exception:
                pass

            # Доступно к открытию ≈ свободные деньги − ГО активных заявок
            available_for_new = max(0.0, free_cash_rub - go_active)
            print(f"Сумма портфеля: {total:.2f}")
            print(f"Свободные деньги (RUB): {free_cash_rub:.2f}")
            print(f"ГО по позициям (оценка): {go_sum:.2f}")
            print(f"ГО по активным заявкам (оценка): {go_active:.2f}")
            print(f"Доступно для новых позиций: {available_for_new:.2f}")
            print(f"Позиции: {len(positions)}")
            for p in positions[:20]:
                figi = getattr(p, 'figi', '')
                q = getattr(p, 'quantity', None)
                qty = getattr(q, 'units', q)
                try:
                    avg = Money(getattr(p, 'average_position_price', None)).to_float() if hasattr(p, 'average_position_price') else 0.0
                except Exception:
                    avg = 0.0
                print(f" - {figi}: qty={qty} avg={avg}")
        return 0
    except Exception as e:
        print(f"Ошибка получения портфеля: {e}")
        return 1


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
        print("\n📈 ТОРГОВЛЯ:")
        print("  1) Запустить торговую систему")
        print("  2) Запустить торговую систему (ограниченное время)")
        print("  3) Многоаккаунтный режим")
        print("\n📊 ДАННЫЕ:")
        print("  4) Сбор рыночных данных → SQLite")
        print("  5) Сбор данных → запустить в фоне (detached)")
        print("  6) Сбор данных → остановить (stop)")
        print("  7) Сбор данных → статус")
        print("  8) Загрузка исторических данных")
        print("  9) Просмотр БД (последние записи)")
        print("\n⚙️ СИСТЕМА:")
        print("  10) Outbox → запустить в фоне")
        print("  11) Outbox → остановить")
        print("  12) Outbox → статус")
        print("  13) Linux: сервисы (systemd)")
        print("\n🔧 РАЗРАБОТКА:")
        print("  14) Оптимизация параметров")
        print("  15) Тесты (pytest)")
        print("  16) Песочница: пополнение счёта")
        print("\n👤 АККАУНТ:")
        print("  17) Показать портфель")
        print("\n  0) Выход")

        choice = input("> ").strip()
        try:
            # ТОРГОВЛЯ
            if choice == "1":
                return asyncio.run(_start_trading()) or 0
            if choice == "2":
                return asyncio.run(_start_trading_limited()) or 0
            if choice == "3":
                _multi_account_menu()
            # ДАННЫЕ
            elif choice == "4":
                _run_market_ingestor()
            elif choice == "5":
                _run_market_ingestor_daemon()
            elif choice == "6":
                _stop_market_ingestor_daemon()
            elif choice == "7":
                _status_market_ingestor_daemon()
            elif choice == "8":
                _load_historical()
            elif choice == "9":
                _view_db_summary()
            # СИСТЕМА
            elif choice == "10":
                _run_outbox_daemon()
            elif choice == "11":
                _stop_outbox_daemon()
            elif choice == "12":
                _status_outbox_daemon()
            elif choice == "13":
                _systemd_menu()
            # РАЗРАБОТКА
            elif choice == "14":
                _run_optimization()
            elif choice == "15":
                _run_tests_pytest()
            elif choice == "16":
                _sandbox_payin()
            # АККАУНТ
            elif choice == "17":
                return asyncio.run(_show_portfolio()) or 0
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


