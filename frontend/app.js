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
async function loadMarket(){try{market=await (await fetch(API_BASE+"/api/paper/market/"+SYMBOL)).json();$("signal").textContent=market.signal.action;drawChart(market.candles,market.indicators);$("sma5").textContent=won(market.indicators?.sma5);$("sma20").textContent=won(market.indicators?.sma20);$("rsi14").textContent=market.indicators?.rsi14==null?"-":market.indicators.rsi14.toFixed(1);$("source").textContent=market.source}catch{}}
function drawChart(cs, indicators){
  const c=$("chart"),ctx=c.getContext("2d"),dpr=devicePixelRatio||1,w=c.clientWidth,h=280;
  c.width=w*dpr;c.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);
  const pad=28, highs=cs.map(x=>+x.highPrice), lows=cs.map(x=>+x.lowPrice);
  const min=Math.min(...lows),max=Math.max(...highs),range=Math.max(1,max-min);
  const xAt=i=>pad+i*(w-pad*2)/Math.max(1,cs.length-1);
  const yAt=v=>h-pad-(v-min)/range*(h-pad*2);
  ctx.clearRect(0,0,w,h);
  ctx.strokeStyle="#303846";ctx.lineWidth=1;
  for(let g=0;g<4;g++){const y=pad+g*(h-pad*2)/3;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-pad,y);ctx.stroke()}
  const step=Math.max(3,(w-pad*2)/cs.length*0.62);
  cs.forEach((x,i)=>{
    const px=xAt(i),o=+x.openPrice,cl=+x.closePrice,hi=+x.highPrice,lo=+x.lowPrice;
    ctx.strokeStyle=cl>=o?"#75e3a1":"#ff9a9a";ctx.fillStyle=ctx.strokeStyle;ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(px,yAt(lo));ctx.lineTo(px,yAt(hi));ctx.stroke();
    const top=yAt(Math.max(o,cl)),bottom=yAt(Math.min(o,cl));
    ctx.fillRect(px-step/2,top,Math.max(1,step),Math.max(1,bottom-top));
  });
  const values=key=>cs.map(x=>indicators&&x[key]);
  [["sma5","#f0c36a"],["sma20","#75a7ff"]].forEach(([key,color])=>{
    if(!indicators)return;
    const period=key==="sma5"?5:20;
    ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.beginPath();
    let started=false;
    cs.forEach((x,i)=>{
      if(i+1<period)return;
      const v=cs.slice(i+1-period,i+1).reduce((a,z)=>a+Number(z.closePrice),0)/period;
      const px=xAt(i),py=yAt(v);
      if(!started){ctx.moveTo(px,py);started=true}else ctx.lineTo(px,py);
    });ctx.stroke();
  });
  ctx.fillStyle="#8993a4";ctx.font="11px system-ui";ctx.fillText(won(max),8,16);ctx.fillText(won(min),8,h-6);
}
async function order(side){try{const r=await fetch(API_BASE+"/api/paper/order",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol:SYMBOL,side,quantity:Number($("orderQty").value),price:Number($("orderPrice").value)})});const d=await r.json();if(!r.ok)throw Error(d.detail||"주문 실패");await portfolio()}catch(e){alert(e.message)}}
async function testToss(){
  try{
    const r=await fetch(API_BASE+"/api/toss/status");
    const d=await r.json();
    $("tossState").textContent=d.connected?"CONNECTED":"BLOCKED";
    $("liveMode").textContent=(d.mode||"paper").toUpperCase();
    $("liveReady").textContent=d.connected&&d.mode==="live"?"READY":"BLOCKED";
  }catch{$("tossState").textContent="OFFLINE"}
}
async function runBacktest(){try{const d=await (await fetch(API_BASE+"/api/paper/backtest/"+SYMBOL)).json();$("btInitial").textContent=won(d.initial_cash);$("btFinal").textContent=won(d.final_equity);$("btPnl").textContent=(d.pnl>=0?"+":"")+won(d.pnl);$("btReturn").textContent=d.return_pct.toFixed(2)+"%";$("btDrawdown").textContent=d.max_drawdown_pct.toFixed(2)+"%";$("btWinRate").textContent=d.win_rate.toFixed(1)+"%";$("btTrades").textContent=d.trades.length+"건의 가상 체결 발생"}catch{$("btTrades").textContent="백테스트 실패"}}
$("tossTest").onclick=testToss;\n$("toggle").onclick=async()=>{try{renderHealth(await (await fetch(API_BASE+"/api/trading/toggle",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:!enabled})})).json())}catch{alert("서버 연결 실패")}};
$("buy").onclick=()=>order("BUY");$("sell").onclick=()=>order("SELL");$("backtest").onclick=runBacktest;
$("reset").onclick=async()=>{if(confirm("가상계좌를 초기화할까요?")){await fetch(API_BASE+"/api/paper/reset",{method:"POST"});await portfolio()}};
addEventListener("resize",()=>market&&drawChart(market.candles,market.indicators));health();portfolio();loadMarket();setInterval(health,10000);setInterval(portfolio,10000);setInterval(loadMarket,30000);