"""
Фабрика для создания API клиентов
"""
from typing import Optional
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient


class APIClientFactory:
    """Фабрика для создания и инициализации API клиентов"""
    
    @staticmethod
    def create_tinkoff_client(token: str, account_id: str, sandbox_token: Optional[str] = None) -> TinkoffAPIClient:
        """Создает TinkoffAPIClient"""
        return TinkoffAPIClient(
            token=token,
            account_id=account_id,
            sandbox_token=sandbox_token
        )
    
    @staticmethod
    async def create_initialized_tinkoff_client(token: str, account_id: str, sandbox_token: Optional[str] = None) -> TinkoffAPIClient:
        """Создает и инициализирует TinkoffAPIClient"""
        client = APIClientFactory.create_tinkoff_client(token, account_id, sandbox_token)
        # Инициализируем клиент и проверяем, что services установлен
        await client.__aenter__()
        
        # Проверяем, что инициализация прошла успешно
        if not client.services:
            raise RuntimeError("API клиент не инициализирован: services is None")
            
        return client
