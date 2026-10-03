import time
import uuid
import httpx
from .config import settings

BASE_URL = "https://openapi.tossinvest.com"


class TossClient:
    def __init__(self):
        self._token = None
        self._token_expires_at = 0.0
        self._account_seq = settings.toss_account_seq or None

    async def token(self):
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token
        if not settings.toss_client_id or not settings.toss_client_secret:
            raise RuntimeError("Toss API credentials are not configured")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{BASE_URL}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.toss_client_id,
                    "client_secret": settings.toss_client_secret,
                },
            )
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + int(data.get("expires_in", 86400))
            return self._token

    async def _request(self, method, path, params=None, json=None, account=False):
        token = await self.token()
        headers = {"Authorization": f"Bearer {token}"}
        if account:
            headers["X-Tossinvest-Account"] = await self.account_seq()

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(
                method,
                f"{BASE_URL}{path}",
                headers=headers,
                params=params,
                json=json,
            )
            if response.status_code == 401:
                self._token = None
                token = await self.token()
                headers["Authorization"] = f"Bearer {token}"
                response = await client.request(
                    method,
                    f"{BASE_URL}{path}",
                    headers=headers,
                    params=params,
                    json=json,
                )
            response.raise_for_status()
            return response.json()

    async def _get(self, path, params=None, account=False):
        return await self._request("GET", path, params=params, account=account)

    async def _post(self, path, json=None, account=False):
        return await self._request("POST", path, json=json, account=account)

    @staticmethod
    def _find_account_seq(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() == "accountseq":
                    return str(item)
                found = TossClient._find_account_seq(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = TossClient._find_account_seq(item)
                if found:
                    return found
        return None

    async def accounts(self):
        return await self._get("/api/v1/accounts")

    async def account_seq(self):
        if self._account_seq:
            return self._account_seq
        data = await self.accounts()
        found = self._find_account_seq(data)
        if not found:
            raise RuntimeError("No usable Toss accountSeq was returned by /api/v1/accounts")
        self._account_seq = found
        return found

    async def price(self, symbol: str):
        return await self._get("/api/v1/prices", {"symbols": symbol})

    async def candles(self, symbol: str, interval: str = "1d", count: int = 100):
        return await self._get(
            "/api/v1/candles",
            {"symbol": symbol, "interval": interval, "count": min(max(count, 1), 200)},
        )

    async def holdings(self):
        return await self._get("/api/v1/holdings", account=True)

    async def daily_profit_loss_krw(self):
        data = await self.holdings()
        value = data.get("result", data) if isinstance(data, dict) else data
        try:
            return float(value["dailyProfitLoss"]["amount"]["krw"])
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("Toss holdings response did not contain dailyProfitLoss.amount.krw")

    async def orders(self, status: str = "OPEN"):
        return await self._get("/api/v1/orders", {"status": status}, account=True)

    async def order(self, order_id: str):
        return await self._get(f"/api/v1/orders/{order_id}", account=True)

    async def buying_power(self, currency: str = "KRW"):
        currency = currency.upper()
        if currency not in {"KRW", "USD"}:
            raise ValueError("currency must be KRW or USD")
        return await self._get("/api/v1/buying-power", {"currency": currency}, account=True)

    async def orderbook(self, symbol: str):
        return await self._get("/api/v1/orderbook", {"symbol": symbol})

    async def sellable_quantity(self, symbol: str):
        return await self._get("/api/v1/sellable-quantity", {"symbol": symbol}, account=True)

    async def create_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float | None = None,
        order_type: str = "LIMIT",
        client_order_id: str | None = None,
    ):
        side = side.upper()
        order_type = order_type.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if order_type not in {"LIMIT", "MARKET"}:
            raise ValueError("order_type must be LIMIT or MARKET")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if order_type == "LIMIT" and (price is None or price <= 0):
            raise ValueError("LIMIT order requires a positive price")

        payload = {
            "clientOrderId": client_order_id or f"aiat-{uuid.uuid4().hex}",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "quantity": str(quantity),
        }
        if order_type == "LIMIT":
            payload["price"] = str(price)

        return await self._post("/api/v1/orders", json=payload, account=True)
