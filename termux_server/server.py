#!/usr/bin/env python3
import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://openapi.tossinvest.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, "backend", ".env")

def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v=line.split("=",1)
            if k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env(ENV_FILE)

CLIENT_ID = os.getenv("TOSS_CLIENT_ID","")
CLIENT_SECRET = os.getenv("TOSS_CLIENT_SECRET","")
ACCOUNT_SEQ = os.getenv("TOSS_ACCOUNT_SEQ","")
MODE = os.getenv("TRADING_MODE","paper")

_token = None
_token_until = 0

def toss_request(method, path, params=None, body=None, account=False):
    global _token, _token_until
    if not _token or time.time() >= _token_until - 30:
        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError("Toss credentials are not configured in backend/.env")
        data = ("grant_type=client_credentials&client_id=" + CLIENT_ID +
                "&client_secret=" + CLIENT_SECRET).encode()
        req = Request(BASE_URL+"/oauth2/token", data=data,
                      headers={"Content-Type":"application/x-www-form-urlencoded"},
                      method="POST")
        with urlopen(req, timeout=10) as r:
            token=json.loads(r.read())
        _token=token["access_token"]
        _token_until=time.time()+int(token.get("expires_in",86400))

    query=""
    if params:
        query="?" + "&".join(f"{k}={str(v)}" for k,v in params.items())
    headers={"Authorization":f"Bearer {_token}"}
    if account:
        if not ACCOUNT_SEQ:
            raise RuntimeError("TOSS_ACCOUNT_SEQ is not configured")
        headers["X-Tossinvest-Account"]=ACCOUNT_SEQ
    data=None
    if body is not None:
        data=json.dumps(body).encode()
        headers["Content-Type"]="application/json"
    try:
        req=Request(BASE_URL+path+query, data=data, headers=headers, method=method)
        with urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except HTTPError as e:
        raw=e.read().decode(errors="replace")
        if e.code == 401:
            _token=None
        raise RuntimeError(f"Toss API {e.code}: {raw[:500]}")

class Handler(BaseHTTPRequestHandler):
    def send_json(self, value, status=200):
        raw=json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Headers","*")
        self.send_header("Access-Control-Allow-Methods","GET,OPTIONS")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_json({"ok":True})

    def do_GET(self):
        p=urlparse(self.path)
        path=p.path
        q=parse_qs(p.query)
        try:
            if path == "/health":
                return self.send_json({"ok":True,"mode":MODE,"trading_enabled":False,"paper_ready":True,"server":"termux"})
            if path == "/api/toss/status":
                if not CLIENT_ID or not CLIENT_SECRET:
                    return self.send_json({"connected":False,"account_configured":False,"mode":MODE,"error":"credentials not configured"})
                toss_request("GET","/api/v1/accounts")
                return self.send_json({"connected":True,"account_configured":bool(ACCOUNT_SEQ),"mode":MODE,"live_api_ready":bool(ACCOUNT_SEQ)})
            if path == "/api/price/" + path.rsplit("/",1)[-1] and path.startswith("/api/price/"):
                symbol=path.rsplit("/",1)[-1]
                return self.send_json(toss_request("GET","/api/v1/prices",{"symbols":symbol}))
            if path.startswith("/api/candles/"):
                symbol=path.rsplit("/",1)[-1]
                interval=q.get("interval",["1d"])[0]
                if interval not in ("1m","1d"):
                    return self.send_json({"error":"interval must be 1m or 1d"},400)
                return self.send_json(toss_request("GET","/api/v1/candles",{"symbol":symbol,"interval":interval}))
            if path.startswith("/api/market/"):
                symbol=path.rsplit("/",1)[-1]
                interval=q.get("interval",["1d"])[0]
                data=toss_request("GET","/api/v1/candles",{"symbol":symbol,"interval":interval})
                return self.send_json({"symbol":symbol,"source":"TOSS_LIVE","candles":data.get("result",{}).get("candles",[]),"raw":data})
            if path == "/api/live/account":
                if MODE.lower()!="live": return self.send_json({"error":"TRADING_MODE is not live"},403)
                return self.send_json({"accountSeq":ACCOUNT_SEQ,"holdings":toss_request("GET","/api/v1/holdings",account=True)})
            if path == "/api/live/orderbook/" + path.rsplit("/",1)[-1] and path.startswith("/api/live/orderbook/"):
                symbol=path.rsplit("/",1)[-1]
                return self.send_json(toss_request("GET","/api/v1/orderbook",{"symbol":symbol}))
            return self.send_json({"error":"not found"},404)
        except Exception as e:
            return self.send_json({"error":str(e)},502)

    def log_message(self, fmt, *args):
        print("[HTTP]", fmt % args)

if __name__ == "__main__":
    port=int(os.getenv("PORT","8000"))
    print("AI Auto Trader - Termux server")
    print("http://127.0.0.1:"+str(port)+"/health")
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
