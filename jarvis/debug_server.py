"""Developer debug console — `jarvis debug`.

A dependency-free web dashboard (http.server + polling JS) to develop and
tune JARVIS without the device:

  - chat tester with live streamed answers
  - pipeline trace: RAG queries with per-chunk scores vs threshold, LLM
    rounds, tool calls with arguments/results, timings
  - RAG inspector: try any query against the knowledge base
  - emotion animation previews (the exact faces shown on the LCD)
  - knowledge retrain button, conversation reset, config overview

Bind host/port with JARVIS_DEBUG_HOST / JARVIS_DEBUG_PORT (defaults
127.0.0.1:17870; set host 0.0.0.0 to reach a Pi from your laptop).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config, emotions, knowledge, memory, skills, trace
from .chat import ChatSession
from .llm import OllamaLLM


class DebugState:
    def __init__(self, backend=None, echo=False):
        self.tracer = trace.Tracer(echo=echo)
        self.session = ChatSession(backend=backend, tracer=self.tracer)
        self.lock = threading.Lock()
        self.busy = False
        self.question = ""
        self.answer = ""
        self.thinking = ""
        self.exchanges = []  # [{q, a}]

    def ask_async(self, text):
        with self.lock:
            if self.busy:
                return False
            self.busy = True
            self.question = text
            self.answer = ""
            self.thinking = ""
        threading.Thread(target=self._run, args=(text,), daemon=True).start()
        return True

    def _run(self, text):
        def on_content(chunk):
            with self.lock:
                self.answer += chunk

        def on_thinking(chunk):
            with self.lock:
                self.thinking += chunk

        try:
            final = self.session.ask(
                text, on_content=on_content, on_thinking=on_thinking
            )
        except Exception as err:
            final = "error: %s" % err
            with self.lock:
                self.answer = final
        with self.lock:
            self.exchanges.append({"q": text, "a": final or self.answer})
            self.exchanges = self.exchanges[-30:]
            self.busy = False

    def train_async(self, rebuild=False):
        def log(message):
            self.tracer.emit("train", message=str(message))

        def run():
            try:
                knowledge.train(rebuild=rebuild, log=log)
                self.session.store = knowledge.open_store()
            except Exception as err:
                self.tracer.emit("train", message="FAILED: %s" % err)
            with self.lock:
                self.busy = False

        with self.lock:
            if self.busy:
                return False
            self.busy = True
        threading.Thread(target=run, daemon=True).start()
        return True

    def snapshot(self):
        llm = OllamaLLM()
        stats = self.session.store.stats()
        with self.lock:
            return {
                "backend": self.session.backend,
                "model": getattr(self.session.llm, "model", "-"),
                "endpoint": llm.endpoint,
                "ollama_reachable": llm.available(timeout=1),
                "busy": self.busy,
                "question": self.question,
                "answer": self.answer,
                "thinking": self.thinking,
                "exchanges": list(self.exchanges),
                "knowledge": {
                    "chunks": stats["chunks"],
                    "files": stats["files"],
                    "signature": stats["embed_signature"],
                    "threshold": knowledge.score_threshold(self.session.store),
                    "by_source": stats["by_source"],
                },
                "skills": skills.discover(),
                "memory": memory.facts(),
                "emotions_available": emotions.available(),
            }


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>JARVIS debug console</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box;margin:0}
body{background:#10151c;color:#dbe3ec;font:14px/1.5 system-ui,sans-serif;padding:14px}
h1{font-size:16px;margin-bottom:8px}
h2{font-size:13px;color:#8fa3b8;text-transform:uppercase;letter-spacing:.08em;margin:0 0 8px}
.grid{display:grid;grid-template-columns:minmax(320px,1fr) minmax(380px,1.2fr);gap:14px}
.card{background:#1a2230;border:1px solid #2a3547;border-radius:10px;padding:12px;margin-bottom:14px}
#hdr{display:flex;gap:16px;flex-wrap:wrap;align-items:center}
.badge{background:#233047;border-radius:6px;padding:2px 10px;font-size:12px}
.ok{color:#7fdc9a}.bad{color:#ff8f8f}
#log{max-height:340px;overflow-y:auto;display:flex;flex-direction:column;gap:8px}
.q{align-self:flex-end;background:#2b4a75;border-radius:10px 10px 2px 10px;padding:6px 10px;max-width:85%}
.a{align-self:flex-start;background:#233047;border-radius:10px 10px 10px 2px;padding:6px 10px;max-width:85%;white-space:pre-wrap}
.think{color:#8fa3b8;font-style:italic;font-size:12px;white-space:pre-wrap}
input,button{font:inherit;border-radius:8px;border:1px solid #2a3547;background:#121926;color:#dbe3ec;padding:8px 10px}
input{width:100%}
button{cursor:pointer;background:#2b4a75;border:none;padding:8px 14px}
button.sec{background:#233047}
#askrow{display:flex;gap:8px;margin-top:10px}
#trace{max-height:420px;overflow-y:auto;font-family:ui-monospace,monospace;font-size:12px}
.ev{border-bottom:1px solid #222c3d;padding:4px 0}
.k{display:inline-block;min-width:96px;color:#e8c268}
.k.rag{color:#7fdc9a}.k.tool_call,.k.tool_result{color:#7fb8ff}
.k.llm_error,.k.forced_answer{color:#ff8f8f}
.hit{padding-left:14px;color:#9fb2c8}
.hit b{color:#7fdc9a}.hit.miss b{color:#ff8f8f}
table{border-collapse:collapse;width:100%;font-size:13px}
td,th{border-bottom:1px solid #222c3d;padding:4px 6px;text-align:left}
.emos{display:flex;flex-wrap:wrap;gap:10px}
.emos figure{text-align:center;font-size:12px;color:#8fa3b8}
.emos img{width:96px;height:68px;object-fit:cover;border-radius:8px;background:#000}
small{color:#66788d}
</style></head><body>
<h1>JARVIS debug console</h1>
<div class="card" id="hdr"></div>
<div class="grid"><div>
  <div class="card"><h2>Chat tester</h2>
    <div id="log"></div>
    <div id="askrow">
      <input id="q" placeholder="ask JARVIS… (Enter)">
      <button onclick="ask()">Ask</button>
      <button class="sec" onclick="post('/api/reset')">Reset</button>
    </div>
  </div>
  <div class="card"><h2>RAG inspector</h2>
    <div id="askrow" style="margin:0 0 8px">
      <input id="ragq" placeholder="test a knowledge query… (Enter)">
      <button onclick="ragTest()">Search</button>
      <button class="sec" onclick="post('/api/train')">Retrain</button>
    </div>
    <div id="ragout"></div>
  </div>
  <div class="card"><h2>Emotions (LCD preview)</h2><div class="emos" id="emos"></div></div>
</div><div>
  <div class="card"><h2>Pipeline trace</h2><div id="trace"></div></div>
  <div class="card"><h2>Knowledge / skills / memory</h2><div id="info"></div></div>
</div></div>
<script>
let lastSeq=0, esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
async function post(url,body){await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});}
function ask(){const q=document.getElementById('q');if(!q.value.trim())return;post('/api/ask',{text:q.value.trim()});q.value='';}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')ask();});
document.getElementById('ragq').addEventListener('keydown',e=>{if(e.key==='Enter')ragTest();});
async function ragTest(){
  const q=document.getElementById('ragq').value.trim();if(!q)return;
  const r=await(await fetch('/api/rag?q='+encodeURIComponent(q))).json();
  document.getElementById('ragout').innerHTML =
    '<small>threshold '+r.threshold.toFixed(2)+'</small>'+ r.results.map(h=>
    '<div class="hit'+(h.used?'':' miss')+'"><b>'+h.score.toFixed(3)+'</b> ['+esc(h.source)+'] '+esc(h.content)+'</div>').join('')||'no results';
}
function evHtml(e){
  const d=e.data||{};let extra='';
  if(e.kind==='rag'&&d.results){extra=d.results.map(h=>'<div class="hit'+(h.used?'':' miss')+'"><b>'+h.score.toFixed(3)+'</b> ['+esc(h.source)+'] '+esc(h.content)+'</div>').join('');}
  const skip={results:1};
  const kv=Object.entries(d).filter(([k])=>!skip[k]).map(([k,v])=>k+'='+esc(typeof v==='object'?JSON.stringify(v):v)).join('  ');
  const t=new Date(e.ts*1000).toLocaleTimeString();
  return '<div class="ev"><span class="k '+e.kind+'">'+e.kind+'</span> <small>'+t+'</small> '+kv+extra+'</div>';
}
async function tick(){
  try{
    const s=await(await fetch('/api/state')).json();
    document.getElementById('hdr').innerHTML=
      '<span class="badge">brain: <b>'+esc(s.backend)+'</b></span>'+
      '<span class="badge">model: '+esc(s.model)+'</span>'+
      '<span class="badge">ollama: <span class="'+(s.ollama_reachable?'ok':'bad')+'">'+(s.ollama_reachable?'reachable':'offline')+'</span></span>'+
      '<span class="badge">KB: '+s.knowledge.chunks+' chunks / '+s.knowledge.files+' files</span>'+
      '<span class="badge">'+(s.busy?'⏳ working…':'idle')+'</span>';
    let log=s.exchanges.map(x=>'<div class="q">'+esc(x.q)+'</div><div class="a">'+esc(x.a)+'</div>').join('');
    if(s.busy&&s.question){log+='<div class="q">'+esc(s.question)+'</div>';
      if(s.thinking)log+='<div class="think">'+esc(s.thinking)+'</div>';
      log+='<div class="a">'+esc(s.answer||'…')+'</div>';}
    const el=document.getElementById('log');const stick=el.scrollHeight-el.scrollTop-el.clientHeight<40;
    el.innerHTML=log;if(stick)el.scrollTop=el.scrollHeight;
    document.getElementById('info').innerHTML=
      '<table><tr><th>knowledge file</th><th>chunks</th></tr>'+
      Object.entries(s.knowledge.by_source).map(([f,n])=>'<tr><td>'+esc(f)+'</td><td>'+n+'</td></tr>').join('')+'</table>'+
      '<small>embeddings: '+esc(s.knowledge.signature)+' · threshold '+s.knowledge.threshold.toFixed(2)+'</small>'+
      '<h2 style="margin-top:10px">skills</h2>'+(s.skills.map(k=>'<div>• <b>'+esc(k.name)+'</b> — '+esc(k.description)+'</div>').join('')||'<small>none</small>')+
      '<h2 style="margin-top:10px">memory</h2>'+(s.memory.map(m=>'<div>• '+esc(m)+'</div>').join('')||'<small>empty</small>');
    const tr=await(await fetch('/api/trace?since='+lastSeq)).json();
    if(tr.events.length){
      const el2=document.getElementById('trace');
      const stick2=el2.scrollHeight-el2.scrollTop-el2.clientHeight<40;
      for(const e of tr.events){el2.insertAdjacentHTML('beforeend',evHtml(e));lastSeq=e.seq;}
      while(el2.children.length>400)el2.removeChild(el2.firstChild);
      if(stick2)el2.scrollTop=el2.scrollHeight;
    }
  }catch(err){}
  setTimeout(tick,700);
}
fetch('/api/emotions').then(r=>r.json()).then(r=>{
  document.getElementById('emos').innerHTML=r.emotions.map(n=>
   '<figure><img src="/emotion.gif?name='+n.name+'"><figcaption>'+n.name+(n.custom?' *':'')+'</figcaption></figure>').join('')+
   '<small style="width:100%">* custom GIF from emotions/ — drop your own as emotions/&lt;name&gt;.gif</small>';});
tick();
</script></body></html>"""


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/state":
                self._json(state.snapshot())
            elif url.path == "/api/trace":
                since = int(parse_qs(url.query).get("since", ["0"])[0])
                self._json({"events": state.tracer.since(since)})
            elif url.path == "/api/rag":
                query = parse_qs(url.query).get("q", [""])[0]
                try:
                    results = knowledge.search(query, store=state.session.store)
                    threshold = knowledge.score_threshold(state.session.store)
                    self._json({
                        "threshold": threshold,
                        "results": [
                            {
                                "score": r["score"],
                                "source": r["payload"].get("source", "?"),
                                "used": r["score"] >= threshold,
                                "content": r["payload"].get("content", "")[:300],
                            }
                            for r in results
                        ],
                    })
                except Exception as err:
                    self._json({"threshold": 0, "results": [],
                                "error": str(err)})
            elif url.path == "/api/emotions":
                custom_dir = emotions.emotions_dir()
                import os as _os

                self._json({"emotions": [
                    {
                        "name": name,
                        "custom": _os.path.isfile(
                            _os.path.join(custom_dir, name + ".gif")
                        ),
                    }
                    for name in emotions.EMOTIONS
                ]})
            elif url.path == "/emotion.gif":
                name = parse_qs(url.query).get("name", ["idle"])[0]
                if not emotions.available() or name not in emotions.EMOTIONS:
                    self.send_error(404)
                    return
                try:
                    data = emotions.gif_bytes(name)
                except Exception:
                    self.send_error(500)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/gif")
                self.send_header("Cache-Control", "max-age=60")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                payload = {}
            if self.path == "/api/ask":
                accepted = state.ask_async(str(payload.get("text", "")).strip())
                self._json({"ok": accepted})
            elif self.path == "/api/reset":
                state.session.reset()
                state.tracer.emit("reset", by="debug-console")
                with state.lock:
                    state.exchanges = []
                    state.question = ""
                    state.answer = ""
                self._json({"ok": True})
            elif self.path == "/api/train":
                accepted = state.train_async(
                    rebuild=bool(payload.get("rebuild"))
                )
                self._json({"ok": accepted})
            else:
                self.send_error(404)

    return Handler


def run_debug_server(backend=None, echo=False):
    host = config.get("JARVIS_DEBUG_HOST", "127.0.0.1")
    port = config.get_int("JARVIS_DEBUG_PORT", 17870)
    state = DebugState(backend=backend, echo=echo)
    server = ThreadingHTTPServer((host, port), make_handler(state))
    print("[debug] JARVIS debug console: http://%s:%d  (brain: %s)"
          % (host, port, state.session.backend))
    print("[debug] set JARVIS_DEBUG_HOST=0.0.0.0 to reach it from another "
          "machine")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[debug] bye")
    return 0
