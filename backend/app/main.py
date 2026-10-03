from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .config import settings
from .toss import TossClient
from .risk import validate_order
from .paper import PaperBroker
from .strategy import Strategy
import math
from datetime import datetime, timedelta, timezone

app = FastAPI(title="AI Auto Trader", version="0.5.0")
origins = [x.strip() for x in settings.allowed_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

toss = TossClient()
paper = PaperBroker()
strategy = Strategy()
trading_enabled = False

class ToggleRequest(BaseModel):
    enabled: bool

class PaperOrder(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    side: str
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)

class PriceUpdate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    price: float = Field(gt=0)

def demo_candles(symbol: str, count: int = 120):
    base = 72000 if symbol == "005930" else 50000
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    candles = []
    for i in range(count):
        t = now - timedelta(minutes=(count - 1 - i))
        drift = i * 18
        wave = math.sin(i / 7) * 550 + math.sin(i / 17) * 300
        close = base + drift + wave
        open_price = close - math.sin(i * 1.7) * 180
        high = max(open_price, close) + 220
        low = min(open_price, close) - 220
        candles.append({"timestamp": t.isoformat(), "openPrice": round(open_price), "highPrice": round(high), "lowPrice": round(low), "closePrice": round(close), "volume": int(100000 + abs(math.sin(i / 5)) * 180000), "currency": "KRW"})
    return candles

@app.get("/health")
async def health():
    return {"ok": True, "mode": settings.trading_mode, "trading_enabled": trading_enabled, "paper_ready": True}

@app.get("/api/toss/status")
async def toss_status():
    try:
        await toss.token()
        account_seq = None
        try:
            account_seq = await toss.account_seq()
        except Exception:
            pass
        return {"connected": True, "account_configured": bool(account_seq), "mode": settings.trading_mode}
    except Exception as e:
        return {"connected": False, "account_configured": False, "mode": settings.trading_mode, "error": str(e)}

@app.post("/api/trading/toggle")
async def toggle(req: ToggleRequest):
    global trading_enabled
    trading_enabled = req.enabled
    return {"trading_enabled": trading_enabled, "mode": settings.trading_mode}

@app.get("/api/paper/portfolio")
async def paper_portfolio():
    symbols = list(paper.positions.keys())
    prices = {s: demo_candles(s)[-1]["closePrice"] for s in symbols}
    return paper.snapshot(prices)

@app.post("/api/paper/order")
async def paper_order(order: PaperOrder):
    side = order.side.upper()
    if side not in {"BUY", "SELL"}:
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    decision = validate_order(int(order.quantity * order.price))
    if not decision.allowed:
        raise HTTPException(status_code=400, detail=decision.reason)
    try:
        trade = paper.buy(order.symbol, order.quantity, order.price) if side == "BUY" else paper.sell(order.symbol, order.quantity, order.price)
        return {"ok": True, "trade": trade.__dict__, "portfolio": paper.snapshot({order.symbol: order.price})}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/paper/reset")
async def paper_reset():
    paper.reset()
    return {"ok": True, "portfolio": paper.snapshot()}

@app.post("/api/paper/price")
async def paper_price(update: PriceUpdate):
    return {"ok": True, "portfolio": paper.snapshot({update.symbol: update.price})}

@app.get("/api/paper/market/{symbol}")
async def paper_market(symbol: str):
    candles = demo_candles(symbol)
    signal = strategy.evaluate(symbol, candles)
    return {"symbol": symbol, "source": "PAPER_DEMO", "candles": candles, "signal": signal.__dict__, "indicators": strategy.indicators(candles)}

@app.get("/api/paper/signal/{symbol}")
async def paper_signal(symbol: str):
    return strategy.evaluate(symbol, demo_candles(symbol)).__dict__

@app.get("/api/paper/backtest/{symbol}")
async def paper_backtest(symbol: str):
    candles = demo_candles(symbol, 120)
    initial_cash = 1_000_000.0
    cash = initial_cash
    shares = 0
    trades = []
    equity_curve = []
    closed_trade_pnls = []
    entry_price = None
    peak = initial_cash
    max_drawdown_pct = 0.0

    for i in range(20, len(candles)):
        window = candles[:i + 1]
        signal = strategy.evaluate(symbol, window)
        price = float(candles[i]["closePrice"])

        if signal.action == "BUY" and shares == 0:
            qty = int(cash // price)
            if qty:
                cash -= qty * price
                shares = qty
                entry_price = price
                trades.append({"side": "BUY", "price": price, "quantity": qty, "timestamp": candles[i]["timestamp"]})
        elif signal.action == "SELL" and shares > 0:
            cash += shares * price
            if entry_price is not None:
                closed_trade_pnls.append((price - entry_price) * shares)
            trades.append({"side": "SELL", "price": price, "quantity": shares, "timestamp": candles[i]["timestamp"]})
            shares = 0
            entry_price = None

        equity = cash + shares * price
        peak = max(peak, equity)
        drawdown_pct = ((equity - peak) / peak * 100) if peak else 0
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
        equity_curve.append({"timestamp": candles[i]["timestamp"], "equity": round(equity, 2)})

    final_price = float(candles[-1]["closePrice"])
    final_equity = cash + shares * final_price
    win_rate = (sum(1 for x in closed_trade_pnls if x > 0) / len(closed_trade_pnls) * 100) if closed_trade_pnls else 0
    return {
        "symbol": symbol,
        "initial_cash": initial_cash,
        "final_equity": final_equity,
        "pnl": final_equity - initial_cash,
        "return_pct": (final_equity / initial_cash - 1) * 100,
        "max_drawdown_pct": max_drawdown_pct,
        "closed_trades": len(closed_trade_pnls),
        "win_rate": win_rate,
        "open_position": shares,
        "trades": trades,
        "equity_curve": equity_curve,
    }

@app.post("/api/order/check")
async def order_check(notional_krw: int):
    decision = validate_order(notional_krw)
    return {"allowed": decision.allowed, "reason": decision.reason}

@app.get("/api/account")
async def account():
    try:
        return await toss.holdings()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/price/{symbol}")
async def price(symbol: str):
    try:
        return await toss.price(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/candles/{symbol}")
async def candles(symbol: str, interval: str = "1d"):
    if interval not in {"1m", "1d"}:
        raise HTTPException(status_code=400, detail="interval must be 1m or 1d")
    try:
        return await toss.candles(symbol, interval)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
