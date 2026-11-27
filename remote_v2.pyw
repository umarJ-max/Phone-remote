"""
Phone Remote - V2 (no console window)
Same remote as V1, but it runs hidden: double-click this .pyw file.

A popup shows the address to open on your phone. Nothing is written to disk.
Stop it from the phone: Power > Stop remote (or end pythonw.exe in Task Manager).
Set your PIN by editing PIN below.
"""
import ctypes
import hmac
import ipaddress
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PIN = os.environ.get("REMOTE_PIN", "1234")   # <-- change this
PORT = int(os.environ.get("REMOTE_PORT", "8765"))
DRY = os.environ.get("REMOTE_DRY") == "1"     # test mode: prints instead of pressing keys

# Running as a .pyw (pythonw) means there is no console: throw output away, write no files.
SILENT = sys.stdout is None or os.path.basename(sys.executable).lower() == "pythonw.exe"
if SILENT:
    sys.stdout = sys.stderr = open(os.devnull, "w")

if not DRY and sys.platform != "win32":
    sys.exit("This remote only works on Windows.")

# --------------------------------------------------------------------------
# Windows input layer
# --------------------------------------------------------------------------
VK = {
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28, "SPACE": 0x20,
    "SHIFT": 0x10, "CTRL": 0x11, "ALT": 0x12, "WIN": 0x5B,
    "ENTER": 0x0D, "ESC": 0x1B, "BACK": 0x08, "TAB": 0x09,
    "F4": 0x73, "F5": 0x74, "F11": 0x7A,
    "VOLMUTE": 0xAD, "VOLDOWN": 0xAE, "VOLUP": 0xAF, "MEDIAPLAY": 0xB3,
    "COMMA": 0xBC, "PERIOD": 0xBE, "SLASH": 0xBF,
    "LBRACKET": 0xDB, "RBRACKET": 0xDD, "EQUALS": 0xBB,
}
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    VK[_c] = ord(_c)
EXTENDED = {"LEFT", "UP", "RIGHT", "DOWN"}
KEYUP, EXT, UNI = 0x0002, 0x0001, 0x0004

if DRY:
    def _log(*a):
        print("[dry]", *a, flush=True)

    def key_combo(keys): _log("key", keys)
    def key_down(k): _log("key DOWN", k)
    def key_up(k): _log("key UP", k)
    def mouse_move(dx, dy): _log("move", dx, dy)
    def mouse_button(flag): _log("mouse button flag", hex(flag))
    def mouse_wheel(delta): _log("wheel", delta)
    def send_text(s): _log("type", repr(s))
    def lock_pc(): _log("lock")
    def screen_off(): _log("screen off")
    def shutdown_pc(): _log("shutdown in 60s")
    def cancel_shutdown(): _log("cancel shutdown")
else:
    from ctypes import wintypes as wt

    user32 = ctypes.windll.user32
    user32.mouse_event.argtypes = [wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t]
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                    ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                    ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wt.DWORD), ("u", _U)]

    user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

    def key_combo(keys):
        codes = [(VK[k], EXT if k in EXTENDED else 0) for k in keys]
        for vk, ext in codes:
            user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), ext, 0)
        for vk, ext in reversed(codes):
            user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), ext | KEYUP, 0)

    def key_down(k):
        vk = VK[k]
        user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), EXT if k in EXTENDED else 0, 0)

    def key_up(k):
        vk = VK[k]
        user32.keybd_event(vk, user32.MapVirtualKeyW(vk, 0), (EXT if k in EXTENDED else 0) | KEYUP, 0)

    def mouse_move(dx, dy):
        user32.mouse_event(0x0001, dx & 0xFFFFFFFF, dy & 0xFFFFFFFF, 0, 0)

    def mouse_button(flag):
        user32.mouse_event(flag, 0, 0, 0, 0)

    def mouse_wheel(delta):
        user32.mouse_event(0x0800, 0, 0, delta & 0xFFFFFFFF, 0)

    def _flush(units):
        if not units:
            return
        arr = (INPUT * (len(units) * 2))()
        for i, u in enumerate(units):
            for j, fl in enumerate((UNI, UNI | KEYUP)):
                e = arr[i * 2 + j]
                e.type = 1
                e.ki.wVk = 0
                e.ki.wScan = u
                e.ki.dwFlags = fl
        user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))

    def send_text(s):
        units = []
        for ch in s:
            if ch in "\r\n":
                _flush(units)
                units = []
                key_combo(["ENTER"])
                continue
            cp = ord(ch)
            if cp >= 0x10000:
                cp -= 0x10000
                units += [0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF)]
            else:
                units.append(cp)
            if len(units) >= 40:
                _flush(units)
                units = []
                time.sleep(0.01)
        _flush(units)

    def lock_pc():
        user32.LockWorkStation()

    def screen_off():
        user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)

    def shutdown_pc():
        subprocess.run(["shutdown", "/s", "/t", "60"], check=False)

    def cancel_shutdown():
        subprocess.run(["shutdown", "/a"], check=False)

