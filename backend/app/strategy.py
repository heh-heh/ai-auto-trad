from dataclasses import dataclass


@dataclass
class Signal:
    symbol: str
    action: str
    reason: str
    fast_sma: float | None = None
    slow_sma: float | None = None


class Strategy:
    """Simple SMA trend signal used only for paper/backtest development."""

    def evaluate(self, symbol: str, candles: list[dict]) -> Signal:
        closes = []
        for c in candles:
            value = c.get("closePrice", c.get("close"))
            if value is not None:
                closes.append(float(value))
        if len(closes) < 20:
            return Signal(symbol, "HOLD", "not enough candles")
        fast = sum(closes[:5]) / 5
        slow = sum(closes[:20]) / 20
        if fast > slow * 1.002:
            action, reason = "BUY", "5-period SMA is above 20-period SMA"
        elif fast < slow * 0.998:
            action, reason = "SELL", "5-period SMA is below 20-period SMA"
        else:
            action, reason = "HOLD", "SMA trend is neutral"
        return Signal(symbol, action, reason, fast, slow)
