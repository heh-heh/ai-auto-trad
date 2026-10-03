const API_BASE = localStorage.getItem("TRADING_API_BASE") || "https://ai-auto-trad.onrender.com";
const SYMBOL = "005930";
let enabled = false;
let market = null;
const $ = id => document.getElementById(id);
const won = n => "₩" + Math.round(Number(n || 0)).toLocaleString("ko-KR");

function renderHealth(d){enabled=d.trading_enabled;$("state").textContent=enabled?"실행 중":"중지됨";$("status").textContent=enabled?"RUNNING":"STOPPED";$("status").className="badge "+(enabled?"running":"stopped");$("toggle").textContent=enabled?"자동매매 중지":"자동매매 시작"}
async function health(){try{const r=await fetch(API_BASE+"/health");if(!r.ok)throw 0;renderHealth(await r.json());$("server").textContent="ONLINE"}catch{$("server").textContent="OFFLINE"}}
async function portfolio(){try{const d=await (await fetch(API_BASE+"/api/paper/portfolio")).json();$("equity").textContent=won(d.equity);$("cash").textContent=won(d.cash);$("pnl").textContent=(d.total_pnl>=0?"+":"")+won(d.total_pnl);renderTrades(d.trades||[])}catch{}}
function renderTrades(ts){$("trades").innerHTML=ts.length?ts.slice(0,12).map(t=>'<div class="trade"><span class="'+(t.side==="BUY"?"buytext":"selltext")+'">'+t.side+" "+t.symbol+" × "+t.quantity+'</span><span>'+won(t.price)+'</span></div>').join(""):"거래 없음"}
async function loadMarket(){try{market=await (await fetch(API_BASE+"/api/paper/market/"+SYMBOL)).json();$("signal").textContent=market.signal.action;drawChart(market.candles);$("source").textContent=market.source}catch{}}
function drawChart(cs){const c=$("chart"),ctx=c.getContext("2d"),dpr=devicePixelRatio||1,w=c.clientWidth,h=280;c.width=w*dpr;c.height=h*dpr;ctx.scale(dpr,dpr);const v=cs.map(x=>+x.closePrice),min=Math.min(...v),max=Math.max(...v),pad=24;ctx.beginPath();v.forEach((x,i)=>{const px=pad+i*(w-pad*2)/(v.length-1),py=h-pad-(x-min)/(max-min)*(h-pad*2);i?ctx.lineTo(px,py):ctx.moveTo(px,py)});ctx.strokeStyle="#75a7ff";ctx.lineWidth=2;ctx.stroke();ctx.fillStyle="#8993a4";ctx.font="11px system-ui";ctx.fillText(won(max),8,16);ctx.fillText(won(min),8,h-6)}
async function order(side){try{const r=await fetch(API_BASE+"/api/paper/order",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol:SYMBOL,side,quantity:Number($("orderQty").value),price:Number($("orderPrice").value)})});const d=await r.json();if(!r.ok)throw Error(d.detail||"주문 실패");await portfolio()}catch(e){alert(e.message)}}
async function runBacktest(){try{const d=await (await fetch(API_BASE+"/api/paper/backtest/"+SYMBOL)).json();$("btInitial").textContent=won(d.initial_cash);$("btFinal").textContent=won(d.final_equity);$("btPnl").textContent=(d.pnl>=0?"+":"")+won(d.pnl);$("btReturn").textContent=d.return_pct.toFixed(2)+"%";$("btTrades").textContent=d.trades.length+"건의 가상 체결 발생"}catch{$("btTrades").textContent="백테스트 실패"}}
$("toggle").onclick=async()=>{try{renderHealth(await (await fetch(API_BASE+"/api/trading/toggle",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:!enabled})})).json())}catch{alert("서버 연결 실패")}};
$("buy").onclick=()=>order("BUY");$("sell").onclick=()=>order("SELL");$("backtest").onclick=runBacktest;
$("reset").onclick=async()=>{if(confirm("가상계좌를 초기화할까요?")){await fetch(API_BASE+"/api/paper/reset",{method:"POST"});await portfolio()}};
addEventListener("resize",()=>market&&drawChart(market.candles));health();portfolio();loadMarket();setInterval(health,10000);setInterval(portfolio,10000);setInterval(loadMarket,30000);