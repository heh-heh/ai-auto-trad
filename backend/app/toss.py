import httpx
from .config import settings

BASE_URL = "https://openapi.tossinvest.com"

class TossClient:
    def __init__(self):
        self._token = None

    async def token(self):
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
            self._token = r.json()["access_token"]
            return self._token

    async def _get(self, path, params=None, account=False):
        if not self._token:
            await self.token()
        headers = {"Authorization": f"Bearer {self._token}"}
        if account:
            if not settings.toss_account_seq:
                raise RuntimeError("TOSS_ACCOUNT_SEQ is not configured")
            headers["X-Tossinvest-Account"] = settings.toss_account_seq
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{BASE_URL}{path}", headers=headers, params=params)
            if r.status_code == 401:
                await self.token()
                headers["Authorization"] = f"Bearer {self._token}"
                r = await client.get(f"{BASE_URL}{path}", headers=headers, params=params)
            r.raise_for_status()
            return r.json()

    async def price(self, symbol: str):
        return await self._get("/api/v1/prices", {"symbol": symbol})

    async def candles(self, symbol: str, interval: str = "1d"):
        return await self._get("/api/v1/candles", {"symbol": symbol, "interval": interval})

    async def accounts(self):
        return await self._get("/api/v1/accounts")

    async def holdings(self):
        return await self._get("/api/v1/holdings", account=True)
