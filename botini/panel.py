#!/usr/bin/env python3
"""
botini · панель управления — единый красочный дашборд на localhost.

Запуск:   python panel.py
Открой:   http://localhost:8899

Что умеет:
  • ввод API-ключей Bybit прямо в браузере (сохраняются в bot/.env);
  • кнопка «Запустить» — пред-анализ + торговля по нескольким парам;
  • живая картина: цена, сетка, ордера, профит, портфель, лента событий;
  • кнопка «Стоп» — отменяет ордера и останавливает всё.

Слушает только 127.0.0.1 — из интернета панель не видна.
"""

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# botini подтягивает bot/exchange/notifier/backtest и настраивает логи
import botini as B  # noqa: E402

log = logging.getLogger("botini")

# ---------- лента логов для панели ----------
FEED = deque(maxlen=400)


class FeedHandler(logging.Handler):
    def emit(self, record):
        try:
            FEED.appendleft({
                "t": datetime.now().strftime("%H:%M:%S"),
                "lvl": record.levelname,
                "pair": getattr(record, "threadName", ""),
                "msg": record.getMessage(),
            })
        except Exception:
            pass


logging.getLogger().addHandler(FeedHandler())


def save_env(key: str, secret: str):
    env = ROOT / "bot" / ".env"
    env.write_text(f"BYBIT_API_KEY={key}\nBYBIT_API_SECRET={secret}\n", encoding="utf-8")


def make_cfg(testnet, rng, levels, budget_each):
    return dict(
        testnet=testnet, grid_range_pct=rng, grid_levels=levels,
        rebuild_on_breakout_up=True, breakout_confirm_polls=3,
        stop_action="stop", rebuild_cooldown_min=30, stop_loss_extra_pct=3.0,
        max_drawdown_pct=0, volatility_max_pct=1.2, poll_interval_sec=B.POLL_SEC,
        report_hour=21, heartbeat_sec=15, candle_log_sec=60,
        candle_interval=str(B.INTERVAL_MIN), web_enabled=False,  # панель агрегирует сама
    )


