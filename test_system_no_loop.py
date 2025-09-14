#!/usr/bin/env python3
"""
Тест системы без бесконечного цикла
"""
import asyncio
import sys
import os

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from config_data.config import load_config

async def test_system_no_loop():
    print('🚀 Тестируем систему без бесконечного цикла...')
    
    try:
        # Загружаем конфигурацию
        config = load_config()
        print('✅ Конфигурация загружена')
        
        # Создаем торговую конфигурацию
        trading_config = TradingConfig(
            figi='FUTIMOEXF000',
            enable_visualization=True
        )
        trading_config.tcs_client = config.tcs_client
        print('✅ Торговая конфигурация создана')
        
        # Создаем DI контейнер
        container = TradingSystemContainer(trading_config)
        print('✅ DI контейнер создан')
        
        trading_system = await container.build_trading_system(host="127.0.0.1", port=8050, start_server=True)
        print('✅ Система собрана успешно!')
        print(f'🚌 EventBus: {type(trading_system["event_bus"]).__name__}')
        print(f'📊 Визуализация: {"включена" if trading_system["visualizer"] else "отключена"}')
        
        # Получаем SessionController
        session_controller = trading_system['session_controller']
        print('✅ SessionController получен')
        
        print('🎮 Запускаем торговую сессию с принудительным стартом...')
        
        # Устанавливаем force_start=True
        session_controller._force_start = True
        
        success = await session_controller.start()
        print(f'✅ Результат запуска: {success}')
        
        if success:
            print('🔄 Система запущена! Визуализатор доступен по адресу: http://127.0.0.1:8050')
            print('⏱️ Ждем 10 секунд для получения данных...')
            
            # Ждем 10 секунд вместо бесконечного цикла
            for i in range(10):
                await asyncio.sleep(1)
                print(f'⏱️ Прошло {i+1}/10 секунд...')
            
            print('🛑 Останавливаем систему...')
            await session_controller.stop()
            print('✅ Система остановлена')
        else:
            print('❌ Не удалось запустить систему')
            
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_system_no_loop())
