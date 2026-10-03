from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .config import settings
from .toss import TossClient
from .risk import validate_order
from .paper import PaperBroker
from .strategy import Strategy
import math
import json
import websockets
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

class LiveOrder(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    side: str
    quantity: int = Field(gt=0)
    price: float | None = Field(default=None, gt=0)
    order_type: str = "LIMIT"

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

async def _outbound_ip():
    import httpx
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        return response.json().get("ip")

def _error_summary(error):
    return {"message": str(error), "status_code": getattr(error, "status_code", None), "response": getattr(error, "response_body", None)}

@app.get("/api/toss/diagnostics")
async def toss_diagnostics():
    result = {"credentials_configured": bool(settings.toss_client_id and settings.toss_client_secret), "outbound_ip": None, "oauth": False, "accounts": False, "holdings": False, "price": False, "orderbook": False, "account_seq_configured": bool(settings.toss_account_seq), "errors": {}}
    try:
        result["outbound_ip"] = await _outbound_ip()
    except Exception as e:
        result["errors"]["outbound_ip"] = _error_summary(e)
    try:
        await toss.token()
        result["oauth"] = True
    except Exception as e:
        result["errors"]["oauth"] = _error_summary(e)
        return result
    try:
        accounts = await toss.accounts()
        result["accounts"] = True
        if not result["account_seq_configured"]:
            result["account_seq_configured"] = bool(toss._find_account_seq(accounts))
    except Exception as e:
        result["errors"]["accounts"] = _error_summary(e)
    try:
        await toss.account_seq()
        await toss.holdings()
        result["holdings"] = True
    except Exception as e:
        result["errors"]["holdings"] = _error_summary(e)
    try:
        await toss.price("005930")
        result["price"] = True
    except Exception as e:
        result["errors"]["price"] = _error_summary(e)
    try:
        await toss.orderbook("005930")
        result["orderbook"] = True
    except Exception as e:
        result["errors"]["orderbook"] = _error_summary(e)
    return result

@app.get("/api/toss/status")
async def toss_status():
    try:
        await toss.token()
        account_seq = None
        try:
            account_seq = await toss.account_seq()
        except Exception:
            pass
        return {"connected": True, "account_configured": bool(account_seq), "mode": settings.trading_mode, "live_api_ready": bool(account_seq)}
    except Exception as e:
        return {"connected": False, "account_configured": False, "mode": settings.trading_mode, "error": str(e)}

@app.get("/api/market/{symbol}")
async def market_data(symbol: str, interval: str = "1d"):
    try:
        data = await toss.candles(symbol, interval)
        candles = data.get("result", {}).get("candles", []) if isinstance(data, dict) else []
        if not candles:
            raise RuntimeError("Toss returned no candles")
        normalized = list(reversed(candles))
        signal = strategy.evaluate(symbol, normalized)
        return {"symbol": symbol, "source": "TOSS_LIVE", "candles": normalized, "signal": signal.__dict__, "indicators": strategy.indicators(normalized)}
    except Exception as live_error:
        candles = demo_candles(symbol)
        signal = strategy.evaluate(symbol, candles)
        return {"symbol": symbol, "source": "PAPER_DEMO_FALLBACK", "live_error": _error_summary(live_error), "candles": candles, "signal": signal.__dict__, "indicators": strategy.indicators(candles)}

@app.websocket("/ws/market/{symbol}")
async def market_websocket(websocket: WebSocket, symbol: str):
    await websocket.accept()
    upstream = None
    try:
        token = await toss.token()
        upstream = await websockets.connect("wss://openapi-ws.tossinvest.com/ws/v1", additional_headers={"Authorization": f"Bearer {token}"}, ping_interval=30, ping_timeout=20, close_timeout=5)
        await upstream.send(json.dumps([{"id": "aiat-market"}, {"type": "trade:kr", "codes": [symbol]}, {"type": "orderbook:kr", "codes": [symbol]}]))
        while True:
            await websocket.send_text(await upstream.recv())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "error": _error_summary(e)})
        except Exception:
            pass
    finally:
        if upstream is not None:
            await upstream.close()

