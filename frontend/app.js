const API_BASE = localStorage.getItem("TRADING_API_BASE") || "https://ai-auto-trad.onrender.com";
const WATCH_SYMBOL = "005930";
let enabled = false;
const $ = id => document.getElementById(id);

function render() {
  $("state").textContent = enabled ? "실행 중" : "중지됨";
  $("status").textContent = enabled ? "RUNNING" : "STOPPED";
  $("status").className = "badge " + (enabled ? "running" : "stopped");
  $("toggle").textContent = enabled ? "자동매매 중지" : "자동매매 시작";
}

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

async function health() {
  try {
    const r = await fetch(API_BASE + "/health");
    if (!r.ok) throw new Error();
    const d = await r.json();
    setText("server", d.ok ? "ONLINE" : "OFFLINE");
    enabled = d.trading_enabled;
    render();
  } catch {
    setText("server", "OFFLINE");
  }
}

async function loadPrice() {
  try {
    const r = await fetch(API_BASE + "/api/price/" + WATCH_SYMBOL);
    if (!r.ok) throw new Error();
    const d = await r.json();
    const price = d?.result?.prices?.[0]?.price ?? d?.result?.price;
    if (price != null) setText("price", "₩" + Number(price).toLocaleString("ko-KR"));
  } catch {
    setText("price", "조회 실패");
  }
}

async function loadAccount() {
  try {
    const r = await fetch(API_BASE + "/api/account");
    if (!r.ok) throw new Error();
    const d = await r.json();
    const holdings = d?.result?.holdings ?? d?.result?.assets ?? [];
    setText("holdings", Array.isArray(holdings) ? holdings.length + "종목" : "연결됨");
  } catch {
    setText("holdings", "조회 실패");
  }
}

$("toggle").onclick = async () => {
  const next = !enabled;
  try {
    const r = await fetch(API_BASE + "/api/trading/toggle", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({enabled: next})
    });
    if (!r.ok) throw new Error();
    enabled = (await r.json()).trading_enabled;
    render();
  } catch {
    alert("트레이딩 서버에 연결할 수 없습니다.");
  }
};

render();
health();
loadPrice();
loadAccount();
setInterval(health, 10000);
setInterval(loadPrice, 30000);