# --------------------------------------------------------------------------
# What each button does
# --------------------------------------------------------------------------
def K(*keys):
    return [list(keys)]


SYS = {  # work in every mode
    "volup": K("VOLUP"), "voldown": K("VOLDOWN"), "sysmute": K("VOLMUTE"),
    "mediaplay": K("MEDIAPLAY"),
    "up": K("UP"), "down": K("DOWN"), "left": K("LEFT"), "right": K("RIGHT"),
    "enter": K("ENTER"), "esc": K("ESC"), "back": K("BACK"), "tab": K("TAB"),
    "alttab": K("ALT", "TAB"), "closetab": K("CTRL", "W"), "newtab": K("CTRL", "T"),
    "nexttab": K("CTRL", "TAB"), "prevtab": K("CTRL", "SHIFT", "TAB"),
    "addr": K("CTRL", "L"), "refresh": K("F5"), "win": K("WIN"),
    "desktop": K("WIN", "D"), "altf4": K("ALT", "F4"), "space": K("SPACE"),
    "taskview": K("WIN", "TAB"),
}

for _n in "123456789":          # Win+1 ... Win+9 = Nth taskbar icon
    SYS["app" + _n] = K("WIN", _n)

YT = {
    "back10": K("J"), "fwd10": K("L"), "back5": K("LEFT"), "fwd5": K("RIGHT"),
    "back60": [["J"]] * 6, "fwd60": [["L"]] * 6,
    "pause": K("K"), "full": K("F"), "mute": K("M"), "cc": K("C"),
    "next": K("SHIFT", "N"), "prev": K("SHIFT", "P"),
    "slower": K("SHIFT", "COMMA"), "faster": K("SHIFT", "PERIOD"),
}
for _d in "0123456789":
    YT["j" + _d] = K(_d)

VLC = {
    "back10": K("ALT", "LEFT"), "fwd10": K("ALT", "RIGHT"),
    "back5": K("SHIFT", "LEFT"), "fwd5": K("SHIFT", "RIGHT"),
    "back60": K("CTRL", "LEFT"), "fwd60": K("CTRL", "RIGHT"),
    "pause": K("SPACE"), "full": K("F"), "mute": K("M"), "cc": K("V"),
    "next": K("N"), "prev": K("P"),
    "slower": K("LBRACKET"), "faster": K("RBRACKET"),
}
ACTIONS = {"yt": YT, "vlc": VLC}
POWER = {"lock": lock_pc, "screenoff": screen_off,
         "shutdown": shutdown_pc, "cancel": cancel_shutdown}
CLICKS = {"left": (0x2, 0x4), "right": (0x8, 0x10)}

