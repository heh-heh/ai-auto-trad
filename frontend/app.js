const API_BASE = localStorage.getItem("TRADING_API_BASE") || "http://localhost:8000";
let enabled=false;
const $=id=>document.getElementById(id);

function render(){
  $("state").textContent=enabled?"실행 중":"중지됨";
  $("status").textContent=enabled?"RUNNING":"STOPPED";
  $("status").className="badge "+(enabled?"running":"stopped");
  $("toggle").textContent=enabled?"자동매매 중지":"자동매매 시작";
}
async function health(){
  try{
    const r=await fetch(API_BASE+"/health"); const d=await r.json();
    $("server").textContent=d.ok?"ONLINE":"OFFLINE";
    enabled=d.trading_enabled; render();
  }catch{ $("server").textContent="OFFLINE"; }
}
$("toggle").onclick=async()=>{
  const next=!enabled;
  try{
    const r=await fetch(API_BASE+"/api/trading/toggle",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:next})});
    if(!r.ok) throw new Error();
    enabled=(await r.json()).trading_enabled; render();
  }catch{ alert("트레이딩 서버에 연결할 수 없습니다."); }
};
render(); health(); setInterval(health,10000);
