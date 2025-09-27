from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from dash import Dash, Input, Output, State, html
from plotly.graph_objects import Figure


class UIStateManager:
    """Менеджер состояния UI для хранения данных между callback'ами"""
    
    def __init__(self):
        self._state = {
            'candles_data': [],
            'signals_data': [],
            'orders_data': [],
            'portfolio_data': {},
            'market_status': {},
            'current_price': 0.0,
            'buy_count': 0,
            'sell_count': 0,
            'last_update': None
        }
    
    def get_state(self):
        return self._state
    
    def update_state(self, new_state):
        self._state.update(new_state)
    
    def append_candle(self, candle):
        self._state['candles_data'].append(candle)
        self._state['current_price'] = candle.get('close', self._state['current_price'])
        self._state['last_update'] = candle.get('time')
    
    def append_signal(self, signal):
        self._state['signals_data'].append(signal)
        if signal.get('type') == 'buy':
            self._state['buy_count'] += 1
        else:
            self._state['sell_count'] += 1

# Глобальный экземпляр менеджера состояния
_ui_state_manager = UIStateManager()

def register_core_callbacks(
    app: Dash,
    *,
    ui_components,
    chart_builder,
    logger,
    market_status_service=None
):
    @app.callback(
        [Output('trading-graph', 'figure'),
         Output('current-price', 'children'),
         Output('market-status', 'children'),
         Output('market-time', 'children'),
         Output('buy-signals-count', 'children'),
         Output('sell-signals-count', 'children'),
         Output('buy-orders-count', 'children'),
         Output('sell-orders-count', 'children'),
         Output('orders-list', 'children'),
         Output('recent-orders', 'children'),
         Output('portfolio-balance', 'children'),
         Output('portfolio-pnl', 'children'),
         Output('portfolio-variation-margin', 'children'),
         Output('portfolio-guarantee-deposit', 'children')],
        [Input('ws_events', 'message')],
        prevent_initial_call=False
    )
    def update_display(ws_message):  # noqa: ANN001
        try:
            logger.debug(f"Callback вызван по WebSocket сообщению: {type(ws_message)} - {ws_message}")
            
            # Извлекаем данные из WebSocket сообщения
            if isinstance(ws_message, dict) and 'data' in ws_message:
                # WebSocket сообщение обернуто в объект с полем 'data'
                import json
                try:
                    data_str = ws_message['data']
                    if isinstance(data_str, str):
                        ws_message = json.loads(data_str)
                    else:
                        ws_message = data_str
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Не удалось распарсить WebSocket данные: {e}")
                    return
            
            # Обрабатываем разные типы WebSocket сообщений
            if isinstance(ws_message, dict):
                msg_type = ws_message.get('type')
                
                if msg_type in ('snapshot', 'init_snapshot'):
                    # Полный снэпшот - обновляем все данные
                    snapshot_data = ws_message.get('data', {})
                    logger.debug(f"Получен снэпшот: candles={len(snapshot_data.get('candles_data', []))}, orders={len(snapshot_data.get('orders_data', []))}, market_status={snapshot_data.get('market_status', {})}")
                    _ui_state_manager.update_state(snapshot_data)
                    logger.debug("Обновлен полный снэпшот данных")
                    updated_state = _ui_state_manager.get_state()
                    logger.debug(f"Новое состояние UI: candles={len(updated_state.get('candles_data', []))}, orders={len(updated_state.get('orders_data', []))}")
                    
                elif msg_type == 'candle_added':
                    # Инкрементальное обновление свечи
                    new_candle = ws_message.get('candle')
                    if new_candle:
                        _ui_state_manager.append_candle(new_candle)
                        logger.debug(f"Добавлена новая свеча: {new_candle.get('time')} @ {new_candle.get('close')}")
                        
                elif msg_type == 'signal_added':
                    # Инкрементальное обновление сигнала
                    new_signal = ws_message.get('signal')
                    if new_signal:
                        _ui_state_manager.append_signal(new_signal)
                        logger.debug(f"Добавлен новый сигнал: {new_signal.get('type')} @ {new_signal.get('price')}")

                elif msg_type == 'delta_batch':
                    # Пакет инкрементов (свечи/сигналы)
                    candles = ws_message.get('candles') or []
                    if candles:
                        for c in candles:
                            _ui_state_manager.append_candle(c)
                        logger.debug(f"Пакет свечей применён: +{len(candles)}")
                    signals = ws_message.get('signals') or []
                    if signals:
                        for s in signals:
                            _ui_state_manager.append_signal(s)
                        logger.debug(f"Пакет сигналов применён: +{len(signals)}")
            
            # Используем текущее состояние для построения UI
            snapshot = _ui_state_manager.get_state()

            # График
            hide_inactive = True
            fig = chart_builder.create_trading_chart(
                candles_data=snapshot['candles_data'],
                orders_data=snapshot['orders_data'],
                current_price=snapshot['current_price'],
                hide_inactive_time=hide_inactive,
            )
            # При догрузке пропусков (backfill) принудительно меняем uirevision, чтобы ось пересчиталась
            try:
                import json as _json
                import time as _time
                msg = None
                if isinstance(ws_message, dict):
                    msg = ws_message
                elif isinstance(ws_message, str):
                    try:
                        msg = _json.loads(ws_message)
                    except Exception:
                        msg = None
                msg_type = (msg or {}).get('type') if isinstance(msg, dict) else None
                if msg_type in {'candle_backfill', 'candle_gap_backfill', 'init'}:
                    fig._layout_obj[u"uirevision"] = f"backfill_{_time.time()}"
            except Exception:
                pass

            # Статус рынка и таймер
            ms = snapshot.get('market_status', {}) or {}
            is_trading = bool(ms.get('is_trading', False))
            session_type = ms.get('session_type', 'unknown')
            session_name = {
                'main': 'Основная сессия',
                'evening': 'Вечерняя сессия',
                'weekend': 'Выходная сессия',
                'clearing': 'Клиринг',
            }.get(session_type, 'Торговая сессия')

            if is_trading:
                time_text = market_status_service.countdown_to_close_text(session_type) if market_status_service else ""
                enhanced_market_status = f"🟢 Открыт • {session_name}"
            else:
                if session_type == 'clearing':
                    time_text = market_status_service.countdown_to_close_text(session_type) if market_status_service else ""
                    enhanced_market_status = "🟡 Клиринг"
                else:
                    time_text = market_status_service.countdown_to_open_text() if market_status_service else ""
                    enhanced_market_status = "🔴 Рынок закрыт"

            # Портфель
            portfolio_data = snapshot.get('portfolio_data', {})
            portfolio_balance = f"{portfolio_data.get('total_amount', 0):.2f} ₽"
            pnl_value = portfolio_data.get('pnl', 0)
            portfolio_pnl = f"{pnl_value:.2f} ₽"
            portfolio_variation_margin = f"{portfolio_data.get('variation_margin', 0):.2f} ₽"
            portfolio_guarantee_deposit = f"{portfolio_data.get('guarantee_deposit', 0):.2f} ₽"

            current_price = snapshot.get('current_price', 0.0) or 0.0

            orders_list = ui_components.create_orders_list(snapshot['orders_data'])
            recent_orders = ui_components.create_recent_orders(snapshot['orders_data'])

            logger.debug(f"Возвращаем данные для UI: current_price={current_price}, candles={len(snapshot['candles_data'])}, orders={len(snapshot['orders_data'])}")
            return (
                fig,
                f"{float(current_price):.1f} ₽",
                enhanced_market_status,
                time_text,
                str(snapshot['buy_count']),
                str(snapshot['sell_count']),
                str(snapshot.get('buy_orders_count', 0)),
                str(snapshot.get('sell_orders_count', 0)),
                orders_list,
                recent_orders,
                portfolio_balance,
                portfolio_pnl,
                portfolio_variation_margin,
                portfolio_guarantee_deposit,
            )
        except Exception as e:  # noqa: ANN001
            import traceback
            logger.error(f"Ошибка обновления отображения: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return (
                Figure(),
                "Ошибка",
                "❌ Ошибка",
                "",
                "0",
                "0",
                "0",
                "0",
                [html.P("Ошибка отображения")],
                [html.P("Ошибка отображения")],
                "0.00 ₽",
                "0.00 ₽",
                "0.00 ₽",
                "0.00 ₽",
            )

    @app.callback(
        Output('portfolio-pnl', 'style'),
        [Input('ws_events', 'message')],
        prevent_initial_call=True,
    )
    def update_pnl_color(ws_message):  # noqa: ANN001
        try:
            # Получаем данные из WebSocket сообщения
            pnl_value = 0
            if isinstance(ws_message, dict) and ws_message.get('type') == 'snapshot':
                snapshot = ws_message.get('data', {})
                pnl_value = snapshot.get('portfolio_data', {}).get('pnl', 0)
            if pnl_value > 0:
                color = '#28a745'
            elif pnl_value < 0:
                color = '#dc3545'
            else:
                color = '#6c757d'
            return {'color': color}
        except Exception:
            return {'color': '#6c757d'}

    @app.callback(
        Output('portfolio-variation-margin', 'style'),
        [Input('ws_events', 'message')],
        prevent_initial_call=True,
    )
    def update_variation_margin_color(ws_message):  # noqa: ANN001
        try:
            # Получаем данные из WebSocket сообщения
            value = 0
            if isinstance(ws_message, dict) and ws_message.get('type') == 'snapshot':
                snapshot = ws_message.get('data', {})
                value = snapshot.get('portfolio_data', {}).get('variation_margin', 0)
            if value > 0:
                color = '#28a745'
            elif value < 0:
                color = '#dc3545'
            else:
                color = '#6c757d'
            return {'color': color}
        except Exception:
            return {'color': '#6c757d'}


