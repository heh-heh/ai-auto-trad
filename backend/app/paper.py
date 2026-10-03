from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class Position:
    symbol: str
    quantity: int = 0
    avg_price: float = 0.0


@dataclass
class PaperTrade:
    id: int
    symbol: str
    side: str
    quantity: int
    price: float
    notional: float
    timestamp: str


class PaperBroker:
    def __init__(self, initial_cash: float = 10_000_000):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[PaperTrade] = []
        self._next_trade_id = 1

    def reset(self):
        self.cash = self.initial_cash
        self.positions.clear()
        self.trades.clear()
        self._next_trade_id = 1

    def _position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        return self.positions[symbol]

    def buy(self, symbol: str, quantity: int, price: float) -> PaperTrade:
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")
        notional = quantity * price
        if notional > self.cash:
            raise ValueError("insufficient paper cash")
        p = self._position(symbol)
        total = p.avg_price * p.quantity + notional
        p.quantity += quantity
        p.avg_price = total / p.quantity
        self.cash -= notional
        return self._record(symbol, "BUY", quantity, price, notional)

    def sell(self, symbol: str, quantity: int, price: float) -> PaperTrade:
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")
        p = self._position(symbol)
        if p.quantity < quantity:
            raise ValueError("insufficient paper position")
        notional = quantity * price
        p.quantity -= quantity
        if p.quantity == 0:
            p.avg_price = 0.0
        self.cash += notional
        return self._record(symbol, "SELL", quantity, price, notional)

    def _record(self, symbol, side, quantity, price, notional):
        trade = PaperTrade(
            id=self._next_trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            notional=notional,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._next_trade_id += 1
        self.trades.append(trade)
        return trade

    def snapshot(self, prices: dict[str, float] | None = None):
        prices = prices or {}
        holdings = []
        market_value = 0.0
        for p in self.positions.values():
            if p.quantity <= 0:
                continue
            current = float(prices.get(p.symbol, p.avg_price))
            value = p.quantity * current
            market_value += value
            holdings.append({
                **asdict(p),
                "current_price": current,
                "market_value": value,
                "unrealized_pnl": (current - p.avg_price) * p.quantity,
            })
        equity = self.cash + market_value
        return {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "market_value": market_value,
            "equity": equity,
            "total_pnl": equity - self.initial_cash,
            "return_pct": (equity / self.initial_cash - 1) * 100,
            "holdings": holdings,
            "trades": [asdict(t) for t in reversed(self.trades)],
        }
