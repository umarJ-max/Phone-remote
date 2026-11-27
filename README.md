# Phone Remote

Control your Windows laptop from your phone while you lean back in your chair.
Built for **YouTube** and **VLC**, with a touchpad, typing, app switching and power controls too.

- One Python file, **no installs** (standard library only)
- Dark interface that is easy on the eyes at night
- Works over your home Wi-Fi, protected by a PIN

## Versions

| | **V1** (`remote_v1.py`) | **V2** (`remote_v2.pyw`) |
|---|---|---|
| Console window | Yes, stays open | **No, runs hidden** |
| How to start | `python remote_v1.py` | Double-click the file |
| Address to open on phone | Printed in the console | Shown in a popup on start |
| How to stop | `Ctrl+C`, or *Power > Stop remote* | *Power > Stop remote*, or end `pythonw.exe` in Task Manager |
| Writes files to disk | No | No |
| Best for | Trying it out, development, seeing errors | Everyday use, auto-start with Windows |

Both versions have exactly the same remote control page and features. Pick one.

## Requirements

- Windows 10 or 11
- Python 3.8 or newer (no extra packages, see `requirements.txt`)
- Phone and laptop on the same Wi-Fi

## Quick start

1. Download `remote_v1.py` or `remote_v2.pyw`.
2. Open it in a text editor and set your own PIN near the top:
   ```python
   PIN = os.environ.get("REMOTE_PIN", "1234")
   ```
3. Start it:
   - **V1:** run `python remote_v1.py` and keep the window open.
   - **V2:** double-click `remote_v2.pyw`. A popup shows the address.
4. Allow Python through Windows Firewall on **Private** networks when asked.
5. Open the address (for example `http://192.168.1.5:8765`) in your phone's browser and enter the PIN. The phone remembers it.

Tips:
- Add the page to your phone's home screen for one-tap access.
- To start V2 with Windows, put a shortcut to `remote_v2.pyw` in the Startup folder (`Win+R`, then `shell:startup`).
- If the laptop's IP address changes, use the new address shown at the next start.

## Using the remote

| Tab | What it does |
|---|---|
| **Media** | Big -10s / +10s and play/pause, 5s and 1 min skips, volume, mute, fullscreen, next/prev, speed, subtitles. Hold a button to repeat. YouTube / VLC switch. *Last app* (`Alt+Tab`) toggles your two most recent windows. *Any app* is the global play/pause media key. In YouTube mode, 0-9 jump to that part of the video. |
| **Apps** | Nine buttons for `Win+1` ... `Win+9` (the Nth icon on your taskbar). A window switcher: *Next* / *Prev* cycle through every open window, *Go* picks it, *Cancel* backs out. *Task view* opens the Windows overview. |
| **Mouse** | Touchpad: one finger moves, tap clicks, two fingers scroll, two-finger tap right-clicks. Left, Right, Double and Drag buttons. |
| **Keys** | Type text from your phone, arrows and OK, Esc, Backspace, Tab, previous / next / new / close browser tab, address bar, refresh, show desktop (`Win+D`), Start, Alt+F4. |
| **Power** | Lock, screen off, shutdown in 1 minute (with confirm and cancel), stop the remote, forget the PIN on this phone. |

Because the remote presses real keys, **the video window must be the one in front** on the laptop. Click the video once.

### Default keys

| Action | YouTube | VLC |
|---|---|---|
| Back / forward 10s | `J` / `L` | `Alt+Left` / `Alt+Right` |
| Back / forward 5s (3s in VLC) | `Left` / `Right` | `Shift+Left` / `Shift+Right` |
| Back / forward 1 min | `J` x6 / `L` x6 | `Ctrl+Left` / `Ctrl+Right` |
| Play / pause | `K` | `Space` |
| Fullscreen | `F` | `F` |
| Mute | `M` | `M` |
| Subtitles | `C` | `V` |
| Next / previous | `Shift+N` / `Shift+P` | `N` / `P` |
| Slower / faster | `Shift+,` / `Shift+.` | `[` / `]` |
| Jump to 0-90% | `0` ... `9` | not available |

VLC hotkeys can differ between versions: check *Tools > Preferences > Hotkeys*.

## Configuration

| Setting | How |
|---|---|
| PIN | Edit `PIN` in the file, or (V1) set the `REMOTE_PIN` environment variable |
| Port (default `8765`) | `REMOTE_PORT` environment variable |

## Security

- This remote controls your **whole laptop**. Change the PIN from `1234`.
- It uses plain HTTP, so use it on your **home Wi-Fi only**. Never use it on public or shared networks.
- Do not forward the port on your router.
- Only devices on a local/private network are accepted. Anything else gets `403`.
- Five wrong PINs lock that device out for a minute.
- Use **Power > Forget PIN on this phone** if someone else might use your phone.
- Stop the remote when you are not using it.

## Troubleshooting

