"""
Dash визуализатор событий торговой системы
"""
import asyncio
import os
import threading
import json
from typing import Dict, Any, Callable
from datetime import datetime
from visualization.event_visualizer_interface import WebSocketEventVisualizerable
from visualization.chart_builder import ChartBuilder
from visualization.ui_components import UIComponents
from visualization.logging_config import QuietFlaskServer
from visualization.logging_config import disable_verbose_logging
from visualization.services.market_status_service import MarketStatusService
from visualization.channels.ws import WebSocketHub
from visualization.callbacks.core_callbacks import register_core_callbacks
from robotlib.utils.logger import get_logger
from robotlib.utils.market_hours_enhanced import get_market_status_enhanced
from visualization.formatters import to_moscow_time

# Dash импорты
from dash import Dash, html


class DashEventVisualizer:
    """Dash визуализатор событий торговой системы"""
    
    def __init__(
        self,
        figi: str = "FUTIMOEXF000",
        host: str = "127.0.0.1",
        port: int = 8050,
        start_server: bool = True,
        *,
        chart_builder: ChartBuilder,
        ui_components: UIComponents,
        ws_hub: WebSocketHub,
        market_status_service: MarketStatusService = None,
    ):
        self._figi = figi
        self._host = host
        self._port = port
        self._start_server = start_server
        self._running = False
        self._logger = get_logger(__name__)
        
        # Зависимости инъецируются извне
        self._chart_builder = chart_builder
        self._ui_components = ui_components
        self._ws_hub = ws_hub
        self._market_status_service = market_status_service
        
        # Инициализируем портфель с нулевыми значениями (будет обновлен от API)
        self._init_portfolio()

        # Callback для отправки снэпшотов по требованию
        self._snapshot_callback = None

        # Данные будут загружены через WebSocket события от TradingToUIBridge
        self._logger.debug("DashEventVisualizer инициализирован, ожидает данные через WebSocket")
    
    def set_snapshot_callback(self, callback: Callable[[], None]) -> None:
        """Устанавливает callback для отправки снэпшотов по требованию"""
        self._snapshot_callback = callback
        self._logger.debug("Snapshot callback установлен в DashEventVisualizer")

    
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
            # Портфель будет обновлен через WebSocket события от TradingToUIBridge
            self._logger.debug("Портфель инициализирован с нулевыми значениями")
            
        except Exception as e:
            self._logger.error(f"Ошибка инициализации портфеля: {e}")
    
    async def handle_market_status_event(self, event: Any) -> None:
        """Обрабатывает событие статуса рынка"""
        if not self._running:
            return
        
        try:
            market_data = event.data
            # Статус рынка будет обновлен через WebSocket события от TradingToUIBridge
            self._logger.debug(f"Обновлен статус рынка: {event.event_type}")
            # Push-уведомление в UI
            self._broadcast_ws({"type": "market_status", "is_trading": market_data.get('is_trading', False)})
        except Exception as e:
            self._logger.error(f"Ошибка обработки события статуса рынка: {e}")

    async def start(self) -> None:
        """Запускает визуализатор"""
        if self._running:
            self._logger.warning("Визуализатор уже запущен")
            return
        try:
            # Настраиваем уровень логирования визуализатора при старте
            try:
                disable_verbose_logging(enable_debug_logs=True)
            except Exception:
                pass
            try:
                ms = await get_market_status_enhanced()
                # Статус рынка будет обновлен через WebSocket события от TradingToUIBridge
            except Exception as e:
                self._logger.warning(f"Не удалось предзаполнить статус рынка: {e}")

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
                asyncio.create_task(self._periodic_market_status_refresh())
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
        assets_path = os.path.join(os.path.dirname(__file__), 'assets')
        if os.path.exists(assets_path):
            app.server.add_url_rule(
                '/assets/<path:filename>',
                'assets',
                lambda filename: app.server.send_static_file(f'assets/{filename}')
            )
        
        # Используем кастомный HTML шаблон из UIComponents
        app.index_string = self._ui_components._get_custom_html_template()
        
        # Создаем макет
        app.layout = self._create_layout()
        
        # Настраиваем callbacks (данные получаем из WebSocket)
        register_core_callbacks(
            app,
            ui_components=self._ui_components,
            chart_builder=self._chart_builder,
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
                    
                    # Мгновенно отправляем снэпшот с данными после подключения
                    if self._snapshot_callback:
                        try:
                            # Вызываем callback напрямую, чтобы не ждать тикера/посредников
                            self._snapshot_callback()
                            self._logger.info("Отправлен снэпшот при подключении WebSocket клиента (синхронно)")
                        except Exception as e:
                            self._logger.warning(f"Не удалось отправить снэпшот при подключении: {e}")
                    
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
                # Данные теперь поступают через WebSocket, возвращаем базовую информацию
                return jsonify({
                    'ok': True,
                    'is_trading': False,  # Будет обновлено через WebSocket
                    'candles_count': 0,   # Будет обновлено через WebSocket
                    'buy_signals': 0,     # Будет обновлено через WebSocket
                    'sell_signals': 0     # Будет обновлено через WebSocket
                })
            
            @app.server.get('/_snapshot')
            def _snapshot():
                # Данные теперь поступают через WebSocket, возвращаем пустой снэпшот
                return jsonify({
                    'candles_data': [],
                    'signals_data': [],
                    'orders_data': [],
                    'portfolio_data': {},
                    'market_status': {},
                    'buy_count': 0,
                    'sell_count': 0
                })
        except Exception as e:
            self._logger.warning(f"Не удалось добавить диагностические эндпоинты: {e}")
        

        # Прогреем стратегии историческими барами из TradingToUIBridge без размещения ордеров
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
                # Статус рынка будет обновлен через WebSocket события от TradingToUIBridge
                self._broadcast_ws({"type": "market_status", "is_trading": ms.get('is_trading', False)})
            except Exception as e:
                self._logger.debug(f"Ошибка обновления статуса рынка: {e}")
            # Обновляем раз в 30 секунд
            await asyncio.sleep(30)
    
    def _create_layout(self) -> html.Div:
        """Создает основной макет приложения с полным UI"""
        return self._ui_components._create_layout()
    
    def _setup_callbacks(self, app: Dash) -> None:
        """Зарезервировано для совместимости; основные callbacks вынесены."""
    
    def _get_strategy_status(self):
        """Получает статус стратегий"""
        try:
            # Данные теперь поступают через WebSocket, возвращаем пустой статус
            strategies_data = []
            
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
            # Данные теперь поступают через WebSocket, возвращаем базовые значения
            candle_count = 0
            signal_count = 0
            current_price = 0.0
            last_update = None
            
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
                    # Данные теперь поступают через WebSocket, используем базовые значения
                    positions_count = 0
                    pnl_value = 0
                    orders_count = 0
                    
                    if positions_count > 0:
                        pnl_sign = "+" if pnl_value >= 0 else ""
                        status = f"🟡 Ожидание сигналов • {candle_count} свечей • {positions_count} позиций • P&L: {pnl_sign}{pnl_value:.2f}₽ • {time_str}"
                    else:
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