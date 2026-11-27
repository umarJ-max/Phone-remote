# Phone Remote

Control your Windows laptop from your phone while you lean back in your chair.
Built for watching **YouTube** and **VLC**, with a touchpad, typing and power controls too.

One Python file. No installs. Dark interface that is easy on the eyes at night.

## Features

- **Media:** big -10s / +10s buttons, 5s and 1 min skips, play/pause, volume, mute, fullscreen, next/prev, playback speed, subtitles. Hold a button to repeat it.
- **YouTube / VLC switch:** the same buttons send the right keys for each player.
- **Mouse:** a touchpad on your phone (move, tap to click, two-finger scroll, two-finger tap for right click, drag).
- **Keys:** type text from your phone, arrow keys, Esc, Tab, Alt+Tab, new/close tab, address bar, refresh and more.
- **Power:** lock, screen off, shutdown in 1 minute (with confirmation and cancel).
- **PIN protection:** the phone asks for the PIN once, five wrong tries lock that device for a minute, and only devices on your local network can connect.

## Requirements

- Windows 10 or 11
- Python 3.8 or newer (no extra packages, see `requirements.txt`)
- Phone and laptop on the same Wi-Fi

## Quick start

1. Download `remote.py`.
2. Open it in a text editor and change the PIN near the top:
   ```python
   PIN = os.environ.get("REMOTE_PIN", "1234")
   ```
   Or set it without editing the file:
   ```
   set REMOTE_PIN=your-secret-pin
   ```
3. Run it:
   ```
   python remote.py
   ```
4. Allow Python through Windows Firewall on **Private** networks when asked.
5. Open the address it prints (for example `http://192.168.1.5:8765`) in your phone's browser and enter the PIN.

Tip: add the page to your phone's home screen for one-tap access.

To start it automatically with Windows, put a shortcut to `remote.py` in the Startup folder (`Win+R`, then `shell:startup`).

## How it works

The laptop runs a tiny web server. The page on your phone sends button presses to it, and the server turns them into real key presses and mouse movements with the Windows API. Because it presses keys, the video window must be the one in front on the laptop (click the video once).

Default keys sent:

| Action | YouTube | VLC |
|---|---|---|
| Back / forward 10s | `J` / `L` | `Alt+Left` / `Alt+Right` |
| Back / forward 5s | `Left` / `Right` | `Shift+Left` / `Shift+Right` |
| Play / pause | `K` | `Space` |
| Fullscreen | `F` | `F` |

You can edit the `YT` and `VLC` tables in `remote.py` to change them.

## Security

- This remote controls your whole laptop, so **change the PIN**.
- It uses plain HTTP, so use it on your **home Wi-Fi only**, never on public or shared networks.
- Do not forward the port on your router.
- Use the **Forget PIN** button (Power tab) if someone else might use your phone.
- Close the program when you are not using it.

## Options

| Setting | How |
|---|---|
| PIN | `REMOTE_PIN` environment variable, or edit the file |
| Port (default 8765) | `REMOTE_PORT` environment variable |

## Troubleshooting

- **Page does not load on phone:** check both devices are on the same Wi-Fi, and that Windows Firewall allows Python on Private networks. Make sure the laptop's network is set to Private.
- **Buttons do nothing:** click the video window first so it has focus.
- **A VLC key does not work:** check Tools > Preferences > Hotkeys, since defaults can differ between versions.

## License

MIT, free to use and modify.
