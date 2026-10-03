#!/usr/bin/env python3
import json, os, time, math, secrets, threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE="https://openapi.tossinvest.com"
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV=os.path.join(ROOT,"backend",".env"); STATE_FILE=os.path.join(ROOT,"termux_server","state.json"); TOKEN_FILE=os.path.join(ROOT,"termux_server",".control_token")

def load_env(p):
    if not os.path.exists(p): return
    for line in open(p,encoding="utf-8"):
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))
load_env(ENV)
CLIENT_ID=os.getenv("TOSS_CLIENT_ID",""); CLIENT_SECRET=os.getenv("TOSS_CLIENT_SECRET",""); ACCOUNT_SEQ=os.getenv("TOSS_ACCOUNT_SEQ","")
MODE=os.getenv("TRADING_MODE","paper").lower(); MAX_ORDER=float(os.getenv("MAX_ORDER_KRW","100000")); MAX_DAILY_LOSS=float(os.getenv("MAX_DAILY_LOSS_KRW","50000"))
ORIGINS=[x.strip() for x in os.getenv("ALLOWED_ORIGINS","https://heh-heh.github.io").split(",") if x.strip()]
CONTROL_TOKEN=os.getenv("CONTROL_TOKEN","").strip()
if not CONTROL_TOKEN:
    if os.path.exists(TOKEN_FILE): CONTROL_TOKEN=open(TOKEN_FILE,encoding="utf-8").read().strip()
    else:
        CONTROL_TOKEN=secrets.token_urlsafe(24); open(TOKEN_FILE,"w",encoding="utf-8").write(CONTROL_TOKEN)
        try: os.chmod(TOKEN_FILE,0o600)
        except OSError: pass
        print("CONTROL TOKEN (save for GitHub Pages):",CONTROL_TOKEN)

def defaults():
    return {"paper_cash":10000000.0,"positions":{},"trades":[],"next_trade_id":1,"trading_enabled":False,
            "auto_enabled":False,"auto_symbol":"005930","auto_interval":"1m","auto_order_krw":50000.0,
            "last_auto_candle":"","last_auto_action":"HOLD","last_auto_reason":"","last_error":""}
def load_state():
    try:
        d=json.load(open(STATE_FILE,encoding="utf-8")); s=defaults(); s.update(d); return s
    except Exception: return defaults()
STATE=load_state(); LOCK=threading.RLock()
def save():
    with LOCK:
        tmp=STATE_FILE+".tmp"; json.dump(STATE,open(tmp,"w",encoding="utf-8"),ensure_ascii=False,indent=2); os.replace(tmp,STATE_FILE)

