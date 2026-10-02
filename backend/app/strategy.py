from dataclasses import dataclass

@dataclass
class Signal:
    symbol: str
    action: str
    reason: str

class Strategy:
    """Initial strategy interface. Real strategies should be backtested before live use."""

    def evaluate(self, symbol: str, candles: list[dict]) -> Signal:
        if len(candles) < 2:
            return Signal(symbol, "HOLD", "not enough candles")
        return Signal(symbol, "HOLD", "strategy not enabled")
