"""Веб-панель бота: http://localhost:<port>

Работает в фоновом потоке, показывает живую «лестницу» сетки с ордерами
и текущей ценой, профит, ленту событий и кнопку аварийного стопа.
Слушает ТОЛЬКО 127.0.0.1 — из интернета панель не видна.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("gridbot")


def _status(bot) -> dict:
    price = bot.price_cache
    has_grid = bool(bot.levels)
    return {
        "symbol": bot.cfg["symbol"],
        "testnet": bot.testnet,
        "running": bot.running,
        "price": float(price) if price is not None else None,
        "profit": float(bot.profit),
        "trades": bot.trades,
        "budget": float(bot.cfg["budget_usdt"]),
        "orders_n": len(bot.orders),
        "levels": [float(x) for x in bot.levels],
        "lower": float(bot.lower) if has_grid else None,
        "upper": float(bot.upper) if has_grid else None,
        "stop": float(bot.stop_price) if has_grid else None,
        "orders": [
            {"side": o["side"], "price": float(o["price"])}
            for o in list(bot.orders.values())
        ],
        "events": list(bot.events),
        "history": list(bot.history),
    }


def start(bot, port: int = 8899):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # не засоряем консоль
            pass

        def _send(self, code, ctype, body: bytes):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.encode())
            elif self.path == "/api/status":
                try:
                    body = json.dumps(_status(bot)).encode()
                except Exception as e:
                    body = json.dumps({"error": str(e)}).encode()
                self._send(200, "application/json", body)
            else:
                self._send(404, "text/plain", b"not found")

        def do_POST(self):
            if self.path == "/api/stop":
                bot.stop_requested = True
                self._send(200, "application/json", b'{"ok": true}')
            else:
                self._send(404, "text/plain", b"not found")

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


PAGE = """<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Grid Bot — панель</title>
<style>
  :root{--bg1:#0E1220;--bg2:#16213A;--panel:rgba(255,255,255,.055);
        --line:rgba(255,255,255,.10);--txt:#E8EAF2;--dim:rgba(232,234,242,.55);
        --gold:#FFD700;--buy:#4ADE80;--sell:#F87171;--mono:ui-monospace,Consolas,monospace}
  *{box-sizing:border-box;margin:0}
  body{font:15px/1.45 system-ui,-apple-system,sans-serif;color:var(--txt);
       background:linear-gradient(170deg,var(--bg1),var(--bg2)) fixed;min-height:100vh;padding:22px}
  header{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:18px}
  h1{font-size:21px;font-weight:700}
  .badge{font:600 12px/1 var(--mono);padding:5px 10px;border-radius:999px}
  .badge.test{background:rgba(74,222,128,.15);color:var(--buy)}
  .badge.real{background:rgba(248,113,113,.18);color:var(--sell)}
  .badge.off{background:rgba(255,255,255,.1);color:var(--dim)}
  button{margin-left:auto;background:none;border:1px solid var(--sell);color:var(--sell);
         padding:8px 16px;border-radius:10px;font:600 13px system-ui;cursor:pointer}
  button:hover{background:rgba(248,113,113,.12)}
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:18px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
  .card b{display:block;font:700 20px var(--mono);margin-top:2px}
  .card span{font-size:12px;color:var(--dim)}
  .profit-pos{color:var(--buy)} .profit-neg{color:var(--sell)}
  .grid2{display:grid;grid-template-columns:280px 1fr;gap:14px}
  @media(max-width:760px){.grid2{grid-template-columns:1fr}}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px}
  .panel h2{font-size:13px;color:var(--dim);font-weight:600;margin-bottom:10px;
            text-transform:uppercase;letter-spacing:.06em}
  /* лестница */
  #ladder{position:relative;height:440px;font:11px var(--mono)}
  .lvl{position:absolute;left:0;right:0;border-top:1px dashed rgba(255,255,255,.13)}
  .lvl span{position:absolute;right:2px;top:-15px;color:var(--dim)}
  .ord{position:absolute;left:8px;width:10px;height:10px;border-radius:50%;transform:translateY(-5px)}
  .ord.buy{background:var(--buy);box-shadow:0 0 8px rgba(74,222,128,.6)}
  .ord.sell{background:var(--sell);box-shadow:0 0 8px rgba(248,113,113,.6)}
  .priceline{position:absolute;left:0;right:0;border-top:2px solid var(--gold);
             transition:top .8s ease;z-index:2}
  .priceline span{position:absolute;left:26px;top:-19px;background:var(--gold);color:#12122B;
                  font-weight:700;padding:1px 7px;border-radius:6px}
  .stopline{position:absolute;left:0;right:0;border-top:1px solid var(--sell)}
  .stopline span{position:absolute;left:2px;top:-15px;color:var(--sell)}
  canvas{width:100%;height:170px}
  #events{list-style:none;font:12.5px var(--mono);max-height:210px;overflow-y:auto}
  #events li{padding:5px 0;border-bottom:1px solid var(--line);color:var(--dim)}
  #events li:first-child{color:var(--txt)}
  .legend{font-size:12px;color:var(--dim);margin-top:8px}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 4px 0 10px}
