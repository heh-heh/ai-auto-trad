import time
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
            self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
            return self._token

    async def _get(self, path, params=None, account=False):
        token = await self.token()
        headers = {"Authorization": f"Bearer {token}"}

        if account:
            headers["X-Tossinvest-Account"] = await self.account_seq()

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BASE_URL}{path}", headers=headers, params=params)
            if r.status_code == 401:
                await self.token()
                headers["Authorization"] = f"Bearer {self._token}"
                r = await client.get(f"{BASE_URL}{path}", headers=headers, params=params)
            r.raise_for_status()
            return r.json()

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

    async def candles(self, symbol: str, interval: str = "1d"):
        return await self._get(
            "/api/v1/candles",
            {"symbol": symbol, "interval": interval},
        )

    async def holdings(self):
        return await self._get("/api/v1/holdings", account=True)