class Runner:
    def __init__(self):
        self.bots = []
        self.state = "idle"          # idle | starting | running | stopped | error
        self.err = None
        self.portfolio = {"equity": None, "profit": 0.0, "dd": 0.0, "initial": None}
        self.testnet = True

    def start(self, key, secret, testnet, budget, max_pairs, skip):
        if self.state in ("starting", "running"):
            return
        self.state = "starting"
        self.err = None
        self.testnet = testnet
        threading.Thread(target=self._run, name="runner", daemon=True,
                         args=(key, secret, testnet, budget, max_pairs, skip)).start()

    def _run(self, key, secret, testnet, budget, max_pairs, skip):
        try:
            save_env(key, secret)
            budget = Decimal(str(budget))
            if skip:
                chosen = [{"symbol": s, "range": 5.0, "levels": 10}
                          for s in B.CANDIDATES[:max_pairs]]
                log.info("Панель: запуск без анализа, пары %s",
                         ", ".join(c["symbol"] for c in chosen))
            else:
                log.info("Панель: анализ %d пар…", len(B.CANDIDATES))
                guess = budget / max_pairs
                scored = [r for r in (B.analyze(s, guess) for s in B.CANDIDATES) if r]
                if not scored:
                    raise RuntimeError("Анализ без данных (нет сети к Bybit?)")
                scored.sort(key=lambda x: x["worst"], reverse=True)
                chosen = [s for s in scored if s["worst"] > -5][:max_pairs]
                if not chosen:
                    raise RuntimeError("Ни одна пара не прошла анализ — рынок не для грида")

            each = (budget / len(chosen)).quantize(Decimal("0.01"))
            notifier = B.Notifier()
            run_dir = ROOT / "run"
            run_dir.mkdir(exist_ok=True)
            for c in chosen:
                lv = int(c["levels"])
                while lv > 1 and each / lv < B.ORDER_MIN_USDT:
                    lv -= 1
                cfg = make_cfg(testnet, c["range"], lv, each)
                try:
                    ex = B.Exchange(key, secret, testnet, c["symbol"])
                except Exception as e:
                    log.error("[%s] пропуск: %s", c["symbol"], e)
                    continue
                bot = B.GridBot(cfg, c["symbol"], each, ex, notifier,
                                state_file=str(run_dir / f"state_{c['symbol']}.json"))
                threading.Thread(target=bot.run, name=c["symbol"], daemon=True).start()
                self.bots.append(bot)
                time.sleep(1)
            if not self.bots:
                raise RuntimeError("Не удалось подключить ни одну пару (проверь ключи)")
            self.state = "running"
            self._portfolio_loop()
        except Exception as e:
            self.err = str(e)
            self.state = "error"
            log.error("Панель: запуск не удался — %s", e)

    def _portfolio_loop(self):
        while any(b.running for b in self.bots):
            eq = B.portfolio_equity(self.bots)
            if eq is not None:
                if self.portfolio["initial"] is None:
                    self.portfolio["initial"] = float(eq)
                init = self.portfolio["initial"]
                self.portfolio["equity"] = float(eq)
                self.portfolio["profit"] = sum(float(b.profit) for b in self.bots)
                self.portfolio["dd"] = (init - float(eq)) / init * 100 if init else 0.0
            time.sleep(12)
        if self.state == "running":
            self.state = "stopped"

    def stop(self):
        for b in self.bots:
            b.stop_requested = True
        self.state = "stopped"

    def status(self):
        pairs = []
        for b in self.bots:
            has = bool(b.levels)
            pairs.append({
                "symbol": b.symbol,
                "price": float(b.price_cache) if b.price_cache is not None else None,
                "profit": float(b.profit),
                "trades": b.trades,
                "orders_n": len(b.orders),
                "budget": float(b.budget),
                "connected": getattr(b.ex, "connected", True),
                "paused": b.paused_by_volatility,
                "running": b.running,
                "lower": float(b.lower) if has else None,
                "upper": float(b.upper) if has else None,
                "levels": [float(x) for x in b.levels] if has else [],
                "orders": [{"side": o["side"], "price": float(o["price"])}
                           for o in list(b.orders.values())],
            })
        return {
            "state": self.state,
            "err": self.err,
            "testnet": self.testnet,
            "portfolio": self.portfolio,
            "pairs": pairs,
            "feed": list(FEED)[:120],
        }


RUNNER = Runner()


def serve(port=8899):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.encode())
            elif self.path == "/api/status":
                self._send(200, "application/json",
                           json.dumps(RUNNER.status()).encode())
            else:
                self._send(404, "text/plain", b"not found")

        def do_POST(self):
            ln = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(ln) if ln else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except Exception:
                data = {}
            if self.path == "/api/start":
                RUNNER.start(
                    key=data.get("api_key", "").strip(),
                    secret=data.get("api_secret", "").strip(),
                    testnet=bool(data.get("testnet", True)),
                    budget=float(data.get("budget", 1000)),
                    max_pairs=int(data.get("max_pairs", 3)),
                    skip=bool(data.get("skip_analysis", False)),
                )
                self._send(200, "application/json", b'{"ok":true}')
            elif self.path == "/api/stop":
                RUNNER.stop()
                self._send(200, "application/json", b'{"ok":true}')
            else:
                self._send(404, "text/plain", b"not found")

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    log.info("Панель управления: http://localhost:%d  (открой в браузере)", port)
    srv.serve_forever()


