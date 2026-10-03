#!/usr/bin/env python3
import json, os, time, math, secrets, threading
from datetime import datetime, timezone, timedelta
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
            k,v=line.split("=",1); os.environ[k.strip()]=v.strip().strip('"').strip("'")
load_env(ENV)
CLIENT_ID=os.getenv("TOSS_CLIENT_ID",""); CLIENT_SECRET=os.getenv("TOSS_CLIENT_SECRET",""); ACCOUNT_SEQ=os.getenv("TOSS_ACCOUNT_SEQ","")
MODE=os.getenv("TRADING_MODE","paper").lower(); MAX_ORDER=float(os.getenv("MAX_ORDER_KRW","100000")); MAX_ORDER_USD=float(os.getenv("MAX_ORDER_USD","100")); MAX_DAILY_LOSS=float(os.getenv("MAX_DAILY_LOSS_KRW","50000"))
LIVE_TRADING_ENABLED=os.getenv("LIVE_TRADING_ENABLED","false").lower()=="true"
LIVE_ARM_PHRASE=os.getenv("LIVE_ARM_PHRASE","").strip()
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
            "auto_enabled":False,"auto_symbol":"AAPL","auto_interval":"1m","auto_order_krw":50000.0,"auto_order_usd":50.0,
            "last_auto_candle":"","paper_last_auto_candle":"","live_last_auto_candle":"","last_auto_action":"HOLD","last_auto_reason":"","last_error":"","live_armed":False,"live_auto_enabled":False,"live_last_order_id":"","live_risk_date":"","live_risk_baseline":None,"live_daily_loss":0.0,"live_halted":False}
def load_state():
    try:
        d=json.load(open(STATE_FILE,encoding="utf-8")); s=defaults(); s.update(d); return s
    except Exception: return defaults()
STATE=load_state(); LOCK=threading.RLock()
if STATE.get("auto_symbol")=="005930": STATE["auto_symbol"]="AAPL"; STATE["auto_order_usd"]=50.0
def save():
    with LOCK:
        tmp=STATE_FILE+".tmp"; json.dump(STATE,open(tmp,"w",encoding="utf-8"),ensure_ascii=False,indent=2); os.replace(tmp,STATE_FILE)

