let API_BASE=localStorage.getItem("TRADING_API_BASE")||"";
let CONTROL_TOKEN=localStorage.getItem("TRADING_CONTROL_TOKEN")||"";
let engine=false,liveArmed=false,liveAuto=false,interval="1m",market=null;
const $=id=>document.getElementById(id);
const won=n=>"₩"+Math.round(Number(n||0)).toLocaleString("ko-KR");
function headers(){return {"Content-Type":"application/json","X-Control-Token":CONTROL_TOKEN}}
async function api(path,opt={}){return fetch(API_BASE+path,{...opt,headers:{...headers(),...(opt.headers||{})}})}
function errText(d){return d?.error?.message||d?.error||"요청 실패"}
function numbers(v){
  const out=[];
  const walk=x=>{
    if(Array.isArray(x)) return x.forEach(walk);
    if(x&&typeof x==="object") for(const [k,val] of Object.entries(x)){
      if(typeof val==="number") out.push([k.toLowerCase(),val]);
      else if(typeof val==="string"&&/^-?[d,]+(?:\.\d+)?$/.test(val)) out.push([k.toLowerCase(),Number(val.replaceAll(",",""))]);
      walk(val);
    }
  }; walk(v); return out;
}
function find(v,names){const s=new Set(names.map(x=>x.toLowerCase()));return numbers(v).find(x=>s.has(x[0]))?.[1]??null}
function list(v,names){
  if(Array.isArray(v)) return v;
  if(v&&typeof v==="object") for(const k of names){if(Array.isArray(v[k]))return v[k]}
  if(v&&typeof v==="object") for(const x of Object.values(v)){const r=list(x,names);if(r.length)return r}
  return [];
}
function renderEngine(d){
  engine=!!d.trading_enabled;
  $("engineState").textContent=engine?"실거래 엔진 실행 중":"실거래 엔진 중지";
  $("status").textContent=engine?"LIVE RUNNING":"LIVE STOPPED";
  $("status").className="badge "+(engine?"running":"stopped");
  $("engineToggle").textContent=engine?"실거래 엔진 중지":"실거래 엔진 시작";
}
async function health(){
  try{const r=await api("/health"),d=await r.json();renderEngine(d);$("serverText").textContent=API_BASE+" · ONLINE";return d}
  catch{$("status").textContent="OFFLINE";$("status").className="badge stopped";$("serverText").textContent="API 서버 연결 실패"}
}
function drawChart(cs){
  const c=$("chart"),ctx=c.getContext("2d"),dpr=devicePixelRatio||1,w=c.clientWidth,h=300;
  c.width=w*dpr;c.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);if(!cs.length)return;
  const pad=30,hi=cs.map(x=>+x.highPrice),lo=cs.map(x=>+x.lowPrice),min=Math.min(...lo),max=Math.max(...hi),range=Math.max(1,max-min);
  const x=i=>pad+i*(w-pad*2)/Math.max(1,cs.length-1),y=v=>h-pad-(v-min)/range*(h-pad*2);
  ctx.clearRect(0,0,w,h);ctx.strokeStyle="#2a3340";
  for(let g=0;g<4;g++){let yy=pad+g*(h-pad*2)/3;ctx.beginPath();ctx.moveTo(pad,yy);ctx.lineTo(w-pad,yy);ctx.stroke()}
  let step=Math.max(3,(w-pad*2)/cs.length*.62);
  cs.forEach((z,i)=>{let px=x(i),o=+z.openPrice,cl=+z.closePrice;ctx.strokeStyle=cl>=o?"#75e3a1":"#ff9a9a";ctx.beginPath();ctx.moveTo(px,y(+z.lowPrice));ctx.lineTo(px,y(+z.highPrice));ctx.stroke();ctx.fillStyle=ctx.strokeStyle;let top=y(Math.max(o,cl)),bot=y(Math.min(o,cl));ctx.fillRect(px-step/2,top,Math.max(1,step),Math.max(1,bot-top))});
  ctx.fillStyle="#8993a4";ctx.font="11px system-ui";ctx.fillText(won(max),8,16);ctx.fillText(won(min),8,h-6);
}
async function loadMarket(){
  const sym=$("symbol").value.trim().toUpperCase();
  try{
    market=await(await api("/api/market/"+encodeURIComponent(sym)+"?interval="+interval)).json();
    $("signal").textContent=market.signal?.action||"-";$("source").textContent=market.source||"-";
    $("livePrice").textContent=market.candles?.length?won(market.candles.at(-1).closePrice):"-";
    const i=market.indicators||{};$("sma5").textContent=won(i.sma5);$("sma20").textContent=won(i.sma20);$("rsi14").textContent=i.rsi14==null?"-":Number(i.rsi14).toFixed(1);
    drawChart(market.candles||[]);
    if(market.candles?.length)$("orderPrice").value=Math.round(Number(market.candles.at(-1).closePrice));
    await orderbook(sym);
  }catch{}
}
async function orderbook(sym){
  try{
    const d=await(await api("/api/orderbook/"+encodeURIComponent(sym))).json(),v=d.result||d;
    const asks=v.asks||v.sell||v.sellOrders||[],bids=v.bids||v.buy||v.buyOrders||[],rows=[];
    for(let i=0;i<Math.max(asks.length,bids.length,5)&&i<10;i++){const a=asks[i],b=bids[i];rows.push('<div class="bookrow"><span class="ask">'+(a?(a.price??a.askPrice??"-"):"")+'</span><span>'+(a?(a.quantity??a.volume??a.askQuantity??"-"):"")+'</span><span class="bid">'+(b?(b.price??b.bidPrice??"-"):"")+'</span></div>')}
    $("orderbook").innerHTML='<div class="bookrow"><b>매도</b><b>잔량</b><b>매수</b></div>'+rows.join("");
  }catch{$("orderbook").textContent="호가 조회 실패"}
}
function renderHoldings(d){
  const rows=list(d,["holdings","items","positions","assets"]);
  if(!rows.length){$("holdings").textContent="보유 종목 없음";return}
  $("holdings").innerHTML=rows.map(x=>{
    const sym=x.symbol||x.stockCode||"-",q=find(x,["quantity","holdingQuantity","sellableQuantity"])||0;
    const value=find(x,["marketValue","evaluationAmount","evaluationValue","assetValue"])||0;
    const pnl=find(x,["unrealizedPnl","profitLoss","profitAndLoss","pnl"])||0;
    return '<div class="trade"><span>'+sym+' × '+q+'</span><span>'+won(value)+' / '+(pnl>=0?"+":"")+won(pnl)+'</span></div>';
  }).join("");
}
async function account(){
  try{
    const r=await api("/api/live/account"),d=await r.json();if(!r.ok)throw Error(errText(d));
    const s=d.snapshot||{},bp=s.buying_power||{},h=s.holdings||{};
    const equity=find(h,["totalEvaluationAmount","totalEvaluationValue","totalMarketValue","totalAssetValue","totalEquity","equity"]);
    const cash=find(bp,["cashBuyingPower","buyingPower","availableAmount","availableCash","cash","orderableAmount"]);
    $("equity").textContent=equity==null?"-":won(equity);$("cash").textContent=cash==null?"-":won(cash);
    const baseline=find(h,["totalPurchaseAmount","totalBuyAmount"]);
    $("pnl").textContent=baseline!=null&&equity!=null?(equity>=baseline?"+":"")+won(equity-baseline):"-";
    renderHoldings(h);renderOrders(s.open_orders);
  }catch{$("equity").textContent="-";$("cash").textContent="-";$("holdings").textContent="계좌 조회 실패"}
}
function renderOrders(d){
  const rows=list(d,["orders","items","records"]);
  if(!rows.length){$("orders").textContent="미체결 주문 없음";return}
  $("orders").innerHTML=rows.map(x=>{
    const id=x.orderId||x.id||"-",sym=x.symbol||"-",side=x.side||"-",qty=x.quantity||x.orderQuantity||"-",price=x.price||x.orderPrice||"시장가";
    return '<div class="trade"><span>'+side+' '+sym+' × '+qty+' @ '+price+'</span><span><button class="mini secondary" onclick="modifyOrder(\''+id+'\')">정정</button> <button class="mini danger" onclick="cancelOrder(\''+id+'\')">취소</button></span></div>';
  }).join("");
}
async function liveStatus(){
  try{
    const r=await api("/api/live/status"),d=await r.json();if(!r.ok)throw Error(errText(d));
    liveArmed=!!d.live_armed;liveAuto=!!d.live_auto_enabled;
    $("liveState").textContent=d.live_halted?"위험한도 정지":liveArmed?(liveAuto?"ARM + 자동 ON":"ARM 완료"):"대기";
    $("liveState").className="badge "+(d.live_halted?"stopped":liveArmed?"running":"stopped");
    $("liveArm").disabled=liveArmed;$("liveDisarm").disabled=!liveArmed;$("liveAuto").disabled=!liveArmed||!engine;
    $("liveAuto").textContent=liveAuto?"실거래 자동매매 OFF":"실거래 자동매매 ON";
    $("risk").textContent=won(d.daily_loss_krw)+" / "+won(d.daily_loss_limit_krw);
    $("lastOrder").textContent=d.last_order_id||"-";
  }catch{}
}
async function toggleEngine(){
  try{const r=await api("/api/trading/toggle",{method:"POST",body:JSON.stringify({enabled:!engine})}),d=await r.json();if(!r.ok)throw Error(errText(d));renderEngine(d);await liveStatus()}
  catch(e){alert(e.message)}
}
async function arm(){
  const phrase=prompt("LIVE_ARM_PHRASE를 입력하세요. 입력값은 서버로 전송되며 화면에 저장되지 않습니다.");
  if(!phrase)return;
  try{const r=await api("/api/live/arm",{method:"POST",body:JSON.stringify({phrase})}),d=await r.json();if(!r.ok)throw Error(errText(d));await liveStatus();await account();alert("실거래 ARM 완료")}
  catch(e){alert(e.message)}
}
async function placeOrder(){
  const sym=$("symbol").value.trim().toUpperCase(),side=$("orderSide").value,qty=Number($("orderQty").value),type=$("orderType").value,price=Number($("orderPrice").value);
  if(!liveArmed){alert("먼저 실거래 ARM을 하세요.");return}
  if(!$("confirmOrder").checked){alert("실거래 주문 확인을 체크하세요.");return}
  if(!Number.isInteger(qty)||qty<=0){alert("수량을 확인하세요.");return}
  const detail=side+" "+sym+" "+qty+"주 "+(type==="MARKET"?"시장가":"지정가 "+price.toLocaleString()+"원");
  if(!confirm("실제 계좌에 주문합니다.\n\n"+detail+"\n\n계속하시겠습니까?"))return;
  try{
    const body={symbol:sym,side,quantity:qty,order_type:type,confirm:true};if(type==="LIMIT")body.price=price;
    const r=await api("/api/live/order",{method:"POST",body:JSON.stringify(body)}),d=await r.json();if(!r.ok)throw Error(errText(d));
    $("confirmOrder").checked=false;alert("주문 접수 완료\n주문번호: "+(d.result?.orderId||d.orderId||"-"));await account();await liveStatus();
  }catch(e){alert(e.message)}
}
async function modifyOrder(id){
  const p=prompt("새 지정가 가격을 입력하세요.\n취소하려면 빈칸.", "");
  if(!p)return;
  const q=prompt("새 수량을 입력하세요.\n그대로면 현재 수량을 다시 입력해야 합니다.", "");
  if(!q)return;
  if(!confirm("주문 "+id+" 을(를) 정정합니다.\n가격: "+p+" / 수량: "+q))return;
  try{const r=await api("/api/live/orders/"+encodeURIComponent(id)+"/modify",{method:"POST",body:JSON.stringify({price:Number(p),quantity:Number(q),confirm:true})}),d=await r.json();if(!r.ok)throw Error(errText(d));alert("정정 요청 완료");await account()}catch(e){alert(e.message)}
}
async function cancelOrder(id){
  if(!confirm("주문 "+id+" 을(를) 취소합니다.\n계속하시겠습니까?"))return;
  try{const r=await api("/api/live/orders/"+encodeURIComponent(id)+"/cancel",{method:"POST",body:JSON.stringify({confirm:true})}),d=await r.json();if(!r.ok)throw Error(errText(d));alert("취소 요청 완료");await account()}catch(e){alert(e.message)}
}
async function toggleAuto(){
  try{
    const r=await api("/api/live/auto",{method:"POST",body:JSON.stringify({enabled:!liveAuto})}),d=await r.json();if(!r.ok)throw Error(errText(d));
    await liveStatus();
  }catch(e){alert(e.message)}
}
$("engineToggle").onclick=toggleEngine;$("liveArm").onclick=arm;
$("liveDisarm").onclick=async()=>{try{const r=await api("/api/live/disarm",{method:"POST",body:"{}"});if(!r.ok)throw Error(errText(await r.json()));await liveStatus();await account()}catch(e){alert(e.message)}};
$("liveAuto").onclick=toggleAuto;$("placeOrder").onclick=placeOrder;
document.querySelectorAll(".interval").forEach(b=>b.onclick=()=>{interval=b.dataset.interval;document.querySelectorAll(".interval").forEach(x=>x.classList.remove("active"));b.classList.add("active");loadMarket()});
$("saveConnection").onclick=async()=>{API_BASE=$("apiBase").value.trim().replace(/\/$/,"");CONTROL_TOKEN=$("controlToken").value.trim();localStorage.setItem("TRADING_API_BASE",API_BASE);localStorage.setItem("TRADING_CONTROL_TOKEN",CONTROL_TOKEN);await health();await liveStatus();await account();await loadMarket()};
$("test").onclick=async()=>{await health();await liveStatus();$("connection").textContent="API: "+API_BASE+"\n관제 토큰: "+(CONTROL_TOKEN?"설정됨":"미설정")};
$("apiBase").value=API_BASE;$("controlToken").value=CONTROL_TOKEN;
health();liveStatus();account();loadMarket();
setInterval(health,10000);setInterval(liveStatus,10000);setInterval(account,15000);setInterval(loadMarket,15000);
addEventListener("resize",()=>market&&drawChart(market.candles));