- **Page does not load on the phone:** check both devices are on the same Wi-Fi, that Windows Firewall allows Python on **Private** networks, and that the laptop's network is set to Private.
- **Buttons do nothing:** click the video window first so it has focus.
- **"Already running" message:** another copy is using the port. Stop it with *Power > Stop remote* (or Task Manager) and start again.
- **V2 does nothing when double-clicked:** make sure `.pyw` files open with Python (`pythonw.exe`). If not, right-click > *Open with* > Python. Run V1 in a console to see error messages.

---

## For developers

### How it works

The laptop runs a small web server (`http.server`). The phone loads one HTML page from it. Every button sends a JSON message to `POST /api`, and the server turns it into real input with the Windows API through `ctypes`:

| Input | Win32 call |
|---|---|
| Key presses | `keybd_event` |
| Mouse move, click, wheel | `mouse_event` |
| Typed text | `SendInput` with Unicode events |
| Lock / screen off | `LockWorkStation`, `SC_MONITORPOWER` message |
| Shutdown | `shutdown /s /t 60` (cancel with `shutdown /a`) |

Everything lives in one file on purpose, so a user only has to download one thing. The page (HTML, CSS and JavaScript) is the `PAGE` string inside the Python file.

### V1 vs V2

`remote_v2.pyw` is `remote_v1.py` plus a few lines. When the interpreter is `pythonw.exe` there is no console, so V2:

1. discards `stdout` / `stderr` (writes nothing to disk),
2. shows the address and "already running" messages in a Windows message box (`MessageBoxW`) instead of printing them.

Keep the two files in sync: any feature change should be made in both. `diff remote_v1.py remote_v2.pyw` shows the only differences.

### Project layout

```
remote_v1.py       console version
remote_v2.pyw      hidden-window version
requirements.txt   (no packages, documents the Python / OS requirement)
README.md
LICENSE
```

### Code map (both files)

| Section | What is in it |
|---|---|
| Windows input layer | `VK` key table, `key_combo`, `key_down` / `key_up`, mouse and text helpers, power functions |
| What each button does | `SYS` (works in every mode), `YT`, `VLC`, `POWER` tables |
| `PAGE` | The phone UI: tabs, touchpad, hold-to-repeat buttons |
| Server | `dispatch()` runs commands, `Handler` does PIN check, lockout and local-network check |

### API

`POST /api` with a JSON body. Every request includes `"pin"`.

| `cmd` | Fields | Notes |
|---|---|---|
| `key` | `mode` (`yt` / `vlc`), `act` | Looks up `act` in the mode table, then in `SYS` |
| `move` | `dx`, `dy` | Relative mouse move |
| `scroll` | `dy` | Mouse wheel |
| `click` | `b`: `left`, `right`, `double`, `ldown`, `lup` | `ldown` / `lup` are used for drag |
| `type` | `text` (max 500 chars), `enter` | Sends Unicode text |
| `switch` | `act`: `next`, `prev`, `go`, `cancel` | Holds `Alt` between taps; auto-released after 10 s of inactivity |
| `power` | `act`: `lock`, `screenoff`, `shutdown`, `cancel`, `quit` | `quit` stops the server |

Responses: `200` ok, `400` bad request, `403` wrong PIN or not a local address, `413` body too large, `429` locked out.

Any command other than `switch` releases a held `Alt` first, so `Alt` can never get stuck.

### Adding a button

1. **Add the action** to a table. For a key combo that works everywhere, add it to `SYS`; for a player-specific one, add it to `YT` and `VLC`:
   ```python
   SYS["screenshot"] = K("WIN", "SHIFT", "S")
   ```
   Key names come from the `VK` table (add new ones there).
2. **Add the button** in the `PAGE` HTML: `<button data-k="screenshot"><b>Snip</b></button>`. Add `data-rep` to repeat while held, or `data-confirm="..."` to ask first.
3. Make the same change in the other version file.

### Testing without Windows

Set `REMOTE_DRY=1` and the server prints each action instead of pressing keys, so you can work on the UI and API on any OS:

```
REMOTE_DRY=1 REMOTE_PIN=4321 REMOTE_PORT=8799 python remote_v1.py
curl -X POST localhost:8799/api -H "Content-Type: application/json" \
     -d '{"pin":"4321","cmd":"key","mode":"yt","act":"back10"}'
```

### Design notes

- **Standard library only:** nothing to install, nothing to break.
- **Keep-alive and `TCP_NODELAY`:** taps feel instant.
- **Hold-to-repeat** is done in the page (first fire, then a repeat timer), not on the server.
- **Touchpad** batches movement and sends one request at a time, so slow Wi-Fi cannot build a backlog.
- **Security:** PIN compared in constant time, per-IP lockout, private-network-only, request size limit, confirmation on destructive actions. It is still plain HTTP: HTTPS would need certificates the phone does not trust.

### Ideas for contributions

Brightness slider, "next episode" button, more player profiles (Netflix, Spotify, PowerPoint), customizable button layouts, optional HTTPS.

## License

MIT, see `LICENSE`.