STATE["live_armed"]=False; STATE["live_auto_enabled"]=False; STATE["live_halted"]=False
save()

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
    for attempt in range(4):
        if not TOKEN or time.time()>TOKEN_UNTIL-30:
            if not CLIENT_ID or not CLIENT_SECRET: raise RuntimeError("Toss credentials are not configured")
            data=urlencode({"grant_type":"client_credentials","client_id":CLIENT_ID,"client_secret":CLIENT_SECRET}).encode()
            req=Request(BASE+"/oauth2/token",data=data,headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
            with urlopen(req,timeout=10) as r: d=json.loads(r.read())
            TOKEN=d["access_token"]; TOKEN_UNTIL=time.time()+int(d.get("expires_in",86400))
        acct=ACCOUNT_SEQ
        if account and not acct:
            acct=find_account(toss("GET","/api/v1/accounts"))
            if not acct: raise RuntimeError("No active Toss account found")
        url=BASE+path+("?" + urlencode(params) if params else "")
        h={"Authorization":"Bearer "+TOKEN}
        if account: h["X-Tossinvest-Account"]=acct
        data=json.dumps(body).encode() if body is not None else None
        if body is not None:h["Content-Type"]="application/json"
        try:
            with urlopen(Request(url,data=data,headers=h,method=method),timeout=10) as r:return json.loads(r.read())
        except HTTPError as e:
            raw=e.read().decode(errors="replace")
            if e.code==401:
                TOKEN=None
                if attempt<3: continue
            if e.code==429:
                retry=float(e.headers.get("Retry-After","0") or 0)
                time.sleep(max(retry,2**attempt)+secrets.randbelow(250)/1000)
                continue
            raise RuntimeError(f"Toss API {e.code}: {raw[:500]}")
    raise RuntimeError("Toss API rate limit retry exhausted")

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
    return secrets.compare_digest(h.headers.get("X-Control-Token",""),CONTROL_TOKEN)

def _numbers(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if isinstance(x,(int,float)) and not isinstance(x,bool):
                yield k.lower(),float(x)
            elif isinstance(x,str):
                s=x.strip().replace(",","")
                # Toss API financial quantities/prices may be returned as strings.
                # Accept only plain numeric strings, avoiding timestamps and arbitrary text.
                try:
                    if s and all(ch in "0123456789.-" for ch in s) and s.count(".") <= 1 and s.count("-") <= 1:
                        yield k.lower(),float(s)
                except ValueError:
                    pass
            yield from _numbers(x)
    elif isinstance(v,list):
        for x in v:
            yield from _numbers(x)

def _find_value(v,names):
    wanted={x.lower() for x in names}
    for k,n in _numbers(v):
        if k in wanted:return n
    return None

def _holding_rows(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if k.lower() in ("holdings","items","assets","positions") and isinstance(x,list):
                for row in x:
                    if isinstance(row,dict): yield row
            yield from _holding_rows(x)
    elif isinstance(v,list):
        for x in v:
            yield from _holding_rows(x)

_FX_CACHE={"rate":None,"until":0.0}

def usd_krw_rate():
    now=time.time()
    if _FX_CACHE["rate"] is not None and now<_FX_CACHE["until"]: return float(_FX_CACHE["rate"])
    d=toss("GET","/api/v1/exchange-rate",{"baseCurrency":"USD","quoteCurrency":"KRW"})
    rate=_find_value(d,{"rate","midRate"})
    if rate is None or rate<=0: raise RuntimeError("USD/KRW exchange rate unavailable")
    _FX_CACHE["rate"]=float(rate); _FX_CACHE["until"]=now+60
    return float(rate)

def is_us_symbol(symbol): return not str(symbol).isdigit()

def live_equity_snapshot():
    live_guard()
    h=toss("GET","/api/v1/holdings",account=True)
    krw=toss("GET","/api/v1/buying-power",{"currency":"KRW"},account=True)
    usd=toss("GET","/api/v1/buying-power",{"currency":"USD"},account=True)
    rows=list(_holding_rows(h)); seen=set(); holding_krw=0.0; holding_usd=0.0
    for row in rows:
        marker=id(row)
        if marker in seen: continue
        seen.add(marker)
        value=_find_value(row,{"marketValue","evaluationAmount","evaluationValue","evaluationPriceAmount","holdingValue","assetValue"})
        if value is None:
            q=_find_value(row,{"quantity","holdingQuantity","sellableQuantity","availableQuantity","balanceQuantity"})
            p=_find_value(row,{"currentPrice","lastPrice","evaluationPrice","marketPrice","price"})
            if q is not None and p is not None: value=q*p
        if value is None: continue
        sym=str(row.get("symbol",row.get("stockCode",""))) if isinstance(row,dict) else ""
        cur=str(row.get("currency","")).upper() if isinstance(row,dict) else ""
        if cur not in ("KRW","USD"): cur="USD" if is_us_symbol(sym) else "KRW"
        if cur=="USD": holding_usd+=float(value)
        else: holding_krw+=float(value)
    krw_cash=_buying_power_value(krw) or 0.0; usd_cash=_buying_power_value(usd) or 0.0
    rate=usd_krw_rate(); equity_krw=krw_cash+holding_krw+(usd_cash+holding_usd)*rate
    if equity_krw<=0: raise RuntimeError("live equity value unavailable; KRW/USD cash and holdings contain no usable value")
    return {"equity":float(equity_krw),"equity_krw":float(equity_krw),"krw_cash":float(krw_cash),"usd_cash":float(usd_cash),"holding_krw":float(holding_krw),"holding_usd":float(holding_usd),"usd_krw_rate":float(rate),"holdings":h,"buying_power":{"KRW":krw,"USD":usd}}

def live_daily_risk_check():
    snap=live_equity_snapshot()
    today=datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    with LOCK:
        if STATE.get("live_risk_date")!=today or STATE.get("live_risk_baseline") is None:
            STATE["live_risk_date"]=today; STATE["live_risk_baseline"]=snap["equity"]; STATE["live_daily_loss"]=0.0; STATE["live_halted"]=False
        loss=max(0.0,float(STATE["live_risk_baseline"])-snap["equity"])
        STATE["live_daily_loss"]=loss
        if loss>=MAX_DAILY_LOSS:
            STATE["live_halted"]=True; STATE["live_auto_enabled"]=False; save()
            raise RuntimeError(f"daily loss limit reached: {loss:,.0f} KRW")
        save()
    return snap

def live_guard():
    global ACCOUNT_SEQ
    if MODE!="live": raise RuntimeError("TRADING_MODE=live is required")
    if not LIVE_TRADING_ENABLED: raise RuntimeError("LIVE_TRADING_ENABLED=false")
    if STATE.get("live_halted",False): raise RuntimeError("live trading halted by risk control")
    if not ACCOUNT_SEQ:
        d=toss("GET","/api/v1/accounts")
        seq=find_account(d)
        if not seq: raise RuntimeError("No active Toss account found")
        ACCOUNT_SEQ=seq
    return True

def _buying_power_value(v):
    return _find_value(v,{"cashBuyingPower","buyingPower","availableAmount","availableCash","cash","orderableAmount"})

def _sellable_value(v):
    return _find_value(v,{"quantity","sellableQuantity","availableQuantity","orderableQuantity"})

def live_order(symbol,side,quantity=None,order_type="MARKET",price=None,order_amount=None):
    live_guard(); live_daily_risk_check()
    symbol=str(symbol).upper(); side=str(side).upper(); order_type=str(order_type).upper(); us=is_us_symbol(symbol)
    if side not in ("BUY","SELL"): raise ValueError("invalid live order")
    if order_type not in ("MARKET","LIMIT"): raise ValueError("invalid order type")
    if order_type=="LIMIT" and (price is None or float(price)<=0): raise ValueError("limit price required")
    if order_type=="MARKET" and price is not None: raise ValueError("market order cannot include price")
    ref=float(price) if price is not None else price_value_for_risk(symbol)
    if ref is None or ref<=0: raise ValueError("live price unavailable; order blocked")
    if us and side=="BUY" and order_type=="MARKET" and order_amount is not None:
        amount=float(order_amount)
        if amount<=0: raise ValueError("USD order amount must be positive")
        if amount>MAX_ORDER_USD*0.95: raise ValueError(f"live max US order is {MAX_ORDER_USD:,.2f} USD (5% buffer required)")
        bp=toss("GET","/api/v1/buying-power",{"currency":"USD"},account=True); available=_buying_power_value(bp)
        if available is not None and amount>available: raise ValueError(f"USD buying power is {available:,.2f}")
        body={"clientOrderId":"ait-"+secrets.token_hex(10),"symbol":symbol,"side":"BUY","orderType":"MARKET","orderAmount":f"{amount:.2f}"}
    else:
        if quantity is None: raise ValueError("quantity required")
        qty=float(quantity)
        if qty<=0: raise ValueError("quantity must be positive")
        if us and qty!=int(qty) and not (side=="SELL" and order_type=="MARKET"): raise ValueError("fractional quantity is only allowed for US market SELL")
        notional=qty*ref; currency="USD" if us else "KRW"
        limit=MAX_ORDER_USD if us else MAX_ORDER
        if notional>limit*0.95: raise ValueError(f"live max {currency} order is {limit:,.2f} (5% buffer required)")
        if side=="BUY":
            bp=toss("GET","/api/v1/buying-power",{"currency":currency},account=True); available=_buying_power_value(bp)
            if available is not None and notional>available: raise ValueError(f"{currency} buying power is {available:,.2f}")
        else:
            sd=toss("GET","/api/v1/sellable-quantity",{"symbol":symbol},account=True); available=_sellable_value(sd)
            if available is not None and qty>available: raise ValueError(f"sellable quantity is {available}")
        qtext=str(qty).rstrip("0").rstrip(".")
        body={"clientOrderId":"ait-"+secrets.token_hex(10),"symbol":symbol,"side":side,"orderType":order_type,"quantity":qtext}
        if order_type=="LIMIT": body["price"]=f"{float(price):.4f}".rstrip("0").rstrip(".") if us else str(int(float(price)))
    result=toss("POST","/api/v1/orders",body=body,account=True)
    with LOCK:
        STATE["live_last_order_id"]=result.get("result",{}).get("orderId",""); STATE["last_error"]=""; save()
    return result


def live_modify(order_id,quantity=None,price=None):
    live_guard()
    if not order_id: raise ValueError("order id required")
    body={}
    if quantity is not None:
        q=int(quantity)
        if q<=0: raise ValueError("quantity must be positive")
        body["quantity"]=str(q)
    if price is not None:
        p=float(price)
        if p<=0: raise ValueError("price must be positive")
        body["price"]=str(int(p))
    if not body: raise ValueError("quantity or price required")
    return toss("POST",f"/api/v1/orders/{order_id}/modify",body=body,account=True)

def live_cancel(order_id):
    live_guard()
    if not order_id: raise ValueError("order id required")
    return toss("POST",f"/api/v1/orders/{order_id}/cancel",body={},account=True)

def price_value_for_risk(symbol):
    try:return price(symbol)
    except Exception:return None

def live_account_snapshot():
    live_guard()
    holdings=toss("GET","/api/v1/holdings",account=True)
    buying_krw=toss("GET","/api/v1/buying-power",{"currency":"KRW"},account=True)
    buying_usd=toss("GET","/api/v1/buying-power",{"currency":"USD"},account=True)
    orders=toss("GET","/api/v1/orders",{"status":"OPEN"},account=True)
    rows=list(_holding_rows(holdings)); seen=set(); holding_krw=0.0; holding_usd=0.0
    for row in rows:
        marker=id(row)
        if marker in seen: continue
        seen.add(marker)
        value=_find_value(row,{"marketValue","evaluationAmount","evaluationValue","evaluationPriceAmount","holdingValue","assetValue"})
        if value is None:
            q=_find_value(row,{"quantity","holdingQuantity","sellableQuantity","availableQuantity","balanceQuantity"})
            p=_find_value(row,{"currentPrice","lastPrice","evaluationPrice","marketPrice","price"})
            if q is not None and p is not None: value=q*p
        if value is None: continue
        sym=str(row.get("symbol",row.get("stockCode",""))) if isinstance(row,dict) else ""
        cur=str(row.get("currency","")).upper() if isinstance(row,dict) else ""
        if cur not in ("KRW","USD"): cur="USD" if is_us_symbol(sym) else "KRW"
        if cur=="USD": holding_usd+=float(value)
        else: holding_krw+=float(value)
    krw_cash=_buying_power_value(buying_krw) or 0.0
    usd_cash=_buying_power_value(buying_usd) or 0.0
    rate=usd_krw_rate()
    equity_krw=krw_cash+holding_krw+(usd_cash+holding_usd)*rate
    return {"holdings":holdings,"buying_power":{"KRW":buying_krw,"USD":buying_usd},"open_orders":orders,
            "valuation":{"equity_krw":equity_krw,"krw_cash":krw_cash,"usd_cash":usd_cash,"holding_krw":holding_krw,"holding_usd":holding_usd,"usd_krw_rate":rate}}

def live_auto_loop():
    while True:
        try:
            with LOCK:
                active=STATE.get("live_armed",False) and STATE.get("live_auto_enabled",False) and STATE.get("trading_enabled",False)
                sym=STATE.get("auto_symbol","005930"); iv=STATE.get("auto_interval","1m")
                budget=float(STATE.get("auto_order_usd",50) if is_us_symbol(sym) else STATE.get("auto_order_krw",50000)); last=STATE.get("live_last_auto_candle","")
            if active and MODE=="live" and LIVE_TRADING_ENABLED:
                live_daily_risk_check()
                m=market(sym,iv); cs=m["candles"]; cid=cs[-1].get("timestamp","")
                if cid and cid!=last:
                    if m.get("source")!="TOSS_LIVE":
                        raise RuntimeError("live trading halted: live market data unavailable")
                    sig=m["signal"]; p=price(sym)
                    if sig["action"]=="BUY":
                        if is_us_symbol(sym):
                            if budget>0: live_order(sym,"BUY",None,"MARKET",order_amount=min(budget,MAX_ORDER_USD))
                        else:
                            n=int(min(budget,MAX_ORDER)//p)
                            if n: live_order(sym,"BUY",n,"MARKET")
                    elif sig["action"]=="SELL":
                        h=toss("GET","/api/v1/holdings",account=True)
                        n=0
                        for row in (h.get("result",{}).get("holdings",[]) if isinstance(h,dict) else []):
                            if str(row.get("symbol","")).upper()==sym:
                                n=int(float(row.get("quantity",row.get("holdingQuantity",0)) or 0)); break
                        if n: live_order(sym,"SELL",n,"MARKET")
                    with LOCK:
                        STATE["live_last_auto_candle"]=cid;STATE["last_auto_action"]=sig["action"];STATE["last_auto_reason"]=sig["reason"];save()
        except Exception as e:
            with LOCK: STATE["last_error"]=str(e); save()
        time.sleep(20)

def auto_loop():
    while True:
        try:
            with LOCK:a=STATE["auto_enabled"] and STATE["trading_enabled"] and MODE=="paper";sym=STATE["auto_symbol"];iv=STATE["auto_interval"];budget=STATE["auto_order_krw"];last=STATE["paper_last_auto_candle"]
            if a:
                m=market(sym,iv);cs=m["candles"];cid=cs[-1].get("timestamp","")
                if cid and cid!=last:
                    p=price(sym);sig=m["signal"]
                    with LOCK:q=int(STATE["positions"].get(sym,{}).get("quantity",0))
                    if sig["action"]=="BUY" and q==0:
                        n=int(min(budget,MAX_ORDER)//p)
                        if n:paper_order(sym,"BUY",n,p)
                    elif sig["action"]=="SELL" and q:paper_order(sym,"SELL",q,p)
                    with LOCK:STATE["paper_last_auto_candle"]=cid;STATE["last_auto_action"]=sig["action"];STATE["last_auto_reason"]=sig["reason"];STATE["last_error"]="";save()
        except Exception as e:
            with LOCK:STATE["last_error"]=str(e);save()
        time.sleep(20)

class Handler(BaseHTTPRequestHandler):
    def send_json(self,v,status=200):
        raw=json.dumps(v,ensure_ascii=False).encode();o=self.headers.get("Origin","")
        if o and o not in ORIGINS:
            self.send_response(403); self.send_header("Content-Type","application/json; charset=utf-8"); self.end_headers(); return
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin",o if o in ORIGINS else (ORIGINS[0] if ORIGINS else "null"));self.send_header("Access-Control-Allow-Headers","Content-Type,X-Control-Token");self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))) or b"{}")
    def guard(self):
        if authorized(self):return True
        self.send_json({"error":"control token required"},401);return False
    def do_OPTIONS(self):self.send_json({"ok":True})
    def do_GET(self):
        p=urlparse(self.path);path=p.path;q=parse_qs(p.query)
        try:
            if path=="/health":return self.send_json({"ok":True,"server":"termux","mode":MODE,"trading_enabled":STATE["trading_enabled"],"auto_enabled":STATE["live_auto_enabled"],"live_armed":STATE["live_armed"],"live_halted":STATE["live_halted"]})
            if path=="/api/config":return self.send_json({"mode":MODE,"max_order_krw":MAX_ORDER,"max_daily_loss_krw":MAX_DAILY_LOSS,"control_token_configured":True})
            if path=="/api/toss/status":
                try:d=toss("GET","/api/v1/accounts");return self.send_json({"connected":True,"account_configured":bool(ACCOUNT_SEQ or find_account(d)),"mode":MODE,"live_api_ready":bool(ACCOUNT_SEQ or find_account(d))})
                except Exception as e:return self.send_json({"connected":False,"account_configured":False,"mode":MODE,"error":str(e)})
            if path.startswith("/api/price/"):return self.send_json(toss("GET","/api/v1/prices",{"symbols":path.rsplit("/",1)[-1]}))
            if path.startswith("/api/candles/"):return self.send_json(toss("GET","/api/v1/candles",{"symbol":path.rsplit("/",1)[-1],"interval":q.get("interval",["1m"])[0],"count":200}))
            if path.startswith("/api/market/"):return self.send_json(market(path.rsplit("/",1)[-1],q.get("interval",["1m"])[0]))
            if path.startswith("/api/orderbook/"):return self.send_json(toss("GET","/api/v1/orderbook",{"symbol":path.rsplit("/",1)[-1]}))
            if path.startswith("/api/trades/"):return self.send_json(toss("GET","/api/v1/trades",{"symbol":path.rsplit("/",1)[-1],"count":50}))
            if path=="/api/paper/portfolio":return self.send_json({"error":"paper trading has been removed"},410)
            if path=="/api/auto/status":return self.send_json({k:STATE[k] for k in ("auto_enabled","auto_symbol","auto_interval","auto_order_krw","last_auto_candle","last_auto_action","last_auto_reason","last_error")})
            if path=="/api/live/config":
                if not self.guard():return
                return self.send_json({"mode":MODE,"live_trading_enabled":LIVE_TRADING_ENABLED,"arm_phrase_configured":bool(LIVE_ARM_PHRASE),"arm_phrase_length":len(LIVE_ARM_PHRASE),"credentials_configured":bool(CLIENT_ID and CLIENT_SECRET)})
            if path=="/api/live/status":
                return self.send_json({"mode":MODE,"credentials_configured":bool(CLIENT_ID and CLIENT_SECRET),"account_configured":bool(ACCOUNT_SEQ),"live_trading_enabled":LIVE_TRADING_ENABLED,"live_armed":bool(STATE.get("live_armed",False)),"live_auto_enabled":bool(STATE.get("live_auto_enabled",False)),"live_halted":bool(STATE.get("live_halted",False)),"daily_loss_krw":float(STATE.get("live_daily_loss",0) or 0),"daily_loss_limit_krw":MAX_DAILY_LOSS,"last_order_id":STATE.get("live_last_order_id",""),"live_order_ready":MODE=="live" and LIVE_TRADING_ENABLED and bool(STATE.get("live_armed",False)) and not bool(STATE.get("live_halted",False))})
            if path=="/api/live/account":
                if not self.guard():return
                if MODE!="live":return self.send_json({"error":"live mode is disabled"},403)
                return self.send_json({"accountSeq":ACCOUNT_SEQ,"snapshot":live_account_snapshot()})
            if path=="/api/live/orders":
                if not self.guard():return
                return self.send_json(toss("GET","/api/v1/orders",{"status":q.get("status",["OPEN"])[0]},account=True))
            if path.startswith("/api/live/orders/"):
                if not self.guard():return
                oid=path.rsplit("/",1)[-1]
                return self.send_json(toss("GET",f"/api/v1/orders/{oid}",account=True))
            if path=="/api/live/buying-power":
                if not self.guard():return
                return self.send_json(toss("GET","/api/v1/buying-power",{"currency":q.get("currency",["KRW"])[0].upper()},account=True))
            if path=="/api/live/risk":
                if not self.guard():return
                snap=live_daily_risk_check()
                return self.send_json({"ok":True,"equity":snap["equity"],"daily_loss_krw":STATE.get("live_daily_loss",0),"daily_loss_limit_krw":MAX_DAILY_LOSS,"halted":STATE.get("live_halted",False)})
            if path.startswith("/api/live/sellable/"):
                if not self.guard():return
                if MODE!="live":return self.send_json({"error":"live mode is disabled"},403)
                sym=path.rsplit("/",1)[-1]
                return self.send_json(toss("GET","/api/v1/sellable-quantity",{"symbol":sym},account=True))
            return self.send_json({"error":"not found"},404)
        except Exception as e:return self.send_json({"error":str(e)},502)
    def do_POST(self):
        if not self.guard():return
        path=urlparse(self.path).path
        try:
            b=self.body()
            if path=="/api/trading/toggle":
                with LOCK:
                    STATE["trading_enabled"]=bool(b.get("enabled",not STATE["trading_enabled"]))
                    if not STATE["trading_enabled"]: STATE["live_auto_enabled"]=False
                    save()
                return self.send_json({"ok":True,"trading_enabled":STATE["trading_enabled"],"auto_enabled":STATE["live_auto_enabled"]})
            if path=="/api/auto/config":
                with LOCK:
                    if "enabled" in b:STATE["auto_enabled"]=bool(b["enabled"])
                    if "symbol" in b:STATE["auto_symbol"]=str(b["symbol"]).upper()
                    if b.get("interval") in ("1m","1d"):STATE["auto_interval"]=b["interval"]
                    if "order_krw" in b:STATE["auto_order_krw"]=max(1000,min(float(b["order_krw"]),MAX_ORDER))
                    save()
                return self.send_json({"ok":True,"auto":{k:STATE[k] for k in ("auto_enabled","auto_symbol","auto_interval","auto_order_krw")}})
            if path=="/api/live/arm":
                if MODE!="live" or not LIVE_TRADING_ENABLED:return self.send_json({"error":"live trading is not enabled in local config"},403)
                phrase=str(b.get("phrase","")).strip()
                if not LIVE_ARM_PHRASE or not secrets.compare_digest(phrase,LIVE_ARM_PHRASE):return self.send_json({"error":"invalid live arm phrase"},403)
                live_daily_risk_check()
                with LOCK:STATE["live_armed"]=True;STATE["live_auto_enabled"]=False;save()
                return self.send_json({"ok":True,"live_armed":True,"live_auto_enabled":False,"daily_loss_krw":STATE.get("live_daily_loss",0)})
            if path=="/api/live/disarm":
                with LOCK:STATE["live_armed"]=False;STATE["live_auto_enabled"]=False;save()
                return self.send_json({"ok":True,"live_armed":False,"live_auto_enabled":False})
            if path=="/api/live/auto":
                if not STATE.get("live_armed",False):return self.send_json({"error":"live engine is not armed"},403)
                if bool(b.get("enabled",False)) and not STATE.get("trading_enabled",False):return self.send_json({"error":"live engine is stopped"},403)
                if bool(b.get("enabled",False)): live_daily_risk_check()
                with LOCK:STATE["live_auto_enabled"]=bool(b.get("enabled",False));save()
                return self.send_json({"ok":True,"live_auto_enabled":STATE["live_auto_enabled"]})
            if path=="/api/live/order":
                if not STATE.get("live_armed",False):return self.send_json({"error":"live engine is not armed"},403)
                if b.get("confirm") is not True:return self.send_json({"error":"live order confirmation required"},400)
                sym=str(b["symbol"]).upper(); side=str(b["side"]).upper(); qty=b.get("quantity")
                amount=b.get("order_amount")
                return self.send_json(live_order(sym,side,qty,b.get("order_type","MARKET"),b.get("price"),amount),201)
            if path.startswith("/api/live/orders/") and path.endswith("/modify"):
                oid=path.split("/")[-2]
                if not b.get("confirm"):return self.send_json({"error":"order modification confirmation required"},400)
                return self.send_json(live_modify(oid,b.get("quantity"),b.get("price")))
            if path.startswith("/api/live/orders/") and path.endswith("/cancel"):
                oid=path.split("/")[-2]
                if not b.get("confirm"):return self.send_json({"error":"order cancellation confirmation required"},400)
                return self.send_json(live_cancel(oid))
            if path=="/api/paper/order":return self.send_json({"error":"paper trading has been removed"},410)
            if path=="/api/paper/reset":return self.send_json({"error":"paper trading has been removed"},410)
            return self.send_json({"error":"not found"},404)
        except Exception as e:return self.send_json({"error":str(e)},400)
    def log_message(self,fmt,*args):print("[HTTP]",fmt%args)

if __name__=="__main__":
    threading.Thread(target=auto_loop,daemon=True).start()
    threading.Thread(target=live_auto_loop,daemon=True).start()
    port=int(os.getenv("PORT","8000"));print("AI Auto Trader - Termux");print("http://127.0.0.1:"+str(port)+"/health");ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