TOKEN=None; TOKEN_UNTIL=0
def find_account(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if k.lower()=="accountseq": return str(x)
            r=find_account(x)
            if r:return r
    elif isinstance(v,list):
        for x in v:
            r=find_account(x)
            if r:return r
    return None
def toss(method,path,params=None,body=None,account=False):
    global TOKEN,TOKEN_UNTIL
    if not TOKEN or time.time()>TOKEN_UNTIL-30:
        if not CLIENT_ID or not CLIENT_SECRET: raise RuntimeError("Toss credentials are not configured")
        data=urlencode({"grant_type":"client_credentials","client_id":CLIENT_ID,"client_secret":CLIENT_SECRET}).encode()
        req=Request(BASE+"/oauth2/token",data=data,headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
        with urlopen(req,timeout=10) as r: d=json.loads(r.read())
        TOKEN=d["access_token"]; TOKEN_UNTIL=time.time()+int(d.get("expires_in",86400))
    url=BASE+path+("?" + urlencode(params) if params else ""); h={"Authorization":"Bearer "+TOKEN}
    if account: h["X-Tossinvest-Account"]=ACCOUNT_SEQ or find_account(toss("GET","/api/v1/accounts"))
    data=json.dumps(body).encode() if body is not None else None
    if body is not None:h["Content-Type"]="application/json"
    try:
        with urlopen(Request(url,data=data,headers=h,method=method),timeout=10) as r:return json.loads(r.read())
    except HTTPError as e:
        raw=e.read().decode(errors="replace")
        if e.code==401:TOKEN=None
        raise RuntimeError(f"Toss API {e.code}: {raw[:500]}")

def candles_of(d):
    return (d.get("result",{}).get("candles",[]) if isinstance(d,dict) else [])
def closes(cs):
    return [float(x.get("closePrice",x.get("close"))) for x in cs if x.get("closePrice",x.get("close")) is not None]
def inds(cs):
    v=closes(cs); sma5=sum(v[-5:])/5 if len(v)>=5 else None; sma20=sum(v[-20:])/20 if len(v)>=20 else None
    if len(v)<=14:r=None
    else:
        g=[];l=[]
        for i in range(len(v)-14,len(v)):
            z=v[i]-v[i-1];g.append(max(z,0));l.append(max(-z,0))
        ag=sum(g)/14;al=sum(l)/14;r=100 if al==0 and ag else 50 if al==0 else 100-100/(1+ag/al)
    return {"sma5":sma5,"sma20":sma20,"rsi14":r}
def signal(cs,symbol):
    d=inds(cs); f,s,r=d["sma5"],d["sma20"],d["rsi14"]
    if f is None or s is None:return {"symbol":symbol,"action":"HOLD","reason":"not enough candles",**d}
    if f>s*1.002 and (r is None or r<70):return {"symbol":symbol,"action":"BUY","reason":"SMA5 above SMA20; RSI below 70",**d}
    if f<s*.998 and (r is None or r>30):return {"symbol":symbol,"action":"SELL","reason":"SMA5 below SMA20; RSI above 30",**d}
    return {"symbol":symbol,"action":"HOLD","reason":"trend/RSI neutral",**d}
def demo(symbol,n=120):
    base=72000 if symbol=="005930" else 50000; now=time.time(); out=[]
    for i in range(n):
        c=base+i*18+math.sin(i/7)*550+math.sin(i/17)*300;o=c-math.sin(i*1.7)*180
        out.append({"timestamp":datetime.fromtimestamp(now-(n-1-i)*60,timezone.utc).isoformat(),"openPrice":round(o),"highPrice":round(max(o,c)+220),"lowPrice":round(min(o,c)-220),"closePrice":round(c),"volume":100000,"currency":"KRW"})
    return out
def market(symbol,interval="1m"):
    try:
        cs=list(reversed(candles_of(toss("GET","/api/v1/candles",{"symbol":symbol,"interval":interval,"count":200}))))
        if not cs:raise RuntimeError("no candles")
        return {"symbol":symbol,"source":"TOSS_LIVE","candles":cs,"signal":signal(cs,symbol),"indicators":inds(cs)}
    except Exception as e:
        cs=demo(symbol);return {"symbol":symbol,"source":"PAPER_DEMO_FALLBACK","live_error":{"message":str(e)},"candles":cs,"signal":signal(cs,symbol),"indicators":inds(cs)}
def price(symbol):
    d=toss("GET","/api/v1/prices",{"symbols":symbol}); rows=d.get("result",[]) if isinstance(d,dict) else []
    return float(rows[0].get("lastPrice",rows[0].get("price"))) if rows else None
def paper_order(symbol,side,qty,p):
    side=side.upper();qty=int(qty);p=float(p);notional=qty*p
    if side not in ("BUY","SELL") or qty<=0 or p<=0:raise ValueError("invalid order")
    if notional>MAX_ORDER:raise ValueError(f"max order is {MAX_ORDER:,.0f} KRW")
    with LOCK:
        pos=STATE["positions"].setdefault(symbol,{"quantity":0,"avg_price":0.0})
        if side=="BUY":
            if notional>STATE["paper_cash"]:raise ValueError("insufficient paper cash")
            q=int(pos["quantity"]);pos["avg_price"]=(pos["avg_price"]*q+notional)/(q+qty);pos["quantity"]=q+qty;STATE["paper_cash"]-=notional
        else:
            if int(pos["quantity"])<qty:raise ValueError("insufficient paper position")
            pos["quantity"]-=qty;STATE["paper_cash"]+=notional
            if pos["quantity"]==0:pos["avg_price"]=0
        t={"id":STATE["next_trade_id"],"symbol":symbol,"side":side,"quantity":qty,"price":p,"notional":notional,"timestamp":datetime.now(timezone.utc).isoformat()}
        STATE["next_trade_id"]+=1;STATE["trades"].append(t);save();return t
def portfolio():
    with LOCK:
        hs=[];mv=0
        for sym,p in STATE["positions"].items():
            q=int(p["quantity"])
            if not q:continue
            try:cur=price(sym)
            except Exception:cur=float(p["avg_price"])
            val=q*cur;mv+=val;hs.append({"symbol":sym,"quantity":q,"avg_price":p["avg_price"],"current_price":cur,"market_value":val,"unrealized_pnl":(cur-p["avg_price"])*q})
        eq=STATE["paper_cash"]+mv
        return {"initial_cash":10000000,"cash":STATE["paper_cash"],"market_value":mv,"equity":eq,"total_pnl":eq-10000000,"return_pct":(eq/10000000-1)*100,"holdings":hs,"trades":list(reversed(STATE["trades"][-100:]))}
def authorized(h):
    if h.client_address and h.client_address[0] in ("127.0.0.1","::1"):return True
    return secrets.compare_digest(h.headers.get("X-Control-Token",""),CONTROL_TOKEN)
def auto_loop():
    while True:
        try:
            with LOCK:a=STATE["auto_enabled"] and STATE["trading_enabled"] and MODE=="paper";sym=STATE["auto_symbol"];iv=STATE["auto_interval"];budget=STATE["auto_order_krw"];last=STATE["last_auto_candle"]
            if a:
                m=market(sym,iv);cs=m["candles"];cid=cs[-1].get("timestamp","")
                if cid and cid!=last:
                    p=price(sym);sig=m["signal"]
                    with LOCK:q=int(STATE["positions"].get(sym,{}).get("quantity",0))
                    if sig["action"]=="BUY" and q==0:
                        n=int(min(budget,MAX_ORDER)//p)
                        if n:paper_order(sym,"BUY",n,p)
                    elif sig["action"]=="SELL" and q:paper_order(sym,"SELL",q,p)
                    with LOCK:STATE["last_auto_candle"]=cid;STATE["last_auto_action"]=sig["action"];STATE["last_auto_reason"]=sig["reason"];STATE["last_error"]="";save()
        except Exception as e:
            with LOCK:STATE["last_error"]=str(e);save()
        time.sleep(20)

class Handler(BaseHTTPRequestHandler):
    def send_json(self,v,status=200):
        raw=json.dumps(v,ensure_ascii=False).encode();o=self.headers.get("Origin","");self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin",o if o in ORIGINS else "*");self.send_header("Access-Control-Allow-Headers","Content-Type,X-Control-Token");self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
    def guard(self):
        if authorized(self):return True
        self.send_json({"error":"control token required"},401);return False
    def do_OPTIONS(self):self.send_json({"ok":True})
    def do_GET(self):
        p=urlparse(self.path);path=p.path;q=parse_qs(p.query)
        try:
            if path=="/health":return self.send_json({"ok":True,"server":"termux","mode":MODE,"trading_enabled":STATE["trading_enabled"],"auto_enabled":STATE["auto_enabled"],"paper_ready":True})
            if path=="/api/config":return self.send_json({"mode":MODE,"max_order_krw":MAX_ORDER,"max_daily_loss_krw":MAX_DAILY_LOSS,"control_token_configured":True})
            if path=="/api/toss/status":
                try:d=toss("GET","/api/v1/accounts");return self.send_json({"connected":True,"account_configured":bool(ACCOUNT_SEQ or find_account(d)),"mode":MODE,"live_api_ready":bool(ACCOUNT_SEQ or find_account(d))})
                except Exception as e:return self.send_json({"connected":False,"account_configured":False,"mode":MODE,"error":str(e)})
            if path.startswith("/api/price/"):return self.send_json(toss("GET","/api/v1/prices",{"symbols":path.rsplit("/",1)[-1]}))
            if path.startswith("/api/candles/"):return self.send_json(toss("GET","/api/v1/candles",{"symbol":path.rsplit("/",1)[-1],"interval":q.get("interval",["1m"])[0],"count":200}))
            if path.startswith("/api/market/"):return self.send_json(market(path.rsplit("/",1)[-1],q.get("interval",["1m"])[0]))
            if path.startswith("/api/orderbook/"):return self.send_json(toss("GET","/api/v1/orderbook",{"symbol":path.rsplit("/",1)[-1]}))
            if path.startswith("/api/trades/"):return self.send_json(toss("GET","/api/v1/trades",{"symbol":path.rsplit("/",1)[-1],"count":50}))
            if path=="/api/paper/portfolio":return self.send_json(portfolio())
            if path=="/api/auto/status":return self.send_json({k:STATE[k] for k in ("auto_enabled","auto_symbol","auto_interval","auto_order_krw","last_auto_candle","last_auto_action","last_auto_reason","last_error")})
            if path=="/api/live/status":return self.send_json({"mode":MODE,"credentials_configured":bool(CLIENT_ID and CLIENT_SECRET),"account_configured":bool(ACCOUNT_SEQ),"live_trading_enabled":False,"live_order_ready":False,"paper_only":True})
            if path=="/api/live/account":
                if not self.guard():return
                if MODE!="live":return self.send_json({"error":"live mode is disabled"},403)
                return self.send_json({"accountSeq":ACCOUNT_SEQ,"holdings":toss("GET","/api/v1/holdings",account=True)})
            if path=="/api/live/orders":
                if not self.guard():return
                return self.send_json(toss("GET","/api/v1/orders",{"status":q.get("status",["OPEN"])[0]},account=True))
            if path=="/api/live/buying-power":
                if not self.guard():return
                return self.send_json(toss("GET","/api/v1/buying-power",{"currency":"KRW"},account=True))
            return self.send_json({"error":"not found"},404)
        except Exception as e:return self.send_json({"error":str(e)},502)
    def do_POST(self):
        if not self.guard():return
        path=urlparse(self.path).path
        try:
            b=self.body()
            if path=="/api/trading/toggle":
                with LOCK:STATE["trading_enabled"]=bool(b.get("enabled",not STATE["trading_enabled"]));save()
                return self.send_json({"ok":True,"trading_enabled":STATE["trading_enabled"],"auto_enabled":STATE["auto_enabled"]})
            if path=="/api/auto/config":
                with LOCK:
                    if "enabled" in b:STATE["auto_enabled"]=bool(b["enabled"])
                    if "symbol" in b:STATE["auto_symbol"]=str(b["symbol"]).upper()
                    if b.get("interval") in ("1m","1d"):STATE["auto_interval"]=b["interval"]
                    if "order_krw" in b:STATE["auto_order_krw"]=max(1000,min(float(b["order_krw"]),MAX_ORDER))
                    save()
                return self.send_json({"ok":True,"auto":{k:STATE[k] for k in ("auto_enabled","auto_symbol","auto_interval","auto_order_krw")}})
            if path=="/api/paper/order":return self.send_json(paper_order(str(b["symbol"]).upper(),b["side"],b["quantity"],b["price"]),201)
            if path=="/api/paper/reset":
                with LOCK:STATE.clear();STATE.update(defaults());save()
                return self.send_json({"ok":True})
            return self.send_json({"error":"not found"},404)
        except Exception as e:return self.send_json({"error":str(e)},400)
    def log_message(self,fmt,*args):print("[HTTP]",fmt%args)

if __name__=="__main__":
    threading.Thread(target=auto_loop,daemon=True).start()
    port=int(os.getenv("PORT","8000"));print("AI Auto Trader - Termux");print("http://127.0.0.1:"+str(port)+"/health");ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
