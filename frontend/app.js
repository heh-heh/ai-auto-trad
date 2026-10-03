const API_BASE = localStorage.getItem("TRADING_API_BASE") || "https://ai-auto-trad.onrender.com";
const SYMBOL = "005930";
let enabled = false;
let market = null;
const $ = id => document.getElementById(id);
const won = n => "₩" + Math.round(Number(n || 0)).toLocaleString("ko-KR");

function renderHealth(d){ enabled=d.trading_enabled; $("state").textContent=enabled?"실행 중":"중지됨"; $("status").textContent=enabled?"RUNNING":"STOPPED"; $("status").className="badge "+(enabled?"running":"stopped"); $("toggle").textContent=enabled?"자동매매 중지":"자동매매 시작"; }
async function health(){try{const r=await fetch(API_BASE+"/health");if(!r.ok)throw 0;renderHealth(await r.json());$("server").textContent="ONLINE"}catch{$("server").textContent="OFFLINE"}}
async function portfolio(){try{const r=await fetch(API_BASE+"/api/paper/portfolio");const d=await r.json();$("equity").textContent=won(d.equity);$("cash").textContent=won(d.cash);$("pnl").textContent=(d.total_pnl>=0?"+":"")+won(d.total_pnl);renderTrades(d.trades||[])}catch{}}
function renderTrades(trades){$("trades").innerHTML=trades.length?trades.slice(0,12).map(t=>'<div class="trade"><span class="'+(t.side==="BUY"?"buytext":"selltext")+'">'+t.side+' '+t.symbol+' × '+t.quantity+'</span><span>'+won(t.price)+'</span></div>').join(""):"거래 없음"}
async function loadMarket(){try{const r=await fetch(API_BASE+"/api/paper/market/"+SYMBOL);market=await r.json();$("signal").textContent=market.signal.action;drawChart(market.candles);$("source").textContent=market.source}catch{}}
function drawChart(candles){const c=$("chart"),ctx=c.getContext("2d"),dpr=window.devicePixelRatio||1,w=c.clientWidth,h=280;c.width=w*dpr;c.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);const vals=candles.map(x=>+x.closePrice),min=Math.min(...vals),max=Math.max(...vals),pad=24;ctx.beginPath();vals.forEach((v,i)=>{const x=pad+i*(w-pad*2)/(vals.length-1),y=h-pad-(v-min)/(max-min)*(h-pad*2);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.strokeStyle="#75a7ff";ctx.lineWidth=2;ctx.stroke();ctx.fillStyle="#8993a4";ctx.font="11px system-ui";ctx.fillText(won(max),8,16);ctx.fillText(won(min),8,h-6)}
async function order(side){const price=Number($("orderPrice").value),quantity=Number($("orderQty").value);try{const r=await fetch(API_BASE+"/api/paper/order",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol:SYMBOL,side,quantity,price})});const d=await r.json();if(!r.ok)throw new Error(d.detail||"주문 실패");await portfolio()}catch(e){alert(e.message)}}
$("toggle").onclick=async()=>{try{const r=await fetch(API_BASE+"/api/trading/toggle",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:!enabled})});renderHealth(await r.json())}catch{alert("서버 연결 실패")}};
$("buy").onclick=()=>order("BUY");$("sell").onclick=()=>order("SELL");
$("reset").onclick=async()=>{if(confirm("가상계좌를 초기화할까요?")){await fetch(API_BASE+"/api/paper/reset",{method:"POST"});await portfolio()}};
window.addEventListener("resize",()=>market&&drawChart(market.candles));
health();portfolio();loadMarket();setInterval(health,10000);setInterval(portfolio,10000);setInterval(loadMarket,30000);
