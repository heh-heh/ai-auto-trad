from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .config import settings
from .toss import TossClient
from .risk import validate_order

app = FastAPI(title="AI Auto Trader", version="0.2.0")
origins = [x.strip() for x in settings.allowed_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

toss = TossClient()
trading_enabled = False


class ToggleRequest(BaseModel):
    enabled: bool


@app.get("/health")
async def health():
    return {"ok": True, "mode": settings.trading_mode, "trading_enabled": trading_enabled}


@app.get("/api/toss/status")
async def toss_status():
    try:
        await toss.token()
        account_seq = None
        try:
            account_seq = await toss.account_seq()
        except Exception:
            pass
        return {
            "connected": True,
            "account_configured": bool(account_seq),
            "mode": settings.trading_mode,
        }
    except Exception as e:
        return {
            "connected": False,
            "account_configured": False,
            "mode": settings.trading_mode,
            "error": str(e),
        }


@app.post("/api/trading/toggle")
async def toggle(req: ToggleRequest):
    global trading_enabled
    trading_enabled = req.enabled
    return {"trading_enabled": trading_enabled, "mode": settings.trading_mode}


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


@app.post("/api/order/check")
async def order_check(notional_krw: int):
    decision = validate_order(notional_krw)
    return {"allowed": decision.allowed, "reason": decision.reason}
