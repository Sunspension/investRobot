"""
Dash визуализатор событий торговой системы (чистая Event-Driven архитектура)
с интеграцией богатого UI из TradingVisualizerAdapter
"""
import asyncio
import threading
import time
import json
import concurrent.futures
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
from robotlib.trading.events import TradingEvent, EventType
from visualization.event_visualizer_interface import EventVisualizerable, VisualizationSinkable
from visualization.data_manager import DataManager
from visualization.chart_builder import ChartBuilder
from visualization.ui_components import UIComponents
from visualization.logging_config import disable_verbose_logging, QuietFlaskServer
from robotlib.utils.logger import get_logger
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
from robotlib.utils.money import Money

# Dash импорты
from dash import Dash, dcc, html, Input, Output, State, callback_context
from plotly.graph_objects import Figure


class DashEventVisualizer(EventVisualizerable, VisualizationSinkable):
    """Dash визуализатор событий торговой системы (чистая Event-Driven архитектура)"""
    
    def __init__(
        self, 
        event_bus: object | None = None,
        figi: str = "FUTIMOEXF000", 
        host: str = "127.0.0.1", 
        port: int = 8050,
        start_server: bool = True
    ):
        self._event_bus = event_bus
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
        
        
        # Добавляем мок-данные для демонстрации (отключено)
        # self._add_demo_data()
        
        # Инициализируем портфель с нулевыми значениями (будет обновлен от API)
        self._init_portfolio()

        # Подписки через EventBus удалены; используется прямой sink
        
        # Проверяем, что данные загружены
        data_snapshot = self._data_manager.get_data_snapshot()
        self._logger.debug(f"После инициализации: {len(data_snapshot['candles_data'])} свечей, {data_snapshot['buy_count']} BUY, {data_snapshot['sell_count']} SELL")
        
        # Dash приложение
        self._app = None
        self._server_thread = None
        self._ws_connections = set()
        
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
            # В случае ошибки оставляем нулевые значения

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
    
    # Подписки через EventBus удалены полностью
    
    async def handle_candle_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие свечи"""
        if not self._running:
            return
        
        self._logger.debug("DashEventVisualizer получил событие CANDLE_RECEIVED")
        try:
            candle = event.data.get('candle')
            if candle:
                # Конвертируем свечу в словарь для DataManager
                candle_time = getattr(candle, 'time', datetime.now())
                candle_data = {
                    'time': self._to_moscow_time(candle_time),
                    'open': float(getattr(candle.open, 'units', 0) + getattr(candle.open, 'nano', 0) / 1e9),
                    'high': float(getattr(candle.high, 'units', 0) + getattr(candle.high, 'nano', 0) / 1e9),
                    'low': float(getattr(candle.low, 'units', 0) + getattr(candle.low, 'nano', 0) / 1e9),
                    'close': float(getattr(candle.close, 'units', 0) + getattr(candle.close, 'nano', 0) / 1e9),
                    'volume': getattr(candle, 'volume', 0)
                }
                # Добавляем свечу в менеджер данных
                self._data_manager.add_candle(candle_data)
                self._logger.debug(f"Добавлена свеча: {candle_data['time']} @ {candle_data['close']}")
                
                # Проверяем, что данные сохранились
                data_snapshot = self._data_manager.get_data_snapshot()
                self._logger.debug(f"DataManager: {len(data_snapshot['candles_data'])} свечей, цена: {data_snapshot['current_price']}")
                
                # Push-уведомление в UI
                self._broadcast_ws({"type": "candle", "time": str(candle_data['time']), "price": candle_data['close']})
        except Exception as e:
            self._logger.error(f"Ошибка обработки события свечи: {e}")

    # Прямой приемник от ядра без EventBus
    async def on_candle(self, candle: Any, price: float, figi: str) -> None:
        if not self._running:
            return
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
                # Конвертируем сигнал в словарь для DataManager
                candle = getattr(signal, 'candle', None)
                if candle:
                    # Извлекаем цену из свечи
                    price = Money(candle.close).to_float()
                else:
                    price = 0.0
                
                signal_data = {
                    'time': datetime.now(),
                    'type': 'buy' if getattr(signal, 'histogram', 0) > 0 else 'sell',
                    'strength': abs(getattr(signal, 'histogram', 0)),
                    'macd': getattr(signal, 'macd', 0),
                    'signal_line': getattr(signal, 'signal', 0),
                    'histogram': getattr(signal, 'histogram', 0),
                    'price': price
                }
                # Добавляем сигнал в менеджер данных
                self._data_manager.add_signal(signal_data)
                self._logger.info(f"✅ Добавлен сигнал: {signal_data['type']} (сила: {signal_data['strength']:.4f})")
                
                # Проверяем, что данные сохранились
                data_snapshot = self._data_manager.get_data_snapshot()
                self._logger.info(f"📊 Сигналы в DataManager: BUY={data_snapshot['buy_count']}, SELL={data_snapshot['sell_count']}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события сигнала: {e}")

    async def on_signal(self, signal: Any, figi: str, price: float) -> None:
        if not self._running:
            return
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
            # Можно отправить короткий WS сигнал при желании
            # self._broadcast_ws({"type": "signal", "side": signal_data['type'], "price": price})
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
        if not self._running:
            return
        try:
            self._data_manager.update_market_status(status)
            self._broadcast_ws({"type": "market_status", "is_trading": status.get('is_trading', False)})
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
            # Устанавливаем флаг запуска сразу, чтобы события обрабатывались
            self._running = True
            
            # Подписки через EventBus не используются

            # Загружаем данные портфеля от API
            await self._load_portfolio_from_api()

            # Немедленно обновляем статус рынка из API без кэша, чтобы UI не показывал "рынок закрыт"
            # Пока нет явного API в DataManager для статуса рынка, просто логируем актуальный статус
            try:
                from robotlib.utils.market_hours import get_market_status_with_api
                market_status = await get_market_status_with_api()
                self._logger.info(f"Статус рынка при старте визуализатора: is_trading={market_status.get('is_trading', False)}")
            except Exception as e:
                self._logger.warning(f"Не удалось получить статус рынка при старте визуализатора: {e}")
            
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
            
            self._logger.info("Dash визуализатор событий остановлен")
            
        except Exception as e:
            self._logger.error(f"Ошибка остановки визуализатора: {e}")
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        return self._running
    
    def _create_dash_app(self) -> Dash:
        """Создает Dash приложение с богатым UI"""
        app = Dash(__name__)
        
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
        self._setup_callbacks(app)

        # WebSocket endpoint для push-уведомлений
        try:
            from flask_sock import Sock
            sock = Sock(app.server)

            @sock.route('/ws')
            def _ws_endpoint(ws):
                try:
                    self._logger.info("WS клиент подключен")
                    self._ws_connections.add(ws)
                    while True:
                        msg = ws.receive()
                        if msg is None:
                            break
                except Exception as e:
                    self._logger.debug(f"WS соединение закрыто: {e}")
                finally:
                    if ws in self._ws_connections:
                        self._ws_connections.discard(ws)
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
        
        # Принудительно вызываем callback при создании приложения
        self._logger.debug("Принудительно вызываем callback при создании приложения")
        try:
            # Получаем данные и создаем график
            data_snapshot = self._data_manager.get_data_snapshot()
            self._logger.debug(f"При создании приложения: {len(data_snapshot['candles_data'])} свечей")
            
            # Создаем график
            fig = self._chart_builder.create_trading_chart(
                candles_data=data_snapshot['candles_data'],
                signals_data=data_snapshot['signals_data'],
                orders_data=data_snapshot['orders_data'],
                current_price=data_snapshot['current_price']
            )
            self._logger.debug("График создан при инициализации")
        except Exception as e:
            self._logger.error(f"❌ Ошибка при создании графика: {e}")
        
        # Убираем принудительный вызов callback'а - исправим основной callback
        
        # Убираем принудительный вызов callback'а - исправим основной callback
        
        return app

    def _broadcast_ws(self, payload: Dict[str, Any]) -> None:
        """Рассылает сообщение всем WS-клиентам"""
        if not self._ws_connections:
            return
        message = json.dumps(payload, default=str)
        dead = []
        for ws in list(self._ws_connections):
            try:
                ws.send(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._ws_connections.discard(ws)
    
    def _create_layout(self) -> html.Div:
        """Создает макет приложения с богатым UI из TradingVisualizerAdapter"""
        return self._ui_components._create_layout()
    
    def _setup_callbacks(self, app: Dash) -> None:
        """Настраивает callbacks для обновления данных с богатым UI"""
        
        @app.callback(
            [Output('trading-graph', 'figure'),
             Output('current-price', 'children'),
             Output('market-status', 'children'),
             Output('buy-signals-count', 'children'),
             Output('sell-signals-count', 'children'),
             Output('buy-orders-count', 'children'),
             Output('sell-orders-count', 'children'),
             Output('total-orders-count', 'children'),
             Output('strategy-status', 'children'),
             Output('trading-status', 'children'),
             Output('signals-list', 'children'),
             Output('recent-signals', 'children'),
             Output('portfolio-balance', 'children'),
             Output('portfolio-pnl', 'children'),
             Output('portfolio-variation-margin', 'children'),
             Output('portfolio-guarantee-deposit', 'children')],
            [Input('ws', 'message')],
            [State('simulation-state', 'data')],
            prevent_initial_call=False
        )
        def update_display(ws_message, state):
            """Обновляет отображение данных с богатым UI"""
            try:
                self._logger.debug("Callback вызван по WebSocket сообщению")
                
                # Получаем снимок данных
                data_snapshot = self._data_manager.get_data_snapshot()
                self._logger.debug(f"DataManager: {len(data_snapshot['candles_data'])} свечей, BUY={data_snapshot['buy_count']}, SELL={data_snapshot['sell_count']}")
                self._logger.debug(f"Портфель: {data_snapshot['portfolio_data']}")
                self._logger.debug(f"Стратегии: {data_snapshot['strategies_data']}")
                
                # Проверяем, что данные действительно есть
                if len(data_snapshot['candles_data']) == 0:
                    self._logger.warning("⚠️ НЕТ СВЕЧЕЙ В DATAMANAGER! Демо-данные отключены")
                    # self._add_demo_data()  # Отключено
                    # data_snapshot = self._data_manager.get_data_snapshot()
                    # self._logger.info(f"📊 После принудительного добавления: {len(data_snapshot['candles_data'])} свечей")
                
                # Создаем график
                fig = self._chart_builder.create_trading_chart(
                    candles_data=data_snapshot['candles_data'],
                    signals_data=data_snapshot['signals_data'],
                    orders_data=data_snapshot['orders_data'],
                    current_price=data_snapshot['current_price']
                )
                
                # Создаем списки сигналов
                signals_list = self._ui_components.create_signals_list(data_snapshot['signals_data'])
                recent_signals = self._ui_components.create_recent_signals(data_snapshot['signals_data'])
                
                # Получаем информацию о состоянии рынка
                market_info = self._get_market_status_info()
                
                if isinstance(market_info, dict):
                    # Форматируем информацию о рынке более читаемо
                    status = market_info.get('status', 'Неизвестно')
                    session_info = market_info.get('session_info', '')
                    next_session = market_info.get('next_session', '')
                    
                    # Создаем красивое отображение с HTML компонентами
                    if session_info and session_info != "Торговая сессия активна":
                        if session_info.startswith('<br>'):
                            # Убираем <br> и создаем HTML компонент
                            clean_session_info = session_info[4:]  # убираем <br>
                            enhanced_market_status = [
                                html.Span(status),
                                html.Br(),
                                html.Span(clean_session_info)
                            ]
                        else:
                            enhanced_market_status = f"{status} {session_info}"
                        if next_session:
                            if isinstance(enhanced_market_status, list):
                                enhanced_market_status.append(html.Span(f" • {next_session}"))
                            else:
                                enhanced_market_status += f" • {next_session}"
                    else:
                        enhanced_market_status = f"{status} {next_session}"
                else:
                    # Если это HTML элементы, используем их напрямую
                    enhanced_market_status = market_info
                
                # Получаем данные портфеля
                portfolio_data = data_snapshot.get('portfolio_data', {})
                self._logger.info(f"📊 Portfolio data в callback: {portfolio_data}")
                portfolio_balance = f"{portfolio_data.get('total_amount', 0):.2f} ₽"
                
                # P&L с динамическим цветом
                pnl_value = portfolio_data.get('pnl', 0)
                portfolio_pnl = f"{pnl_value:.2f} ₽"
                
                portfolio_variation_margin = f"{portfolio_data.get('variation_margin', 0):.2f} ₽"
                portfolio_guarantee_deposit = f"{portfolio_data.get('guarantee_deposit', 0):.2f} ₽"
                
                # Создаем статус стратегий
                strategy_status = self._get_strategy_status()
                
                # Создаем торговый статус
                trading_status = self._get_trading_status()
                
                # Безопасное получение current_price
                current_price = data_snapshot.get('current_price', 0.0)
                if current_price is None:
                    current_price = 0.0
                
                result = (
                    fig,
                    f"{float(current_price):.1f} ₽",
                    enhanced_market_status,
                    str(data_snapshot['buy_count']),  # buy-signals-count
                    str(data_snapshot['sell_count']), # sell-signals-count
                    str(data_snapshot.get('buy_orders_count', 0)),  # buy-orders-count
                    str(data_snapshot.get('sell_orders_count', 0)), # sell-orders-count
                    str(data_snapshot['orders_count']),  # total-orders-count
                    strategy_status,
                    trading_status,
                    signals_list,
                    recent_signals,
                    portfolio_balance,
                    portfolio_pnl,
                    portfolio_variation_margin,
                    portfolio_guarantee_deposit
                )
                
                return result
                
            except Exception as e:
                import traceback
                self._logger.error(f"Ошибка обновления отображения: {e}")
                self._logger.error(f"Traceback: {traceback.format_exc()}")
                return (Figure(), "Ошибка", "❌ Ошибка", "0", "0", "0", "0", "0",
                       [html.P("Ошибка отображения")], [html.P("Ошибка отображения")], 
                       [html.P("Ошибка отображения")], [html.P("Ошибка отображения")],
                       "0.00 ₽", "0.00 ₽", "0.00 ₽", "0.00 ₽")
        
        # Дополнительный callback для принудительного обновления при загрузке
        # Удален триггер на interval-component (polling отключен)
        
        # Убираем Force callback - используем только основной callback
        
        # Callback для динамического цвета P&L
        @app.callback(
            Output('portfolio-pnl', 'style'),
            [Input('ws', 'message')],
            prevent_initial_call=False
        )
        def update_pnl_color(_msg):
            """Обновляет цвет P&L в зависимости от значения"""
            try:
                data_snapshot = self._data_manager.get_data_snapshot()
                portfolio_data = data_snapshot.get('portfolio_data', {})
                pnl_value = portfolio_data.get('pnl', 0)
                
                # Определяем цвет на основе значения P&L
                if pnl_value > 0:
                    color = '#28a745'  # Зеленый для прибыли
                elif pnl_value < 0:
                    color = '#dc3545'  # Красный для убытка
                else:
                    color = '#6c757d'  # Серый для нуля
                
                return {'color': color}
            except Exception as e:
                self._logger.error(f"Ошибка обновления цвета P&L: {e}")
                return {'color': '#6c757d'}  # Серый по умолчанию
        
        # Callback для динамического цвета вариационной маржи
        @app.callback(
            Output('portfolio-variation-margin', 'style'),
            [Input('ws', 'message')],
            prevent_initial_call=False
        )
        def update_variation_margin_color(_msg):
            """Обновляет цвет вариационной маржи в зависимости от значения"""
            try:
                data_snapshot = self._data_manager.get_data_snapshot()
                portfolio_data = data_snapshot.get('portfolio_data', {})
                variation_margin_value = portfolio_data.get('variation_margin', 0)
                
                # Определяем цвет на основе значения вариационной маржи
                if variation_margin_value > 0:
                    color = '#28a745'  # Зеленый для положительной вариационной маржи
                elif variation_margin_value < 0:
                    color = '#dc3545'  # Красный для отрицательной вариационной маржи
                else:
                    color = '#6c757d'  # Серый для нуля
                
                return {'color': color}
            except Exception as e:
                self._logger.error(f"Ошибка обновления цвета вариационной маржи: {e}")
                return {'color': '#6c757d'}  # Серый по умолчанию
    
    def _get_market_status(self) -> Dict[str, Any]:
        """Получает статус рынка"""
        try:
            # Проверяем кэш
            if (self._market_status_cache and 
                self._last_cache_update and 
                time.time() - self._last_cache_update < self._cache_ttl):
                return self._market_status_cache
            
            # Получаем актуальный статус
            try:
                loop = asyncio.get_event_loop()
                status = loop.run_until_complete(get_market_status_enhanced())
            except RuntimeError:
                # Если нет event loop, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    status = loop.run_until_complete(get_market_status_enhanced())
                finally:
                    loop.close()
            
            # Обновляем кэш
            self._market_status_cache = status
            self._last_cache_update = time.time()
            
            return status
            
        except Exception as e:
            self._logger.error(f"Ошибка получения статуса рынка: {e}")
            return {"is_trading": False, "status": "Ошибка"}
    
    def _get_market_status_info(self):
        """Получает информацию о состоянии рынка"""
        try:
            self._logger.info("🔍 Вызываем _get_market_status_info()")
            
            # Используем функцию get_market_status_enhanced асинхронно
            try:
                loop = asyncio.get_event_loop()
                market_status = loop.run_until_complete(get_market_status_enhanced())
            except RuntimeError:
                # Если нет event loop, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    market_status = loop.run_until_complete(get_market_status_enhanced())
                finally:
                    loop.close()
            
            current_time = datetime.now()
            
            if market_status.get('is_trading', False):
                return {
                    'is_trading': True,
                    'status': '🟢 Открыт',
                    'current_time': current_time,
                    'session_info': '📈 Торги идут'
                }
            else:
                # Используем время до открытия из market_hours_enhanced
                time_until_open = market_status.get('time_until_next', 'Неизвестно')
                
                return {
                    'is_trading': False,
                    'status': '🔴 Рынок закрыт',
                    'current_time': current_time,
                    'session_info': f'<br>До открытия: {time_until_open}'
                }
        except Exception as e:
            self._logger.error(f"Ошибка получения статуса рынка: {e}")
            return {
                'is_trading': False,
                'status': '❌ Ошибка',
                'current_time': datetime.now(),
                'session_info': '❌ Ошибка получения статуса'
            }
    
    
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