</style></head><body>

<header>
  <h1 id="title">Grid Bot</h1>
  <span id="mode" class="badge off">подключение…</span>
  <button onclick="stopBot()">⏹ Остановить бота</button>
</header>

<div class="stats">
  <div class="card"><span>Цена</span><b id="price">—</b></div>
  <div class="card"><span>Профит</span><b id="profit">—</b></div>
  <div class="card"><span>Сделок закрыто</span><b id="trades">—</b></div>
  <div class="card"><span>Активных ордеров</span><b id="orders">—</b></div>
</div>

<div class="grid2">
  <div class="panel">
    <h2>Лестница сетки</h2>
    <div id="ladder"></div>
    <div class="legend"><span class="dot" style="background:var(--buy)"></span>покупка
      <span class="dot" style="background:var(--sell)"></span>продажа
      <span class="dot" style="background:var(--gold)"></span>цена</div>
  </div>
  <div>
    <div class="panel" style="margin-bottom:14px">
      <h2>Профит за сессию, USDT</h2>
      <canvas id="chart" width="800" height="170"></canvas>
    </div>
    <div class="panel">
      <h2>События</h2>
      <ul id="events"><li>ожидание данных…</li></ul>
    </div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);

function fmt(x, d=4){ return x==null ? "—" : (+x).toFixed(d).replace(/\\.?0+$/,"") }

function renderLadder(s){
  const el = $("ladder");
  if(!s.levels || !s.levels.length){ el.innerHTML =
    '<div style="color:var(--dim);padding-top:40%">сетка ещё не построена</div>'; return }
  const lo0 = Math.min(s.stop ?? s.lower, s.price ?? s.lower);
  const hi0 = Math.max(s.upper, s.price ?? s.upper);
  const pad = (hi0-lo0)*0.06, lo = lo0-pad, hi = hi0+pad;
  const y = p => (1-(p-lo)/(hi-lo))*100;
  let h = "";
  for(const lvl of s.levels)
    h += `<div class="lvl" style="top:${y(lvl)}%"><span>${fmt(lvl,2)}</span></div>`;
  if(s.stop) h += `<div class="stopline" style="top:${y(s.stop)}%"><span>стоп</span></div>`;
  for(const o of s.orders)
    h += `<div class="ord ${o.side==="Buy"?"buy":"sell"}" style="top:${y(o.price)}%"></div>`;
  if(s.price!=null)
    h += `<div class="priceline" style="top:${y(s.price)}%"><span>${fmt(s.price,2)}</span></div>`;
  el.innerHTML = h;
}

function renderChart(hist){
  const c = $("chart"), ctx = c.getContext("2d");
  ctx.clearRect(0,0,c.width,c.height);
  if(!hist || hist.length<2) return;
  const vals = hist.map(h=>h[1]);
  const min = Math.min(0,...vals), max = Math.max(0.0001,...vals);
  const X = i => i/(hist.length-1)*(c.width-8)+4;
  const Y = v => c.height-8-(v-min)/(max-min)*(c.height-16);
  ctx.strokeStyle = "rgba(255,255,255,.25)"; ctx.setLineDash([4,4]);
  ctx.beginPath(); ctx.moveTo(0,Y(0)); ctx.lineTo(c.width,Y(0)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.strokeStyle = "#FFD700"; ctx.lineWidth = 2; ctx.beginPath();
  hist.forEach((h,i)=> i? ctx.lineTo(X(i),Y(h[1])) : ctx.moveTo(X(i),Y(h[1])));
  ctx.stroke();
}

async function tick(){
  try{
    const s = await (await fetch("/api/status")).json();
    $("title").textContent = "Grid Bot · " + s.symbol;
    const m = $("mode");
    if(!s.running){ m.textContent="ОСТАНОВЛЕН"; m.className="badge off" }
    else if(s.testnet){ m.textContent="TESTNET"; m.className="badge test" }
    else { m.textContent="РЕАЛЬНЫЕ ДЕНЬГИ"; m.className="badge real" }
    $("price").textContent = fmt(s.price,2);
    const p = $("profit");
    p.textContent = (s.profit>=0?"+":"")+fmt(s.profit);
    p.className = s.profit>=0 ? "profit-pos" : "profit-neg";
    $("trades").textContent = s.trades;
    $("orders").textContent = s.orders_n;
    renderLadder(s);
    renderChart(s.history);
    $("events").innerHTML = (s.events.length? s.events : ["пока тихо — сетка ждёт движения цены"])
      .map(e=>`<li>${e}</li>`).join("");
  }catch(e){ $("mode").textContent="нет связи с ботом"; $("mode").className="badge off" }
}

async function stopBot(){
  if(!confirm("Остановить бота и отменить все ордера?")) return;
  await fetch("/api/stop",{method:"POST"});
}

tick(); setInterval(tick, 3000);
</script>
</body></html>
"""
