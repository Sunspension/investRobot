#!/usr/bin/env bash
set -euo pipefail

# Удаление user systemd units investRobot (стандартные, не template-инстансы)

UNIT_DIR="$HOME/.config/systemd/user"

echo "[info] Останавливаю сервисы..."
systemctl --user stop investrobot-market-recorder.service || true
systemctl --user stop investrobot-outbox.service || true

echo "[info] Отключаю enable..."
systemctl --user disable investrobot-market-recorder.service || true
systemctl --user disable investrobot-outbox.service || true

echo "[info] Удаляю unit-файлы..."
rm -f "$UNIT_DIR/investrobot-market-recorder.service" || true
rm -f "$UNIT_DIR/investrobot-outbox.service" || true

echo "[info] Перечитываю демон..."
systemctl --user daemon-reload || true

echo "[done] Готово. Для template-инстансов удаляйте *@.service ссылки и выполняйте disable/stop по именам."

