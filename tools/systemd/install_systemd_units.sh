#!/usr/bin/env bash
set -euo pipefail

# Установка user systemd units для investRobot на Linux.
# Создает и активирует два сервиса: market-recorder и outbox-dispatcher.

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PY_BIN="$ROOT_DIR/env/bin/python"
if [ ! -x "$PY_BIN" ]; then
  echo "[warn] venv python не найден по пути: $PY_BIN"
  PY_BIN="$(command -v python3 || true)"
  if [ -z "$PY_BIN" ]; then
    echo "[error] Не найден python3"
    exit 1
  fi
fi

FIGI="${FIGI:-FUTIMOEXF000}"
DB_PATH="$ROOT_DIR/data/market.db"

UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"

cat > "$UNIT_DIR/investrobot-market-recorder.service" <<EOF
[Unit]
Description=investRobot Market Recorder
After=network-online.target

[Service]
WorkingDirectory=$ROOT_DIR
ExecStart=$PY_BIN $ROOT_DIR/run_market_ingestor.py --figi $FIGI --db $DB_PATH --seconds 0
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

cat > "$UNIT_DIR/investrobot-outbox.service" <<EOF
[Unit]
Description=investRobot Outbox Dispatcher
After=network-online.target

[Service]
WorkingDirectory=$ROOT_DIR
ExecStart=$PY_BIN $ROOT_DIR/tools/outbox_dispatcher.py --db $DB_PATH --interval 1.0
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

echo "[info] Units написаны в $UNIT_DIR"
echo "[info] Выполняю enable и запуск (user units)..."
systemctl --user daemon-reload
systemctl --user enable --now investrobot-market-recorder.service
systemctl --user enable --now investrobot-outbox.service

echo "[done] Проверьте статус командой: systemctl --user status investrobot-market-recorder.service"
echo "[done] Логи через journalctl: journalctl --user -u investrobot-market-recorder -f"

# Также создаём template-юниты для мульти-счетов: ожидают env-файлы в ~/.config/investrobot/<instance>.env
cat > "$UNIT_DIR/investrobot-market-recorder@.service" <<EOF
[Unit]
Description=investRobot Market Recorder (%i)
After=network-online.target

[Service]
WorkingDirectory=$ROOT_DIR
EnvironmentFile=%h/.config/investrobot/%i.env
ExecStart=$PY_BIN $ROOT_DIR/run_market_ingestor.py --figi $FIGI --db $DB_PATH --seconds 0
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

cat > "$UNIT_DIR/investrobot-outbox@.service" <<EOF
[Unit]
Description=investRobot Outbox Dispatcher (%i)
After=network-online.target

[Service]
WorkingDirectory=$ROOT_DIR
EnvironmentFile=%h/.config/investrobot/%i.env
ExecStart=$PY_BIN $ROOT_DIR/tools/outbox_dispatcher.py --db $DB_PATH --interval 1.0
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

mkdir -p "$HOME/.config/investrobot"
if [ ! -f "$HOME/.config/investrobot/sample.env" ]; then
  cat > "$HOME/.config/investrobot/sample.env" <<ENV
# Пример env для инстансов template-юнитов
# Имя файла задаётся как %i (instance) в systemd, например: acc1-FUTIMOEXF000.env
# Ниже укажите FIGI и путь к БД для конкретного счёта/инструмента
FIGI=$FIGI
DB_PATH=$DB_PATH
ENV
  echo "[info] Создан пример env: $HOME/.config/investrobot/sample.env"
fi

systemctl --user daemon-reload
echo "[info] Template-юниты готовы. Создайте env-файл ~/.config/investrobot/<instance>.env и активируйте, например:"
echo "       systemctl --user enable --now investrobot-market-recorder@acc1-FUTIMOEXF000.service"
echo "       systemctl --user enable --now investrobot-outbox@acc1-FUTIMOEXF000.service"