# --------------------------------------------------------------------------
# Web page (dark, phone-first)
# --------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#000000">
<title>Remote</title>
<style>
:root{color-scheme:dark;--bg:#000;--card:#111;--line:#242424;--txt:#ececec;--dim:#8a8a8a;--acc:#3b82f6;--acc2:#1d3f8f}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent;-webkit-user-select:none;user-select:none}
html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;overscroll-behavior:none}
body{display:flex;flex-direction:column;height:100dvh}
main{flex:1;min-height:0;display:flex;flex-direction:column;padding:10px 10px 0}
.tab{display:none;flex:1;min-height:0;flex-direction:column;gap:8px;overflow-y:auto}
.tab.on{display:flex}
button{font:inherit;color:inherit;border:1px solid var(--line);background:var(--card);border-radius:16px;padding:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;touch-action:manipulation;transition:transform .06s,background .06s}
button.down,button:active{background:#222;transform:scale(.97)}
button b{font-size:17px;font-weight:600}
button i{font-style:normal;font-size:11px;color:var(--dim)}
.row{display:grid;gap:8px}
.c2{grid-template-columns:repeat(2,1fr)}
.c3{grid-template-columns:repeat(3,1fr)}
.c4{grid-template-columns:repeat(4,1fr)}
.c10{grid-template-columns:repeat(10,1fr);gap:4px}
.fix{height:52px;flex:none}
.grow{flex:1;min-height:84px}
.grow b{font-size:34px}
.primary{background:var(--acc2)!important;border-color:var(--acc)!important}
.primary.down,.primary:active{background:#2a56c0!important}
.on-btn{background:var(--acc2)!important;border-color:var(--acc)!important}
.seg{display:flex;gap:6px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:4px;flex:none}
.seg button{flex:1;height:38px;border:0;border-radius:10px;background:transparent;color:var(--dim);font-weight:600}
.seg button.on{background:var(--acc2);color:#fff}
.yt-only{display:none;flex:none}
body[data-mode=yt] .yt-only{display:block}
.cap{font-size:11px;color:var(--dim);margin:2px 2px 4px}
nav{display:flex;border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom);flex:none}
nav button{flex:1;height:56px;border:0;border-radius:0;background:transparent;color:var(--dim);font-size:12px;gap:3px}
nav button b{font-size:20px;font-weight:500}
nav button.on{color:#fff;box-shadow:inset 0 2px 0 var(--acc)}
#msg{height:18px;line-height:18px;font-size:12px;color:#e5a04a;text-align:center;flex:none}
#pad{flex:1;min-height:200px;border:1px solid var(--line);border-radius:20px;background:#0a0a0a;touch-action:none;display:flex;align-items:center;justify-content:center;color:#3a3a3a;font-size:13px;text-align:center;padding:20px}
textarea,input{width:100%;background:#0a0a0a;border:1px solid var(--line);border-radius:14px;color:var(--txt);padding:12px;font:inherit;font-size:16px;resize:none;-webkit-user-select:text;user-select:text}
.stack button{height:64px;flex-direction:row;gap:10px}
.danger{border-color:#7f1d1d}
#lock{position:fixed;inset:0;background:#000;z-index:9;display:flex;align-items:center;justify-content:center;padding:24px}
#lock[hidden]{display:none}
#lock form{width:100%;max-width:320px;display:flex;flex-direction:column;gap:12px}
#lock h1{font-size:20px;margin:0 0 4px;font-weight:600}
#lock button{height:52px;background:var(--acc2);border-color:var(--acc)}
</style></head><body data-mode="yt">

<div id="lock" hidden><form id="pinform"><h1>Enter PIN</h1>
<input id="pininput" type="password" autocomplete="off" placeholder="PIN"><button>Unlock</button></form></div>

<main>
<section class="tab" id="t-media">
  <div class="seg"><button id="m-yt">YouTube</button><button id="m-vlc">VLC</button></div>
  <div class="row c2 grow">
    <button data-k="back10" data-rep><b>&minus;10</b><i>seconds</i></button>
    <button data-k="fwd10" data-rep><b>+10</b><i>seconds</i></button>
  </div>
  <div class="row grow" style="grid-template-columns:1fr">
    <button class="primary" data-k="pause"><b>&#9199;</b><i>Play / Pause</i></button>
  </div>
  <div class="row c4 fix">
    <button data-k="back60" data-rep><b>&minus;1m</b></button>
    <button data-k="back5" data-rep><b>&minus;<span class="s5">5s</span></b></button>
    <button data-k="fwd5" data-rep><b>+<span class="s5">5s</span></b></button>
    <button data-k="fwd60" data-rep><b>+1m</b></button>
  </div>
  <div class="row c4 fix">
    <button data-k="voldown" data-rep><b>Vol &minus;</b></button>
    <button data-k="volup" data-rep><b>Vol +</b></button>
    <button data-k="mute"><b>Mute</b></button>
    <button data-k="full"><b>Full</b></button>
  </div>
  <div class="row c4 fix">
    <button data-k="prev"><b>Prev</b></button>
    <button data-k="next"><b>Next</b></button>
    <button data-k="slower"><b>Slower</b></button>
    <button data-k="faster"><b>Faster</b></button>
  </div>
  <div class="row c4 fix">
    <button data-k="cc"><b>CC</b></button>
    <button data-k="esc"><b>Esc</b></button>
    <button data-k="alttab"><b>Last app</b><i>Alt+Tab</i></button>
    <button data-k="mediaplay"><b>Any app</b><i>play/pause</i></button>
  </div>
  <div class="yt-only"><div class="cap">Jump to position (0 = start, 5 = halfway)</div>
    <div class="row c10 fix" style="height:44px">
      <button data-k="j0"><b>0</b></button><button data-k="j1"><b>1</b></button><button data-k="j2"><b>2</b></button>
      <button data-k="j3"><b>3</b></button><button data-k="j4"><b>4</b></button><button data-k="j5"><b>5</b></button>
      <button data-k="j6"><b>6</b></button><button data-k="j7"><b>7</b></button><button data-k="j8"><b>8</b></button>
      <button data-k="j9"><b>9</b></button>
    </div></div>
</section>

<section class="tab" id="t-apps">
  <div class="cap">Taskbar apps: Win + number = the Nth icon on your taskbar (1 = first)</div>
  <div class="row c3" style="grid-auto-rows:64px;flex:none">
    <button data-k="app1"><b>1</b></button><button data-k="app2"><b>2</b></button><button data-k="app3"><b>3</b></button>
    <button data-k="app4"><b>4</b></button><button data-k="app5"><b>5</b></button><button data-k="app6"><b>6</b></button>
    <button data-k="app7"><b>7</b></button><button data-k="app8"><b>8</b></button><button data-k="app9"><b>9</b></button>
  </div>
  <div class="cap">Window switcher: tap Next until the window you want is highlighted on your screen, then tap Go</div>
  <div class="row c3 fix">
    <button data-w="prev"><b>&#9664; Prev</b></button>
    <button data-w="next"><b>Next &#9654;</b></button>
    <button data-w="go" class="primary"><b>Go</b></button>
  </div>
  <div class="row c2 fix">
    <button data-k="taskview"><b>Task view</b><i>then arrows + OK</i></button>
    <button data-w="cancel"><b>Cancel</b></button>
  </div>
</section>

<section class="tab" id="t-mouse">
  <div id="pad">Touchpad<br>1 finger move &middot; tap = click<br>2 fingers scroll &middot; 2-finger tap = right click</div>
  <div class="row c4 fix">
    <button data-c="left"><b>Left</b></button>
    <button data-c="right"><b>Right</b></button>
    <button data-c="double"><b>Double</b></button>
    <button id="drag"><b>Drag</b></button>
  </div>
  <div class="row c2 fix">
    <button data-s="80" data-rep><b>&#9650; Scroll up</b></button>
    <button data-s="-80" data-rep><b>&#9660; Scroll down</b></button>
  </div>
</section>

<section class="tab" id="t-keys">
  <textarea id="txt" rows="2" placeholder="Type here, then send to the laptop"></textarea>
  <div class="row c2 fix"><button id="send"><b>Type</b></button><button id="sendgo" class="primary"><b>Type + Enter</b></button></div>
  <div class="row c3" style="grid-template-rows:repeat(3,52px);flex:none">
    <span></span><button data-k="up" data-rep><b>&#9650;</b></button><span></span>
    <button data-k="left" data-rep><b>&#9664;</b></button><button data-k="enter"><b>OK</b></button><button data-k="right" data-rep><b>&#9654;</b></button>
    <span></span><button data-k="down" data-rep><b>&#9660;</b></button><span></span>
  </div>
  <div class="row c3" style="grid-auto-rows:48px;flex:none">
    <button data-k="esc"><b>Esc</b></button><button data-k="back" data-rep><b>Backspace</b></button><button data-k="tab"><b>Tab</b></button>
    <button data-k="prevtab"><b>Prev tab</b></button><button data-k="nexttab"><b>Next tab</b></button><button data-k="newtab"><b>New tab</b></button>
    <button data-k="closetab"><b>Close tab</b></button><button data-k="addr"><b>Address bar</b></button><button data-k="refresh"><b>Refresh</b></button>
    <button data-k="desktop"><b>Show desktop</b></button><button data-k="win"><b>Start</b></button>
    <button data-k="altf4" data-confirm="Close the active window?" class="danger"><b>Alt+F4</b></button>
  </div>
</section>

<section class="tab stack" id="t-power">
  <button data-p="lock"><b>Lock PC</b></button>
  <button data-p="screenoff"><b>Turn screen off</b><i>(touch the touchpad to wake)</i></button>
  <button data-p="shutdown" data-confirm="Shut down the laptop in 60 seconds?" class="danger"><b>Shut down in 1 min</b></button>
  <button data-p="cancel"><b>Cancel shutdown</b></button>
  <button data-p="quit" data-confirm="Stop the remote on the laptop? You will have to start it again from the laptop." class="danger"><b>Stop remote</b><i>(closes this program on the laptop)</i></button>
  <button id="forget"><b>Forget PIN on this phone</b><i>(you will be asked for it again)</i></button>
</section>
</main>

<div id="msg"></div>
<nav>
  <button data-tab="media"><b>&#9654;</b>Media</button>
  <button data-tab="apps"><b>&#9776;</b>Apps</button>
  <button data-tab="mouse"><b>&#9728;</b>Mouse</button>
  <button data-tab="keys"><b>&#9000;</b>Keys</button>
  <button data-tab="power"><b>&#9211;</b>Power</button>
</nav>

<script>
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
let pin=localStorage.getItem('pin')||'', mode=localStorage.getItem('mode')||'yt';
const vib=()=>{try{navigator.vibrate&&navigator.vibrate(10)}catch(e){}};
const say=t=>{$('#msg').textContent=t};
function askPin(){$('#lock').hidden=false;setTimeout(()=>$('#pininput').focus(),50)}
$('#pinform').onsubmit=e=>{e.preventDefault();pin=$('#pininput').value;localStorage.setItem('pin',pin);$('#pininput').value='';$('#lock').hidden=true;say('')};
async function api(b){
  if(!pin){askPin();return false}
  try{
    const r=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({pin:pin},b))});
    if(r.status===403){localStorage.removeItem('pin');pin='';say('Wrong PIN');askPin();return false}
    if(r.status===429){say('Too many wrong PINs. Wait a minute.');return false}
    if(!r.ok){say('Error '+r.status);return false}
    say('');return true;
  }catch(e){say('Cannot reach laptop');return false}
}
function hold(el,fn,rep){
  let t1,t2;
  const stop=()=>{clearTimeout(t1);clearInterval(t2);el.classList.remove('down')};
  el.addEventListener('pointerdown',e=>{e.preventDefault();el.classList.add('down');vib();fn();if(rep){t1=setTimeout(()=>{t2=setInterval(fn,170)},380)}});
  ['pointerup','pointercancel','pointerleave'].forEach(v=>el.addEventListener(v,stop));
  el.addEventListener('contextmenu',e=>e.preventDefault());
}
$$('[data-k]').forEach(b=>{
  const go=()=>api({cmd:'key',mode:mode,act:b.dataset.k});
  if(b.dataset.confirm){b.onclick=()=>{if(confirm(b.dataset.confirm))go()}}
  else hold(b,go,b.hasAttribute('data-rep'));
});
$$('[data-w]').forEach(b=>hold(b,()=>api({cmd:'switch',act:b.dataset.w}),false));
$$('[data-c]').forEach(b=>hold(b,()=>api({cmd:'click',b:b.dataset.c}),false));
$$('[data-s]').forEach(b=>hold(b,()=>api({cmd:'scroll',dy:+b.dataset.s}),true));
$$('[data-p]').forEach(b=>b.onclick=()=>{if(b.dataset.confirm&&!confirm(b.dataset.confirm))return;vib();api({cmd:'power',act:b.dataset.p})});

$('#forget').onclick=()=>{localStorage.removeItem('pin');pin='';askPin()};

let drag=false;
$('#drag').onclick=()=>{drag=!drag;$('#drag').classList.toggle('on-btn',drag);api({cmd:'click',b:drag?'ldown':'lup'})};

$('#send').onclick=async()=>{const t=$('#txt').value;if(t&&await api({cmd:'type',text:t,enter:false}))$('#txt').value=''};
$('#sendgo').onclick=async()=>{const t=$('#txt').value;if(await api({cmd:'type',text:t,enter:true}))$('#txt').value=''};

function setMode(m){
  mode=m;localStorage.setItem('mode',m);document.body.dataset.mode=m;
  $('#m-yt').classList.toggle('on',m==='yt');$('#m-vlc').classList.toggle('on',m==='vlc');
  $$('.s5').forEach(e=>e.textContent=m==='yt'?'5s':'3s');
}
$('#m-yt').onclick=()=>setMode('yt');$('#m-vlc').onclick=()=>setMode('vlc');
setMode(mode==='vlc'?'vlc':'yt');

function showTab(n){
  if(!$('#t-'+n))n='media';
  localStorage.setItem('tab',n);
  $$('.tab').forEach(t=>t.classList.toggle('on',t.id==='t-'+n));
  $$('nav button').forEach(b=>b.classList.toggle('on',b.dataset.tab===n));
}
$$('nav button').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
showTab(localStorage.getItem('tab')||'media');

/* touchpad */
const pad=$('#pad');
let last=null,mv={x:0,y:0},sc=0,moved=0,t0=0,fingers=0,inflight=false;
const centroid=ts=>{let x=0,y=0;for(const t of ts){x+=t.clientX;y+=t.clientY}return{x:x/ts.length,y:y/ts.length}};
async function pump(){
  if(inflight)return;
  const dx=Math.round(mv.x),dy=Math.round(mv.y),s=Math.round(sc);
  if(!dx&&!dy&&!s)return;
  mv.x-=dx;mv.y-=dy;sc-=s;inflight=true;
  if(dx||dy)await api({cmd:'move',dx:dx,dy:dy});
  if(s)await api({cmd:'scroll',dy:s});
  inflight=false;
  if(Math.abs(mv.x)>=1||Math.abs(mv.y)>=1||Math.abs(sc)>=1)pump();
}
pad.addEventListener('touchstart',e=>{
  e.preventDefault();fingers=Math.max(fingers,e.touches.length);
  if(e.touches.length===1){t0=Date.now();moved=0;fingers=1}
  last=centroid(e.touches);
},{passive:false});
pad.addEventListener('touchmove',e=>{
  e.preventDefault();
  if(!last)return;
  const c=centroid(e.touches),dx=c.x-last.x,dy=c.y-last.y;last=c;moved+=Math.abs(dx)+Math.abs(dy);
  if(e.touches.length>=2){sc+=dy}
  else{const k=1.4+Math.min(Math.hypot(dx,dy),30)/15;mv.x+=dx*k;mv.y+=dy*k}
  pump();
},{passive:false});
pad.addEventListener('touchend',e=>{
  e.preventDefault();
  if(e.touches.length===0){
    if(moved<8&&Date.now()-t0<250){vib();api({cmd:'click',b:fingers>=2?'right':'left'})}
    fingers=0;last=null;
  }else last=centroid(e.touches);
},{passive:false});
</script></body></html>
"""

# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------
LOCK = threading.Lock()
FAILS = {}  # ip -> (count, first_fail_time)


def num(v, lo, hi):
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return 0


# Window switcher: holds Alt down between taps so Tab can cycle through ALL windows.
SWITCH = {"held": False, "timer": None}


def release_alt():
    t = SWITCH["timer"]
    if t:
        t.cancel()
        SWITCH["timer"] = None
    if SWITCH["held"]:
        SWITCH["held"] = False
        key_up("ALT")


def _auto_release():            # safety: never leave Alt stuck down
    with LOCK:
        release_alt()


def arm_switch_timer():
    if SWITCH["timer"]:
        SWITCH["timer"].cancel()
    t = threading.Timer(10, _auto_release)
    t.daemon = True
    t.start()
    SWITCH["timer"] = t


import atexit
atexit.register(release_alt)


def quit_server():
    release_alt()
    threading.Timer(0.4, lambda: os._exit(0)).start()   # lets the reply go out first


POWER["quit"] = quit_server


def popup(text):
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(0, text, "Phone Remote", 0x40)
        except Exception:
            pass


def dispatch(d):
    cmd = d.get("cmd")
    with LOCK:
        if cmd != "switch":
            release_alt()       # any other action confirms the choice and frees Alt
        if cmd == "switch":
            act = d.get("act")
            if act in ("next", "prev"):
                if not SWITCH["held"]:
                    key_down("ALT")
                    SWITCH["held"] = True
                if act == "prev":
                    key_down("SHIFT"); key_combo(["TAB"]); key_up("SHIFT")
                else:
                    key_combo(["TAB"])
                arm_switch_timer()
                return True
            if act == "go":
                release_alt()
                return True
            if act == "cancel":
                if SWITCH["held"]:
                    key_combo(["ESC"])
                    release_alt()
                return True
            return False
        if cmd == "key":
            combos = ACTIONS.get(d.get("mode"), {}).get(d.get("act")) or SYS.get(d.get("act"))
            if not combos:
                return False
            for i, c in enumerate(combos):
                if i:
                    time.sleep(0.02)
                key_combo(c)
            return True
        if cmd == "move":
            mouse_move(num(d.get("dx"), -600, 600), num(d.get("dy"), -600, 600))
            return True
        if cmd == "scroll":
            mouse_wheel(max(-1200, min(1200, -num(d.get("dy"), -600, 600) * 4)))
            return True
        if cmd == "click":
            b = d.get("b")
            if b in CLICKS:
                mouse_button(CLICKS[b][0]); mouse_button(CLICKS[b][1])
            elif b == "double":
                for _ in range(2):
                    mouse_button(CLICKS["left"][0]); mouse_button(CLICKS["left"][1])
                    time.sleep(0.04)
            elif b == "ldown":
                mouse_button(CLICKS["left"][0])
            elif b == "lup":
                mouse_button(CLICKS["left"][1])
            else:
                return False
            return True
        if cmd == "type":
            send_text(str(d.get("text", ""))[:500])
            if d.get("enter"):
                key_combo(["ENTER"])
            return True
        if cmd == "power":
            fn = POWER.get(d.get("act"))
            if not fn:
                return False
            fn()
            return True
    return False


def is_local(ip):
    try:
        a = ipaddress.ip_address(ip)
        return a.is_private or a.is_loopback
    except ValueError:
        return False


def locked(ip):
    c, t = FAILS.get(ip, (0, 0))
    return c >= 5 and time.time() - t < 60


def note_fail(ip):
    c, t = FAILS.get(ip, (0, time.time()))
    if time.time() - t > 60:
        c, t = 0, time.time()
    FAILS[ip] = (c + 1, t)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # keep-alive: faster taps
    timeout = 60

    def setup(self):
        super().setup()
        try:
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

    def log_message(self, *a):
        pass

    def _reply(self, code, body=b"", ctype="text/plain", close=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not is_local(self.client_address[0]):
            return self._reply(403, close=True)
        if self.path in ("/", "/index.html"):
            self._reply(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._reply(404)

    def do_POST(self):
        ip = self.client_address[0]
        if not is_local(ip):
            return self._reply(403, close=True)
        if self.path != "/api":
            return self._reply(404, close=True)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > 8192:
                return self._reply(413, close=True)
            data = json.loads(self.rfile.read(n))
            if not isinstance(data, dict):
                raise ValueError
        except Exception:
            return self._reply(400, close=True)
        if locked(ip):
            return self._reply(429)
        if not hmac.compare_digest(str(data.get("pin", "")).encode(), PIN.encode()):
            note_fail(ip)
            time.sleep(0.5)
            return self._reply(403)
        FAILS.pop(ip, None)
        try:
            ok = dispatch(data)
        except Exception as e:
            print("error:", e)
            ok = False
        self._reply(200 if ok else 400, b"ok" if ok else b"bad")


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "YOUR-LAPTOP-IP"
    finally:
        s.close()


if __name__ == "__main__":
    url = f"http://{local_ip()}:{PORT}"
    try:
        server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError:
        msg = f"Phone Remote is already running (port {PORT} is in use).\n\nOpen this on your phone:\n{url}"
        print(msg)
        if SILENT:
            popup(msg)
        sys.exit(1)

    print(f"\nOpen on your phone:  {url}")
    if PIN == "1234":
        print("WARNING: PIN is still 1234. This remote controls your whole laptop,")
        print("         so change PIN at the top of this file.")
    print("Ctrl+C to stop\n")

    if SILENT:  # no console to read the address from, so show it in a popup
        text = (f"Phone Remote is running.\n\nOpen this on your phone:\n{url}\n\n"
                "Stop it from your phone: Power > Stop remote.")
        if PIN == "1234":
            text += "\n\nWARNING: the PIN is still 1234. Change it at the top of this file."
        threading.Thread(target=popup, daemon=True, args=(text,)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
