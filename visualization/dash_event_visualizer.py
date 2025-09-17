"""
Dash визуализатор событий торговой системы
"""
import asyncio
import threading
import json
from typing import Any, Dict
from datetime import datetime
from visualization.event_visualizer_interface import EventVisualizerable, VisualizationSinkable
from visualization.data_manager import DataManager
from visualization.chart_builder import ChartBuilder
from visualization.ui_components import UIComponents
from visualization.logging_config import disable_verbose_logging, QuietFlaskServer
from visualization.services.market_status_service import MarketStatusService
from visualization.channels.ws import WebSocketHub
from visualization.callbacks.core_callbacks import register_core_callbacks
from visualization.services.portfolio_loader import PortfolioLoader
from visualization.services.historical_loader import HistoricalLoader
from robotlib.utils.logger import get_logger
from robotlib.utils.money import Money
from robotlib.trading.events import TradingEvent
from visualization.adapters.sink_impl import VisualizationSinkAdapter

# Dash импорты
from dash import Dash, html


class DashEventVisualizer(EventVisualizerable, VisualizationSinkable):
    """Dash визуализатор событий торговой системы"""
    
    def __init__(
        self, 
        figi: str = "FUTIMOEXF000", 
        host: str = "127.0.0.1", 
        port: int = 8050,
        start_server: bool = True
    ):
        self._figi = figi
        self._host = host
        self._port = port
        self._start_server = start_server
        self._running = False
        self._logger = get_logger(__name__)
        
        # Создаем компоненты визуализатора
        self._data_manager = DataManager()
        self._chart_builder = ChartBuilder()
        self._ui_components = UIComponents(figi, self._chart_builder)
        
        # Инициализируем портфель с нулевыми значениями (будет обновлен от API)
        self._init_portfolio()

        # Проверяем, что данные загружены
        data_snapshot = self._data_manager.get_data_snapshot()
        self._logger.debug(f"После инициализации: {len(data_snapshot['candles_data'])} свечей, {data_snapshot['buy_count']} BUY, {data_snapshot['sell_count']} SELL")
        
        # Dash приложение
        self._app = None
        self._server_thread = None
        self._ws_hub = WebSocketHub()
        self._market_status_service = MarketStatusService()
        
        # Кэш для API данных
        self._market_status_cache = None
        self._last_cache_update = None
        self._cache_ttl = 5  # Кэш на 5 секунд для отладки

    def _to_moscow_time(self, dt: datetime) -> datetime:
        """Конвертирует время свечи в московский часовой пояс и делает его naive для стабильного отображения.
        Plotly рендерит даты в часовом поясе браузера, поэтому используем naive-дату в МСК.
        """
        try:
            import pytz
            msk = pytz.timezone('Europe/Moscow')
            if dt is None:
                return datetime.now(msk).replace(tzinfo=None)
            if dt.tzinfo is None:
                # считаем, что это UTC
                dt = pytz.utc.localize(dt)
            return dt.astimezone(msk).replace(tzinfo=None)
        except Exception:
            return dt
    
    def _load_historical_data(self) -> None:
        """Загружает исторические данные из базы"""
        try:
            import os
            db_path = os.path.join(os.getcwd(), "data", "candles.db")
            if os.path.exists(db_path):
                self._logger.info(f"🔄 Загружаем исторические данные из {db_path}")
                self._data_manager.load_historical_candles(db_path, self._figi, limit=200)
                self._logger.info(f"✅ Загружено {len(self._data_manager.candles_data)} свечей")
                self._logger.info(f"📊 Сигналы: BUY={self._data_manager.buy_count}, SELL={self._data_manager.sell_count}")
            else:
                self._logger.warning(f"⚠️ База данных не найдена: {db_path}")
        except Exception as e:
            self._logger.error(f"❌ Ошибка загрузки исторических данных: {e}")
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Отключаем избыточные логи
        self._disable_verbose_logging()
        
        # Настраиваем обработчики событий
        self._setup_event_handlers()
    
    def _init_portfolio(self) -> None:
        """Инициализирует портфель с нулевыми значениями"""
        try:
            portfolio_data = {
                'total_amount': 0.0,
                'positions': [],
                'pnl': 0.0,
                'margin': 0.0,
                'free_margin': 0.0,
                'variation_margin': 0.0,
                'guarantee_deposit': 0.0,
                'last_update': datetime.now()
            }
            self._data_manager.update_portfolio(portfolio_data)
            self._logger.debug("Портфель инициализирован с нулевыми значениями")
            
        except Exception as e:
            self._logger.error(f"Ошибка инициализации портфеля: {e}")

    async def _load_portfolio_from_api(self) -> None:
        """Загружает данные портфеля от API"""
        try:
            from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
            from robotlib.trading.portfolio_manager import PortfolioManager
            from config_data.config import load_config
            
            config = load_config()
            
            async with TinkoffAPIClient(
                token=config.tcs_client.token,
                account_id=config.tcs_client.account_id,
                sandbox_token=config.tcs_client.sandbox_token
            ) as api_client:
                portfolio_manager = PortfolioManager(api_client)
                portfolio = await portfolio_manager.get_portfolio()
                
                # Конвертируем данные портфеля в формат для визуализатора
                portfolio_data = {
                    'total_amount': portfolio.total_amount,
                    'positions': [
                        {
                            'figi': pos.figi,
                            'quantity': pos.quantity,
                            'average_price': pos.average_price,
                            'current_price': pos.current_price,
                            'unrealized_pnl': pos.unrealized_pnl,
                            'realized_pnl': pos.realized_pnl
                        }
                        for pos in portfolio.positions
                    ],
                    'pnl': portfolio.pnl,
                    'margin': portfolio.blocked_amount,
                    'free_margin': portfolio.available_amount,
                    'variation_margin': 0.0,  # Пока не реализовано в API
                    'guarantee_deposit': 0.0,  # Пока не реализовано в API
                    'last_update': datetime.now()
                }
                
                self._data_manager.update_portfolio(portfolio_data)
                self._logger.info(f"Портфель загружен от API: {portfolio.total_amount:.2f} ₽, {len(portfolio.positions)} позиций")
                
        except Exception as e:
            self._logger.error(f"Ошибка загрузки портфеля от API: {e}")

    def _add_demo_data(self) -> None:
        """Добавляет демонстрационные данные"""
        try:
            # Добавляем демо-свечи
            import random
            from datetime import datetime, timedelta
            
            base_price = 2900.0
            for i in range(50):  # 50 свечей
                candle_time = datetime.now() - timedelta(minutes=50-i)
                price_change = random.uniform(-5, 5)
                open_price = base_price + price_change
                high_price = open_price + random.uniform(0, 3)
                low_price = open_price - random.uniform(0, 3)
                close_price = open_price + random.uniform(-2, 2)
                volume = random.randint(100, 1000)
                
                base_price = close_price
                
                candle_data = {
                    'time': candle_time,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume
                }
                self._data_manager.add_candle(candle_data)
            
            # Добавляем демо-сигналы
            for i in range(5):
                signal_data = {
                    'time': datetime.now() - timedelta(minutes=i*10),
                    'type': 'buy' if i % 2 == 0 else 'sell',
                    'strength': random.uniform(0.5, 2.0),
                    'macd': random.uniform(-5, 5),
                    'signal_line': random.uniform(-3, 3),
                    'histogram': random.uniform(-2, 2),
                    'price': base_price + random.uniform(-10, 10),  # Добавляем цену
                    'reason': f'MACD сигнал #{i+1}',
                    'quantity': random.randint(1, 10),
                    'strategy': 'LongStrategy' if i % 2 == 0 else 'ShortStrategy'
                }
                self._data_manager.add_signal(signal_data)
            
            # Добавляем демо-портфель
            portfolio_data = {
                'total_amount': 100000.0,
                'positions': [],
                'pnl': 1250.50,
                'margin': 5000.0,
                'free_margin': 95000.0,
                'variation_margin': 2500.0,  # Добавляем вариационную маржу
                'guarantee_deposit': 10000.0,  # Добавляем гарантийное обеспечение
                'last_update': datetime.now()
            }
            self._data_manager.update_portfolio(portfolio_data)
            
            # Добавляем демо-стратегии
            strategies_data = [
                {
                    'name': 'LongStrategy',
                    'position': 0,
                    'income': 0.0
                },
                {
                    'name': 'ShortStrategy', 
                    'position': 0,
                    'income': 0.0
                }
            ]
            self._data_manager.update_strategies_data(strategies_data)
            
            self._logger.info("Демо-данные добавлены успешно")
            
        except Exception as e:
            self._logger.error(f"Ошибка добавления демо-данных: {e}")
    
    
    async def handle_candle_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие свечи"""
        if not self._running:
            return
        
        self._logger.debug("DashEventVisualizer получил событие CANDLE_RECEIVED")
        try:
            candle = event.data.get('candle')
            if candle:
                adapter = VisualizationSinkAdapter(self._data_manager, self._broadcast_ws)
                await adapter.on_candle(candle, 0.0, getattr(candle, 'figi', self._figi))
        except Exception as e:
            self._logger.error(f"Ошибка обработки события свечи: {e}")

    async def on_candle(self, candle: Any, price: float, figi: str) -> None:
        try:
            candle_time = getattr(candle, 'time', datetime.now())
            candle_data = {
                'time': self._to_moscow_time(candle_time),
                'open': float(getattr(candle.open, 'units', 0) + getattr(candle.open, 'nano', 0) / 1e9),
                'high': float(getattr(candle.high, 'units', 0) + getattr(candle.high, 'nano', 0) / 1e9),
                'low': float(getattr(candle.low, 'units', 0) + getattr(candle.low, 'nano', 0) / 1e9),
                'close': float(getattr(candle.close, 'units', 0) + getattr(candle.close, 'nano', 0) / 1e9),
                'volume': getattr(candle, 'volume', 0)
            }
            self._data_manager.add_candle(candle_data)
            if self._running:
                self._broadcast_ws({"type": "candle", "time": str(candle_data['time']), "price": candle_data['close']})
        except Exception as e:
            self._logger.error(f"Ошибка on_candle: {e}")
    
    async def handle_signal_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие сигнала"""
        if not self._running:
            return
        
        try:
            signal = event.data.get('signal')
            if signal:
                adapter = VisualizationSinkAdapter(self._data_manager, self._broadcast_ws)
                price = 0.0
                candle = getattr(signal, 'candle', None)
                if candle:
                    price = Money(candle.close).to_float()
                await adapter.on_signal(signal, getattr(signal, 'figi', 'unknown'), price)
        except Exception as e:
            self._logger.error(f"Ошибка обработки события сигнала: {e}")

    async def on_signal(self, signal: Any, figi: str, price: float) -> None:
        try:
            signal_data = {
                'time': datetime.now(),
                'type': 'buy' if getattr(signal, 'histogram', 0) > 0 else 'sell',
                'strength': abs(getattr(signal, 'histogram', 0)),
                'macd': getattr(signal, 'macd', 0),
                'signal_line': getattr(signal, 'signal', 0),
                'histogram': getattr(signal, 'histogram', 0),
                'price': price
            }
            self._data_manager.add_signal(signal_data)
            # Отправляем короткое WS-сообщение, чтобы UI сразу обновил счетчики
            if self._running:
                self._broadcast_ws({"type": "signal", "side": signal_data['type'], "price": price})
        except Exception as e:
            self._logger.error(f"Ошибка on_signal: {e}")
    
    async def handle_order_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие ордера"""
        if not self._running:
            return
        
        try:
            order_data = event.data
            # Добавляем ордер в менеджер данных
            self._data_manager.add_order(order_data)
            self._logger.debug(f"Добавлен ордер: {event.event_type}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события ордера: {e}")
    
    async def handle_position_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие позиции"""
        if not self._running:
            return
        
        try:
            position_data = event.data
            # Добавляем позицию в менеджер данных
            self._data_manager.add_position(position_data)
            self._logger.debug(f"Добавлена позиция: {event.event_type}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события позиции: {e}")
    
    async def handle_portfolio_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие портфеля"""
        if not self._running:
            return
        
        try:
            portfolio_data = event.data
            # Обновляем данные портфеля
            self._data_manager.update_portfolio(portfolio_data)
            self._logger.debug(f"Обновлен портфель: {event.event_type}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события портфеля: {e}")
    
    async def handle_market_status_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие статуса рынка"""
        if not self._running:
            return
        
        try:
            market_data = event.data
            # Обновляем статус рынка
            self._data_manager.update_market_status(market_data)
            self._logger.debug(f"Обновлен статус рынка: {event.event_type}")
            # Push-уведомление в UI
            self._broadcast_ws({"type": "market_status", "is_trading": market_data.get('is_trading', False)})
        except Exception as e:
            self._logger.error(f"Ошибка обработки события статуса рынка: {e}")

    async def on_market_status(self, status: Dict[str, Any]) -> None:
        try:
            adapter = VisualizationSinkAdapter(self._data_manager, self._broadcast_ws)
            await adapter.on_market_status(status)
        except Exception as e:
            self._logger.error(f"Ошибка on_market_status: {e}")
    
    def _disable_verbose_logging(self) -> None:
        """Отключает избыточные логи"""
        disable_verbose_logging(enable_debug_logs=True)
        # Включаем логи для callback'ов
        import logging
        logging.getLogger('dash').setLevel(logging.INFO)
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    async def start(self) -> None:
        """Запускает визуализатор"""
        if self._running:
            self._logger.warning("Визуализатор уже запущен")
            return
        
        try:
            # До старта UI заполним DataManager актуальным статусом рынка, чтобы не было заглушек
            try:
                from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
                ms = await get_market_status_enhanced()
                self._data_manager.update_market_status(ms)
            except Exception as e:
                self._logger.warning(f"Не удалось предзаполнить статус рынка: {e}")

            # Загружаем данные портфеля от API (через сервис)
            try:
                from config_data.config import load_config
                cfg = load_config()
                await PortfolioLoader().load_into(
                    self._data_manager,
                    token=cfg.tcs_client.token,
                    account_id=cfg.tcs_client.account_id,
                    sandbox_token=cfg.tcs_client.sandbox_token,
                )
            except Exception as e:
                self._logger.warning(f"Не удалось загрузить портфель через сервис: {e}")

            # Устанавливаем флаг запуска, после предзаполнения данных
            self._running = True
            
            # Создаем Dash приложение
            self._app = self._create_dash_app()
            
            # Запускаем сервер только если нужно
            if self._start_server:
                # Запускаем сервер в отдельном потоке
                self._server_thread = threading.Thread(
                    target=self._run_server,
                    daemon=True
                )
                self._server_thread.start()
                
                # Ждем запуска сервера
                await asyncio.sleep(2)
                
                self._logger.info(f"Dash визуализатор событий запущен на http://{self._host}:{self._port}")
            else:
                self._logger.info("Dash визуализатор запущен без сервера (режим тестирования)")
            
            # Запускаем тикер для обновления счетчиков каждую секунду
            self._start_ticker()
            # Параллельно запускаем периодический опрос статуса рынка
            try:
                import asyncio as _asyncio
                _asyncio.create_task(self._periodic_market_status_refresh())
            except Exception as e:
                self._logger.warning(f"Не удалось запустить опрос статуса рынка: {e}")
            
        except Exception as e:
            self._logger.error(f"Ошибка запуска визуализатора: {e}")
            self._running = False
            raise
    
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        if not self._running:
            return
        
        try:
            self._running = False
            
            if self._app:
                # Останавливаем Dash сервер
                try:
                    self._app.server.stop()
                except AttributeError:
                    # В новых версиях Dash может не быть метода stop
                    pass
                self._app = None
            
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=5)
            
            # Останавливаем тикер WS-хаба
            try:
                self._ws_hub.stop_ticker()
            except Exception:
                pass
            
            self._logger.info("Dash визуализатор событий остановлен")
            
        except Exception as e:
            self._logger.error(f"Ошибка остановки визуализатора: {e}")
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        return self._running
    
    def _create_dash_app(self) -> Dash:
        """Создает Dash приложение с богатым UI"""
        app = Dash(__name__, update_title=None, title="Фьючерс на индекс MOEX")
        
        # Отключаем избыточные логи
        app.logger.setLevel('WARNING')
        
        # Настраиваем статические файлы
        app.css.config.serve_locally = True
        app.scripts.config.serve_locally = True
        
        # Добавляем маршрут для статических файлов
        import os
        assets_path = os.path.join(os.path.dirname(__file__), 'assets')
        if os.path.exists(assets_path):
            app.server.add_url_rule('/assets/<path:filename>', 'assets', 
                                  lambda filename: app.server.send_static_file(f'assets/{filename}'))
        
        # Используем кастомный HTML шаблон из UIComponents
        app.index_string = self._ui_components._get_custom_html_template()
        
        # Создаем макет
        app.layout = self._create_layout()
        
        # Настраиваем callbacks
        register_core_callbacks(
            app,
            ui_components=self._ui_components,
            chart_builder=self._chart_builder,
            data_manager=self._data_manager,
            logger=self._logger,
            market_status_service=self._market_status_service,
        )

        # WebSocket endpoint для push-уведомлений
        try:
            from flask_sock import Sock
            sock = Sock(app.server)

            @sock.route('/ws')
            def _ws_endpoint(ws):
                try:
                    self._logger.info("WS клиент подключен")
                    self._ws_hub.add(ws)
                    # Отправляем первичное сообщение, чтобы триггернуть обновление UI
                    try:
                        ws.send(json.dumps({"type": "init"}))
                    except Exception as e:
                        self._logger.debug(f"Не удалось отправить init WS: {e}")
                    while True:
                        msg = ws.receive()
                        if msg is None:
                            break
                except Exception as e:
                    self._logger.debug(f"WS соединение закрыто: {e}")
                finally:
                    self._ws_hub.remove(ws)
                    self._logger.info("WS клиент отключен")
        except Exception as e:
            self._logger.warning(f"Не удалось инициализировать WebSocket: {e}")
        
        # Диагностические эндпоинты для автономной проверки состояния
        try:
            from flask import jsonify
            
            @app.server.get('/_health')
            def _health():
                snapshot = self._data_manager.get_data_snapshot()
                return jsonify({
                    'ok': True,
                    'is_trading': snapshot.get('market_status', {}).get('is_trading', False),
                    'candles_count': len(snapshot.get('candles_data', [])),
                    'buy_signals': snapshot.get('buy_count', 0),
                    'sell_signals': snapshot.get('sell_count', 0)
                })
            
            @app.server.get('/_snapshot')
            def _snapshot():
                snapshot = self._data_manager.get_data_snapshot()
                # Убираем тяжелые поля, если что
                return jsonify(snapshot)
        except Exception as e:
            self._logger.warning(f"Не удалось добавить диагностические эндпоинты: {e}")
        
        # Начальная подгрузка исторических свечей из БД (больше окна)
        try:
            HistoricalLoader().load_into(self._data_manager, self._figi, limit=500)
        except Exception as e:
            self._logger.warning(f"Не удалось загрузить исторические данные: {e}")

        # Прогреем стратегии историческими барами из DataManager без размещения ордеров
        try:
            from robotlib.trading.di_container import TradingSystemContainer  # избегаем циклов импортов в рантайме
        except Exception:
            TradingSystemContainer = None
        try:
            # Если DI доступен и стратегии уже сконфигурированы, прогреем их данными
            # (в обычном запуске прогрев лучше вызывать из раннера после сборки DI)
            pass
        except Exception as e:
            self._logger.debug(f"Прогрев стратегий пропущен: {e}")
        
        # Убираем принудительный вызов callback'а - исправим основной callback
        
        # Убираем принудительный вызов callback'а - исправим основной callback
        
        return app

    def _broadcast_ws(self, payload: Dict[str, Any]) -> None:
        """Рассылает сообщение всем WS-клиентам"""
        self._ws_hub.broadcast(payload)
    
    def _start_ticker(self) -> None:
        """Запускает серверный тикер, который рассылает WS-сообщение раз в секунду."""
        self._ws_hub.start_ticker()

    async def _periodic_market_status_refresh(self) -> None:
        """Периодически обновляет статус рынка и пушит его в UI."""
        while self._running:
            try:
                from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
                ms = await get_market_status_enhanced()
                self._data_manager.update_market_status(ms)
                self._broadcast_ws({"type": "market_status", "is_trading": ms.get('is_trading', False)})
                # Периодически обновляем портфель, чтобы баланс отражал последние сделки
                try:
                    from config_data.config import load_config
                    cfg = load_config()
                    await PortfolioLoader().load_into(
                        self._data_manager,
                        token=cfg.tcs_client.token,
                        account_id=cfg.tcs_client.account_id,
                        sandbox_token=cfg.tcs_client.sandbox_token,
                    )
                except Exception as _e:
                    self._logger.debug(f"Обновление портфеля пропущено: {_e}")
                # Автодогрузка пропущенных свечей из БД, если был разрыв
                try:
                    snapshot = self._data_manager.get_data_snapshot()
                    candles = snapshot.get('candles_data', [])
                    if candles:
                        last_time = candles[-1]['time']
                        from datetime import datetime, timedelta
                        import os
                        db_path = os.path.join(os.getcwd(), "data", "market.db")
                        # если больше 3 минут без новых данных — догружаем из БД окно 15 минут
                        if isinstance(last_time, datetime) and (datetime.now() - last_time) > timedelta(minutes=3):
                            self._logger.info("Автодогрузка пропущенных свечей из БД")
                            self._data_manager.merge_historical_candles(
                                db_path=db_path,
                                figi=self._figi,
                                from_time=last_time,
                                to_time=None,
                            )
                            self._broadcast_ws({"type": "candle_backfill"})
                        # Поиск внутренних разрывов внутри последних 300 баров и догрузка этих окон
                        try:
                            window = candles[-300:] if len(candles) > 300 else candles
                            gap_pairs = []
                            for i in range(1, len(window)):
                                t_prev = window[i-1]['time']
                                t_curr = window[i]['time']
                                if isinstance(t_prev, datetime) and isinstance(t_curr, datetime):
                                    if (t_curr - t_prev).total_seconds() > 90:  # gap > 1.5 мин
                                        gap_pairs.append((t_prev, t_curr))
                            if gap_pairs:
                                self._logger.info(f"Найдены разрывы свечей: {len(gap_pairs)}. Догружаем из БД…")
                                for start, end in gap_pairs[:5]:  # ограничим до 5 окон за цикл
                                    self._data_manager.merge_historical_candles(
                                        db_path=db_path,
                                        figi=self._figi,
                                        from_time=start,
                                        to_time=end,
                                    )
                                self._broadcast_ws({"type": "candle_gap_backfill"})
                        except Exception as __e:
                            self._logger.debug(f"Проверка/догрузка внутренних разрывов пропущена: {__e}")
                    # Обновляем список ордеров из БД за текущий день для текущего FIGI
                    try:
                        import os as _os
                        import sqlite3 as _sqlite3
                        from datetime import datetime as _dt
                        from visualization.formatters import to_moscow_time as _to_msk
                        db_path_orders = _os.path.join(_os.getcwd(), "data", "market.db")
                        with _sqlite3.connect(db_path_orders) as _conn:
                            cur = _conn.cursor()
                            rows = cur.execute(
                                """
                                SELECT time, type, price, quantity, strategy
                                FROM orders
                                WHERE figi = ?
                                  AND date(time,'localtime') = date('now','localtime')
                                ORDER BY time ASC
                                LIMIT 500
                                """,
                                (self._figi,)
                            ).fetchall()
                        orders = []
                        for t, typ, price, qty, strategy in rows:
                            try:
                                dtv = _dt.fromisoformat(t)
                            except Exception:
                                continue
                            orders.append({
                                'time': _to_msk(dtv),
                                'type': (typ or '').lower(),
                                'price': float(price),
                                'quantity': int(qty) if qty is not None else 1,
                                'strategy': strategy,
                            })
                        if orders:
                            self._data_manager.update_orders(orders)
                            # Тригерим обновление UI после синка ордеров
                            self._broadcast_ws({"type": "orders_sync"})
                    except Exception as __e:
                        self._logger.debug(f"Обновление ордеров пропущено: {__e}")
                except Exception as _e:
                    self._logger.debug(f"Автодогрузка пропусков пропущена: {_e}")
            except Exception as e:
                self._logger.debug(f"Ошибка обновления статуса рынка: {e}")
            # Обновляем раз в 30 секунд
            await asyncio.sleep(30)
    
    def _create_layout(self) -> html.Div:
        """Создает макет приложения с богатым UI из TradingVisualizerAdapter"""
        return self._ui_components._create_layout()
    
    def _setup_callbacks(self, app: Dash) -> None:
        """Зарезервировано для совместимости; основные callbacks вынесены."""
    
    # Удалены устаревшие методы статуса рынка: используется MarketStatusService
    
    
    def _get_strategy_status(self):
        """Получает статус стратегий"""
        try:
            # Пытаемся получить данные из DataManager
            data_snapshot = self._data_manager.get_data_snapshot()
            strategies_data = data_snapshot.get('strategies_data', [])
            
            if strategies_data:
                # Создаем детальный статус для каждой стратегии
                strategy_elements = []
                for strategy in strategies_data:
                    strategy_name = strategy.get('name', 'Unknown')
                    position = strategy.get('position', 0)
                    income = strategy.get('income', 0.0)
                    
                    # Определяем тип стратегии и статус
                    if 'Long' in strategy_name:
                        strategy_type = "Лонг"
                        if position > 0:
                            status_text = "Ожидание сигнала на закрытие лонга"
                            color = '#28a745'  # Зеленый для открытой позиции
                        else:
                            status_text = "Ожидание сигнала на открытие лонга"
                            color = '#ffc107'  # Желтый для ожидания
                    elif 'Short' in strategy_name:
                        strategy_type = "Шорт"
                        if position > 0:
                            status_text = "Ожидание сигнала на закрытие шорта"
                            color = '#dc3545'  # Красный для открытой позиции
                        else:
                            status_text = "Ожидание сигнала на открытие шорта"
                            color = '#ffc107'  # Желтый для ожидания
                    else:
                        strategy_type = "Неизвестно"
                        status_text = "Неизвестный статус"
                        color = '#6c757d'  # Серый
                    
                    # Создаем элемент для стратегии
                    strategy_element = html.Div([
                        html.P(f"📊 {strategy_type} стратегия", style={'fontWeight': 'bold', 'marginBottom': '5px', 'textAlign': 'left'}),
                        html.P(f"Позиция: {position}", style={'marginBottom': '2px', 'fontSize': '14px', 'textAlign': 'left'}),
                        html.P(f"Статус: {status_text}", style={'color': color, 'fontSize': '12px', 'textAlign': 'left'})
                    ], style={'marginBottom': '10px', 'padding': '8px', 'border': '1px solid #dee2e6', 'borderRadius': '4px', 'textAlign': 'left'})
                    
                    strategy_elements.append(strategy_element)
                
                return strategy_elements
            else:
                # Fallback - показываем, что стратегии активны
                return [html.P("✅ LongStrategy: Активна", style={'color': '#28a745'}),
                       html.P("✅ ShortStrategy: Активна", style={'color': '#28a745'})]
        except Exception as e:
            self._logger.error(f"Ошибка получения статуса стратегий: {e}")
            return [html.P("❌ Ошибка загрузки стратегий", style={'color': '#dc3545'})]
    
    def _get_trading_status(self):
        """Получает торговый статус"""
        try:
            # Пытаемся получить данные из DataManager
            data_snapshot = self._data_manager.get_data_snapshot()
            candle_count = len(data_snapshot.get('candles_data', []))
            signal_count = data_snapshot.get('buy_count', 0) + data_snapshot.get('sell_count', 0)
            current_price = data_snapshot.get('current_price', 0.0)
            last_update = data_snapshot.get('last_update')
            
            # Форматируем время последнего обновления
            if last_update:
                time_str = last_update.strftime("%H:%M:%S")
            else:
                time_str = "неизвестно"
            
            # Создаем статус на основе данных
            if candle_count > 0:
                if signal_count > 0:
                    status = f"🟢 Торговля активна • {signal_count} сигналов • {candle_count} свечей • {current_price:.2f}₽ • {time_str}"
                else:
                    # Получаем информацию о портфеле
                    portfolio_data = data_snapshot.get('portfolio_data', {})
                    positions_count = len(portfolio_data.get('positions', []))
                    pnl_value = portfolio_data.get('pnl', 0)
                    
                    if positions_count > 0:
                        pnl_sign = "+" if pnl_value >= 0 else ""
                        status = f"🟡 Ожидание сигналов • {candle_count} свечей • {positions_count} позиций • P&L: {pnl_sign}{pnl_value:.2f}₽ • {time_str}"
                    else:
                        orders_count = data_snapshot.get('orders_count', 0)
                        status = f"🟡 Ожидание сигналов • {candle_count} свечей • {orders_count} ордеров • {current_price:.2f}₽ • {time_str}"
            else:
                # Получаем информацию о рынке
                market_info = self._get_market_status_info()
                if isinstance(market_info, dict) and 'status' in market_info:
                    status = market_info['status']
                    if 'session_info' in market_info and market_info['session_info']:
                        status += f" {market_info['session_info']}"
                else:
                    status = "🔄 Подключение к рынку..."
            
            return status
        except Exception as e:
            self._logger.error(f"Ошибка получения торгового статуса: {e}")
            return "❌ Ошибка получения статуса"
    
    def _run_server(self) -> None:
        """Запускает сервер в отдельном потоке"""
        try:
            # Дополнительно отключаем логи в потоке сервера
            with QuietFlaskServer():
                self._app.run(
                    host=self._host,
                    port=self._port,
                    debug=False,
                    use_reloader=False
                )
        except Exception as e:
            self._logger.error(f"Ошибка запуска сервера: {e}")
    
    def set_host_port(self, host: str, port: int) -> None:
        """Устанавливает хост и порт"""
        self._host = host
        self._port = port