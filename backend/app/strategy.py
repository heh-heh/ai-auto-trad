from dataclasses import dataclass


@dataclass
class Signal:
    symbol: str
    action: str
    reason: str
    fast_sma: float | None = None
    slow_sma: float | None = None
    rsi: float | None = None


def closes_from(candles: list[dict]) -> list[float]:
    rows = []
    for candle in candles:
        value = candle.get("closePrice", candle.get("close"))
        if value is None:
            continue
        timestamp = candle.get("timestamp", "")
        rows.append((str(timestamp), float(value)))
    rows.sort(key=lambda item: item[0])
    return [value for _, value in rows]


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for i in range(len(values) - period, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


class Strategy:
    """Paper-only SMA + RSI strategy. It always uses the latest candles."""

    def evaluate(self, symbol: str, candles: list[dict]) -> Signal:
        closes = closes_from(candles)
        if len(closes) < 20:
            return Signal(symbol, "HOLD", "not enough candles")
        fast = sma(closes, 5)
        slow = sma(closes, 20)
        current_rsi = rsi(closes, 14)
        assert fast is not None and slow is not None
        if fast > slow * 1.002 and (current_rsi is None or current_rsi < 70):
            action, reason = "BUY", "5-SMA above 20-SMA with RSI below overbought zone"
        elif fast < slow * 0.998 and (current_rsi is None or current_rsi > 30):
            action, reason = "SELL", "5-SMA below 20-SMA with RSI above oversold zone"
        else:
            action, reason = "HOLD", "trend/RSI conditions are neutral"
        return Signal(symbol, action, reason, fast, slow, current_rsi)

    def indicators(self, candles: list[dict]) -> dict:
        closes = closes_from(candles)
        return {"sma5": sma(closes, 5), "sma20": sma(closes, 20), "rsi14": rsi(closes, 14)}
