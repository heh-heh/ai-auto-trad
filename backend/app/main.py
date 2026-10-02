from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .config import settings
from .toss import TossClient
from .risk import validate_order

app = FastAPI(title="AI Auto Trader", version="0.1.0")
origins = [x.strip() for x in settings.allowed_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

toss = TossClient()
trading_enabled = False

class ToggleRequest(BaseModel):
    enabled: bool

@app.get("/health")
async def health():
    return {"ok": True, "mode": settings.trading_mode, "trading_enabled": trading_enabled}

@app.post("/api/trading/toggle")
async def toggle(req: ToggleRequest):
    global trading_enabled
    # Live trading is intentionally not enabled by this endpoint yet.
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

@app.post("/api/order/check")
async def order_check(notional_krw: int):
    decision = validate_order(notional_krw)
    return {"allowed": decision.allowed, "reason": decision.reason}
