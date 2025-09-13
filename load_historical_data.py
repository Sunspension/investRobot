#!/usr/bin/env python3
"""
Скрипт для загрузки исторических данных свечей
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from robotlib.utils.candles_loader import load_month_candles_to_db
from robotlib.utils.logger import get_logger
from config_data.config import load_config

logger = get_logger(__name__)

async def main():
    """Загружает исторические данные за последний месяц"""
    
    # Загружаем конфигурацию из .env
    try:
        config = load_config()
        token = config.tcs_client.token
        account_id = config.tcs_client.id
        sandbox_token = config.tcs_client.sandbox_token
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        print("💡 Убедитесь, что файл .env содержит правильные токены Tinkoff API")
        return 1
    
    # Параметры
    figi = "FUTIMOEXF000"
    db_path = "data/candles.db"
    
    # Загружаем данные за последний месяц
    start_date = datetime.now() - timedelta(days=30)
    
    print(f"🚀 Загрузка исторических данных для {figi}")
    print(f"📅 Период: {start_date.strftime('%Y-%m-%d')} - {(start_date + timedelta(days=30)).strftime('%Y-%m-%d')}")
    print(f"💾 База данных: {db_path}")
    print(f"🔑 Используем токен: {token[:10]}...")
    print()
    
    try:
        # Загружаем данные
        saved_count = await load_month_candles_to_db(
            app_name="investRobot",
            account_id=account_id,
            token=token,
            sandbox_token=sandbox_token,
            db_path=db_path,
            figi=figi,
            start_date_inclusive=start_date
        )
        
        print(f"✅ Загружено {saved_count} свечей")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        print("💡 Убедитесь, что файл .env содержит правильные токены Tinkoff API")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
