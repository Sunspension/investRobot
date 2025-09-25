from __future__ import annotations

from datetime import datetime

from robotlib.utils.logger import get_logger
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.trading.portfolio_manager import PortfolioManager


class PortfolioLoader:
    """Сервис загрузки портфеля из API и адаптации к формату VisualizationDataStore."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    async def load_into(self, data_manager, *, token: str, account_id: str, sandbox_token: str | None) -> None:
        try:
            async with TinkoffAPIClient(
                token=token,
                account_id=account_id,
                sandbox_token=sandbox_token,
            ) as api_client:
                portfolio_manager = PortfolioManager(api_client)
                portfolio = await portfolio_manager.get_portfolio()

                portfolio_data = {
                    'total_amount': portfolio.total_amount,
                    'positions': [
                        {
                            'figi': pos.figi,
                            'quantity': pos.quantity,
                            'average_price': pos.average_price,
                            'current_price': pos.current_price,
                            'unrealized_pnl': pos.unrealized_pnl,
                            'realized_pnl': pos.realized_pnl,
                        }
                        for pos in portfolio.positions
                    ],
                    'pnl': portfolio.pnl,
                    'margin': portfolio.blocked_amount,
                    'free_margin': portfolio.available_amount,
                    'variation_margin': 0.0,
                    'guarantee_deposit': 0.0,
                    'last_update': datetime.now(),
                }

                data_manager.update_portfolio(portfolio_data)
                self._logger.info(
                    f"Портфель загружен от API: {portfolio.total_amount:.2f} ₽, {len(portfolio.positions)} позиций"
                )
        except Exception as e:
            self._logger.error(f"Ошибка загрузки портфеля от API: {e}")
            # В случае ошибки оставляем нулевые значения


