#!/usr/bin/env python3
"""
Пошаговая отладка системы
"""
import asyncio
import sys
import os

# Добавляем путь к модулю
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def debug_step_by_step():
    print('🚀 Начинаем пошаговую отладку...')
    
    try:
        print('1️⃣ Загружаем конфигурацию...')
        from config_data.config import load_config
        config = load_config()
        print('✅ Конфигурация загружена')
        
        print('2️⃣ Создаем торговую конфигурацию...')
        from robotlib.trading.trading_config import TradingConfig
        trading_config = TradingConfig(
            figi='FUTIMOEXF000',
            enable_visualization=True
        )
        trading_config.tcs_client = config.tcs_client
        print('✅ Торговая конфигурация создана')
        
        print('3️⃣ Создаем DI контейнер...')
        from robotlib.trading.di_container import TradingSystemContainer
        container = TradingSystemContainer(trading_config)
        print('✅ DI контейнер создан')
        
        print('4️⃣ Собираем торговую систему...')
        trading_system = await container.build_trading_system(host="127.0.0.1", port=8050, start_server=True)
        print('✅ Система собрана успешно!')
        print(f'🚌 EventBus: {type(trading_system["event_bus"]).__name__}')
        print(f'📊 Визуализация: {"включена" if trading_system["visualizer"] else "отключена"}')
        
        print('5️⃣ Получаем SessionController...')
        session_controller = trading_system['session_controller']
        print('✅ SessionController получен')
        
        print('6️⃣ Устанавливаем force_start=True...')
        session_controller._force_start = True
        print('✅ force_start установлен')
        
        print('7️⃣ Запускаем торговую сессию...')
        success = await session_controller.start()
        print(f'✅ Результат запуска: {success}')
        
        if success:
            print('🔄 Система запущена! Визуализатор доступен по адресу: http://127.0.0.1:8050')
            print('⏱️ Ждем 5 секунд...')
            await asyncio.sleep(5)
            print('🛑 Останавливаем систему...')
            await session_controller.stop()
            print('✅ Система остановлена')
        else:
            print('❌ Не удалось запустить систему')
            
    except Exception as e:
        print(f'❌ Ошибка на шаге: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_step_by_step())