PAGE = r"""<!DOCTYPE html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>botini · панель</title>
<style>
:root{
  --bg1:#0a0e1f;--bg2:#141a35;--bg3:#1d1140;
  --glass:rgba(255,255,255,.055);--line:rgba(255,255,255,.10);
  --txt:#eef1fb;--dim:rgba(238,241,251,.55);
  --up:#38f2b3;--down:#ff6b8b;--gold:#ffd54a;--cyan:#4ad9ff;--violet:#b98bff;
  --mono:ui-monospace,"SF Mono",Consolas,monospace;
}
*{box-sizing:border-box;margin:0}
body{font:15px/1.5 system-ui,-apple-system,sans-serif;color:var(--txt);min-height:100vh;
  background:
    radial-gradient(1200px 600px at 15% -10%,rgba(74,217,255,.18),transparent 60%),
    radial-gradient(1000px 600px at 110% 10%,rgba(185,139,255,.20),transparent 55%),
    linear-gradient(160deg,var(--bg1),var(--bg2) 55%,var(--bg3));
  background-attachment:fixed;padding:20px;}
.wrap{max-width:1100px;margin:0 auto}
header{display:flex;align-items:center;gap:14px;margin-bottom:20px;flex-wrap:wrap}
.logo{font:800 26px/1 system-ui;letter-spacing:.5px;
  background:linear-gradient(90deg,var(--cyan),var(--violet),var(--gold));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.pill{font:600 12px/1 var(--mono);padding:6px 12px;border-radius:999px;border:1px solid var(--line)}
.pill.test{background:rgba(56,242,179,.14);color:var(--up)}
.pill.real{background:rgba(255,107,139,.16);color:var(--down)}
.pill.idle{background:var(--glass);color:var(--dim)}
.spacer{flex:1}
button{cursor:pointer;border:none;border-radius:12px;font:600 14px system-ui;padding:11px 18px;color:#08111f}
.btn-go{background:linear-gradient(90deg,var(--cyan),var(--up));box-shadow:0 6px 20px rgba(74,217,255,.35)}
.btn-stop{background:linear-gradient(90deg,#ff7a9c,var(--down));color:#1a0510;box-shadow:0 6px 20px rgba(255,107,139,.30)}
button:active{transform:translateY(1px)}
.card{background:var(--glass);border:1px solid var(--line);border-radius:18px;padding:18px;
  backdrop-filter:blur(8px);box-shadow:0 10px 40px rgba(0,0,0,.25)}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin-bottom:14px}
label{display:block;font-size:12px;color:var(--dim);margin:12px 0 6px}
input[type=text],input[type=password],input[type=number]{width:100%;background:rgba(0,0,0,.28);
  border:1px solid var(--line);border-radius:11px;color:var(--txt);padding:12px 14px;font:14px var(--mono)}
input:focus{outline:none;border-color:var(--cyan)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.switch{display:flex;align-items:center;gap:10px;margin-top:14px;font-size:14px}
.switch input{width:18px;height:18px;accent-color:var(--cyan)}
.hint{font-size:12px;color:var(--dim);margin-top:6px}
/* портфель */
.pf{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.stat{background:var(--glass);border:1px solid var(--line);border-radius:16px;padding:14px 16px}
.stat span{font-size:12px;color:var(--dim)}
.stat b{display:block;font:800 22px/1.1 var(--mono);margin-top:6px}
.pos{color:var(--up)}.neg{color:var(--down)}
/* карточки пар */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-bottom:18px}
.pair{position:relative;overflow:hidden}
.pair .accent{position:absolute;inset:0 auto 0 0;width:4px}
.pair .top{display:flex;align-items:baseline;gap:8px}
.sym{font:800 18px var(--mono)}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.dot.on{background:var(--up);box-shadow:0 0 8px var(--up)}
.dot.off{background:var(--down);box-shadow:0 0 8px var(--down)}
.price{font:800 26px/1 var(--mono);margin:10px 0}
.mini{display:flex;gap:16px;font-size:13px;color:var(--dim);margin-bottom:12px}
.mini b{color:var(--txt);font-family:var(--mono)}
/* лестница-полоса */
.bar{position:relative;height:46px;border-radius:12px;background:rgba(0,0,0,.28);
  border:1px solid var(--line);overflow:hidden}
.bar .lvl{position:absolute;top:0;bottom:0;width:1px;background:rgba(255,255,255,.10)}
.bar .ord{position:absolute;top:50%;width:8px;height:8px;border-radius:50%;transform:translate(-50%,-50%)}
.ord.buy{background:var(--up);box-shadow:0 0 6px var(--up)}
.ord.sell{background:var(--down);box-shadow:0 0 6px var(--down)}
.bar .now{position:absolute;top:0;bottom:0;width:2px;background:var(--gold);box-shadow:0 0 10px var(--gold);transition:left .6s ease}
.badge{font:600 11px var(--mono);padding:3px 8px;border-radius:999px;margin-left:auto}
.badge.pause{background:rgba(255,213,74,.16);color:var(--gold)}
/* лента */
.feed{max-height:340px;overflow-y:auto;font:12.5px/1.7 var(--mono)}
.feed div{padding:2px 0;border-bottom:1px solid rgba(255,255,255,.05);white-space:pre-wrap}
.feed .tag{color:var(--cyan)}
.feed .warn{color:var(--gold)}.feed .err{color:var(--down)}
.tt{color:var(--dim)}
@media(max-width:620px){.row{grid-template-columns:1fr}}
</style></head><body><div class="wrap">

<header>
  <div class="logo">botini</div>
  <span id="mode" class="pill idle">не запущен</span>
  <div class="spacer"></div>
  <button id="stopBtn" class="btn-stop" style="display:none" onclick="stop()">⏹ Стоп</button>
</header>

<!-- ЭКРАН НАСТРОЙКИ -->
<div id="setup" class="card">
  <h2>Подключение и запуск</h2>
  <label>API Key (Bybit)</label>
  <input id="k" type="text" placeholder="только Spot Trade, без Withdraw" autocomplete="off">
  <label>API Secret</label>
  <input id="s" type="password" placeholder="секрет показывается на бирже один раз" autocomplete="off">
  <div class="row">
    <div><label>Бюджет, USDT (1 USDT ≈ 90–100 ₽)</label><input id="b" type="number" value="15" min="10"></div>
    <div><label>Сколько пар</label><input id="p" type="number" value="1" min="1" max="8"></div>
  </div>
  <label class="switch"><input id="tn" type="checkbox" checked> Testnet (виртуальные деньги — рекомендую)</label>
  <label class="switch"><input id="sk" type="checkbox"> Пропустить анализ (быстрый старт на дефолтных парах)</label>
  <div class="hint">Ключи сохранятся в bot/.env. Панель слушает только localhost — из интернета не видна.</div>
  <div style="margin-top:18px"><button class="btn-go" onclick="start()">🚀 Запустить</button></div>
  <div id="setupMsg" class="hint" style="color:var(--down);margin-top:12px"></div>
</div>

<!-- ДАШБОРД -->
<div id="dash" style="display:none">
  <div class="pf">
    <div class="stat"><span>Депозит портфеля</span><b id="pfEq">—</b></div>
    <div class="stat"><span>Профит суммарно</span><b id="pfPr">—</b></div>
    <div class="stat"><span>Просадка</span><b id="pfDd">—</b></div>
    <div class="stat"><span>Активных пар</span><b id="pfN">—</b></div>
  </div>
  <div id="pairs" class="grid"></div>
  <div class="card"><h2>Живая лента</h2><div id="feed" class="feed"></div></div>
</div>

<script>
const $=s=>document.querySelector(s);
const COLORS=["#4ad9ff","#b98bff","#ffd54a","#38f2b3","#ff9f6b","#7aa2ff","#ff6b8b","#66e0c0"];
const fmt=(x,d=2)=>x==null?"—":(+x).toLocaleString("ru-RU",{maximumFractionDigits:d});

async function start(){
  $("#setupMsg").textContent="";
  const body={api_key:$("#k").value,api_secret:$("#s").value,testnet:$("#tn").checked,
    budget:+$("#b").value,max_pairs:+$("#p").value,skip_analysis:$("#sk").checked};
  if(!body.api_key||!body.api_secret){$("#setupMsg").textContent="Впиши API Key и Secret.";return;}
  await fetch("/api/start",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
}
async function stop(){ if(confirm("Остановить бота и отменить все ордера?")) await fetch("/api/stop",{method:"POST"}); }

function ladder(p){
  if(!p.levels||!p.levels.length) return '<div class="bar"></div>';
  const lo=Math.min(p.lower,p.price??p.lower), hi=Math.max(p.upper,p.price??p.upper);
  const pad=(hi-lo)*0.05||1, LO=lo-pad, HI=hi+pad, X=v=>((v-LO)/(HI-LO))*100;
  let h='<div class="bar">';
  for(const l of p.levels) h+=`<div class="lvl" style="left:${X(l)}%"></div>`;
  for(const o of p.orders) h+=`<div class="ord ${o.side==='Buy'?'buy':'sell'}" style="left:${X(o.price)}%"></div>`;
  if(p.price!=null) h+=`<div class="now" style="left:${X(p.price)}%"></div>`;
  return h+'</div>';
}

function pairCard(p,i){
  const c=COLORS[i%COLORS.length];
  const pr=p.profit>=0?'pos':'neg';
  return `<div class="card pair">
    <div class="accent" style="background:${c}"></div>
    <div class="top"><span class="sym" style="color:${c}">${p.symbol}</span>
      <span class="dot ${p.connected?'on':'off'}"></span>
      ${p.paused?'<span class="badge pause">🌪 пауза</span>':''}</div>
    <div class="price">${fmt(p.price,2)}</div>
    <div class="mini">
      <div>профит <b class="${pr}">${p.profit>=0?'+':''}${fmt(p.profit,4)}</b></div>
      <div>сделок <b>${p.trades}</b></div>
      <div>ордеров <b>${p.orders_n}</b></div>
    </div>
    ${ladder(p)}
  </div>`;
}

function renderFeed(feed){
  $("#feed").innerHTML = feed.map(f=>{
    const cls=f.lvl==="ERROR"?"err":(f.lvl==="WARNING"?"warn":"");
    const tag=f.pair&&f.pair!=="MainThread"&&f.pair!=="runner"&&f.pair!=="portfolio"
      ? `<span class="tag">[${f.pair}]</span> ` : "";
    return `<div><span class="tt">${f.t}</span> ${tag}<span class="${cls}">${esc(f.msg)}</span></div>`;
  }).join("");
}
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

async function tick(){
  let s; try{ s=await (await fetch("/api/status")).json(); }catch(e){ return; }
  const m=$("#mode");
  const running=(s.state==="running"||s.state==="starting");
  $("#stopBtn").style.display=running?"block":"none";
  if(s.state==="idle"){ m.textContent="не запущен"; m.className="pill idle"; }
  else if(s.state==="starting"){ m.textContent="анализ / запуск…"; m.className="pill idle"; }
  else if(s.state==="running"){ m.textContent=s.testnet?"TESTNET · работает":"РЕАЛЬНЫЕ · работает";
    m.className="pill "+(s.testnet?"test":"real"); }
  else if(s.state==="stopped"){ m.textContent="остановлен"; m.className="pill idle"; }
  else if(s.state==="error"){ m.textContent="ошибка"; m.className="pill real"; }

  const onDash = s.state!=="idle";
  $("#setup").style.display=onDash?"none":"block";
  $("#dash").style.display=onDash?"block":"none";
  if(s.state==="error") $("#setupMsg").textContent=s.err||"ошибка запуска";

  if(onDash){
    const pf=s.portfolio||{};
    $("#pfEq").textContent=fmt(pf.equity,2)+" USDT";
    const pe=$("#pfPr"); pe.textContent=(pf.profit>=0?'+':'')+fmt(pf.profit,4);
    pe.className=pf.profit>=0?'pos':'neg';
    $("#pfDd").textContent=fmt(pf.dd,2)+" %";
    $("#pfN").textContent=(s.pairs||[]).filter(p=>p.running).length;
    $("#pairs").innerHTML=(s.pairs||[]).map(pairCard).join("");
    renderFeed(s.feed||[]);
  }
}
tick(); setInterval(tick,2000);
</script>
</div></body></html>
"""


if __name__ == "__main__":
    serve()
