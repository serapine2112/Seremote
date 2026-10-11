# Seremote

Control your Windows PC from a browser. Seremote streams your screen as
JPEG frames, and the clicks and typing you do in the browser are sent
back to the PC.

I created this because I want to spend my gabut time

## What it can do
- Live view of the main monitor
- Left click, right click, double click, drag, and scroll
- Send text (up to 500 characters) and Enter, Backspace, Tab, Esc
- Change resolution (240p to 1080p), FPS (5 to 60), and JPEG quality
- Five presets, from "hemat" (low data) to "detail" (sharp)

## How it works
A background thread grabs the screen with MSS, shrinks it with Pillow,
and compresses it to JPEG. Flask sends the latest frame to the browser
as a continuous stream.

When you click in the browser, it sends the position as a percentage
(0 to 1) instead of pixels. The server turns that into the real pixel
on the PC and uses PyAutoGUI to click. This way it works at any
resolution.

Control requests need a random token that is generated each time the
server starts.

## Run it
    pip install flask mss pillow pyautogui
    python server.py

Then open http://127.0.0.1:5050

## Limits
- Local only for now. The server accepts 127.0.0.1 only, so a phone
  or another PC can't connect yet.
- Only the main monitor is captured.
- No audio.
- Not safe to put on the internet. The security is basic.
- This is still in development, don't expect too much on me please :'O

## What I'm planning
- Try remote access with Tailscale
- Better security before allowing other devices


---
By [serapine2112](https://github.com/serapine2112)