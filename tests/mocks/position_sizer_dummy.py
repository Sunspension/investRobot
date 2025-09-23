class DummySizer:
    async def calculate_position_size(self, signal, current_position: int, figi: str = "FUTIMOEXF000") -> int:
        return 1


