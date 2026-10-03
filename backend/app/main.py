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

app = FastAPI(title="AI Auto Trader", version="0.3.0")
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
        candles.append({
            "timestamp": t.isoformat(),
            "openPrice": round(open_price),
            "highPrice": round(high),
            "lowPrice": round(low),
            "closePrice": round(close),
            "volume": int(100000 + abs(math.sin(i / 5)) * 180000),
            "currency": "KRW",
        })
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
    return paper.snapshot()

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
    return {"symbol": symbol, "source": "PAPER_DEMO", "candles": candles, "signal": signal.__dict__}

@app.get("/api/paper/signal/{symbol}")
async def paper_signal(symbol: str):
    signal = strategy.evaluate(symbol, demo_candles(symbol))
    return signal.__dict__

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