@app.get("/api/live/status")
async def live_status():
    configured = bool(settings.toss_client_id and settings.toss_client_secret)
    safe_to_order = (
        settings.trading_mode.lower() == "live"
        and settings.live_trading_enabled
        and bool(settings.live_order_confirm)
        and configured
    )
    return {
        "mode": settings.trading_mode,
        "credentials_configured": configured,
        "live_trading_enabled": settings.live_trading_enabled,
        "live_order_ready": safe_to_order,
        "paper_only": not safe_to_order,
    }

@app.get("/api/live/account")
async def live_account():
    if settings.trading_mode.lower() != "live":
        raise HTTPException(status_code=403, detail="TRADING_MODE is not live")
    try:
        return {"accountSeq": await toss.account_seq(), "holdings": await toss.holdings()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/live/buying-power")
async def live_buying_power(currency: str = "KRW"):
    if settings.trading_mode.lower() != "live":
        raise HTTPException(status_code=403, detail="TRADING_MODE is not live")
    try:
        return await toss.buying_power(currency)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/live/sellable/{symbol}")
async def live_sellable(symbol: str):
    if settings.trading_mode.lower() != "live":
        raise HTTPException(status_code=403, detail="TRADING_MODE is not live")
    try:
        return await toss.sellable_quantity(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/live/orderbook/{symbol}")
async def live_orderbook(symbol: str):
    if settings.trading_mode.lower() != "live":
        raise HTTPException(status_code=403, detail="TRADING_MODE is not live")
    try:
        return await toss.orderbook(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/live/orders")
async def live_orders(status: str = "OPEN"):
    if settings.trading_mode.lower() != "live":
        raise HTTPException(status_code=403, detail="TRADING_MODE is not live")
    if status not in {"OPEN", "CLOSED"}:
        raise HTTPException(status_code=400, detail="status must be OPEN or CLOSED")
    try:
        return await toss.orders(status)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/live/orders/{order_id}")
async def live_order_detail(order_id: str):
    if settings.trading_mode.lower() != "live":
        raise HTTPException(status_code=403, detail="TRADING_MODE is not live")
    try:
        return await toss.order(order_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/live/order")
async def live_order(order: LiveOrder, x_live_confirm: str | None = Header(default=None, alias="X-Live-Confirm")):
    if settings.trading_mode.lower() != "live":
        raise HTTPException(status_code=403, detail="Live order blocked: TRADING_MODE is not live")
    if not settings.live_trading_enabled:
        raise HTTPException(status_code=403, detail="Live trading is disabled")
    if not settings.live_order_confirm:
        raise HTTPException(status_code=503, detail="Live order confirmation is not configured")
    if x_live_confirm != settings.live_order_confirm:
        raise HTTPException(status_code=403, detail="Live order confirmation failed")

    side = order.side.upper()
    order_type = order.order_type.upper()
    if side not in {"BUY", "SELL"}:
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    if order_type not in {"LIMIT", "MARKET"}:
        raise HTTPException(status_code=400, detail="order_type must be LIMIT or MARKET")

    if order_type == "MARKET":
        raise HTTPException(status_code=400, detail="MARKET orders are disabled by the safety layer; use LIMIT orders")
    notional = int(order.quantity * order.price)
    decision = validate_order(notional)
    if not decision.allowed:
        raise HTTPException(status_code=400, detail=decision.reason)

    try:
        daily_loss = await toss.daily_profit_loss_krw()
        if daily_loss <= -abs(settings.max_daily_loss_krw):
            raise HTTPException(status_code=400, detail="MAX_DAILY_LOSS_KRW reached")
        result = await toss.create_order(
            symbol=order.symbol,
            side=side,
            quantity=order.quantity,
            price=order.price,
            order_type=order_type,
        )
        return {"ok": True, "mode": "live", "order": result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

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
