
from flask import Flask, Response, request, jsonify, render_template
from mss import MSS
from PIL import Image
import pyautogui
import io
import time
import secrets
import threading
import math


app = Flask(__name__)

TOKEN = secrets.token_urlsafe(32)

RESOLUTIONS = (240, 360, 480, 720, 1080)
FPS_OPTIONS = (5, 15, 30, 45, 60)

PRESETS = {
    "hemat": {"resolution": 360, "fps": 5, "quality": 35},
    "ringan": {"resolution": 480, "fps": 15, "quality": 45},
    "balanced": {"resolution": 720, "fps": 15, "quality": 50},
    "smooth": {"resolution": 720, "fps": 30, "quality": 55},
    "detail": {"resolution": 1080, "fps": 30, "quality": 65}
}

settings = dict(PRESETS["ringan"])
settings_lock = threading.Lock()

frame_condition = threading.Condition()
latest_frame = None
frame_sequence = 0

input_lock = threading.Lock()
drag_active = False
last_drag_activity = 0.0

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


def local_request():
    return request.remote_addr in ("127.0.0.1", "::1")


def authorized():
    return local_request() and secrets.compare_digest(
        request.headers.get("X-Remote-Token", ""),
        TOKEN
    )


def capture_worker():
    global latest_frame, frame_sequence

    with MSS() as screen:
        monitor = screen.monitors[1]

        while True:
            started = time.monotonic()

            with settings_lock:
                config = dict(settings)

            try:
                shot = screen.grab(monitor)

                image = Image.frombytes(
                    "RGB",
                    shot.size,
                    shot.rgb
                )

                if image.height > config["resolution"]:
                    width = max(
                        1,
                        round(
                            image.width
                            * config["resolution"]
                            / image.height
                        )
                    )

                    image = image.resize(
                        (width, config["resolution"]),
                        Image.Resampling.BILINEAR
                    )

                buffer = io.BytesIO()

                image.save(
                    buffer,
                    format="JPEG",
                    quality=config["quality"],
                    optimize=False
                )

                frame = buffer.getvalue()

                with frame_condition:
                    latest_frame = frame
                    frame_sequence += 1
                    frame_condition.notify_all()

            except Exception as exc:
                print("Capture error:", exc)
                time.sleep(1)

            remaining = (
                1 / config["fps"]
                - (time.monotonic() - started)
            )

            if remaining > 0:
                time.sleep(remaining)


def generate_frames():
    last_sequence = -1

    while True:
        with frame_condition:
            frame_condition.wait_for(
                lambda: (
                    frame_sequence != last_sequence
                    and latest_frame is not None
                ),
                timeout=10
            )

            if (
                latest_frame is None
                or frame_sequence == last_sequence
            ):
                continue

            frame = latest_frame
            last_sequence = frame_sequence

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame
            + b"\r\n"
        )


def get_position(data):
    x = float(data["x"])
    y = float(data["y"])

    if not all(
        math.isfinite(value) and 0 <= value <= 1
        for value in (x, y)
    ):
        raise ValueError("Invalid coordinates")

    with MSS() as screen:
        monitor = screen.monitors[1]

    return (
        monitor["left"]
        + round(x * (monitor["width"] - 1)),
        monitor["top"]
        + round(y * (monitor["height"] - 1))
    )


@app.after_request
def response_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.route("/")
def home():
    if not local_request():
        return "Local access only", 403

    return render_template(
        "test.html",
        token=TOKEN
    )


@app.route("/video_feed")
def video_feed():
    if not local_request():
        return jsonify(
            error="Local access only"
        ), 403

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/settings", methods=["GET", "POST"])
def streaming_settings():
    if not authorized():
        return jsonify(
            error="Unauthorized"
        ), 401

    if request.method == "GET":
        with settings_lock:
            return jsonify(dict(settings))

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error="Invalid settings"
        ), 400

    try:
        resolution = int(data["resolution"])
        fps = int(data["fps"])
        quality = int(data["quality"])

        if (
            resolution not in RESOLUTIONS
            or fps not in FPS_OPTIONS
            or not 25 <= quality <= 80
        ):
            raise ValueError()

    except (ValueError, TypeError, KeyError):
        return jsonify(
            error="Invalid settings"
        ), 400

    with settings_lock:
        settings.update(
            resolution=resolution,
            fps=fps,
            quality=quality
        )

        return jsonify(dict(settings))


@app.route("/control", methods=["POST"])
def control():
    global drag_active, last_drag_activity

    if not authorized():
        return jsonify(
            error="Unauthorized"
        ), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error="Invalid request"
        ), 400

    action = data.get("action")

    allowed_actions = (
        "left",
        "right",
        "double",
        "down",
        "move",
        "up",
        "scroll",
        "text",
        "key"
    )

    if action not in allowed_actions:
        return jsonify(
            error="Invalid action"
        ), 400

    try:
        with input_lock:
            if (
                drag_active
                and time.monotonic() - last_drag_activity > 4
            ):
                pyautogui.mouseUp()
                drag_active = False

            if action in (
                "left",
                "right",
                "double",
                "down",
                "move"
            ):
                x, y = get_position(data)

                if action == "left":
                    pyautogui.click(x, y)

                elif action == "right":
                    pyautogui.click(
                        x,
                        y,
                        button="right"
                    )

                elif action == "double":
                    pyautogui.doubleClick(
                        x,
                        y,
                        interval=0.12
                    )

                elif action == "down":
                    if drag_active:
                        pyautogui.mouseUp()

                    pyautogui.moveTo(x, y)
                    pyautogui.mouseDown()

                    drag_active = True
                    last_drag_activity = time.monotonic()

                elif action == "move" and drag_active:
                    pyautogui.moveTo(x, y)
                    last_drag_activity = time.monotonic()

            elif action == "up":
                if drag_active:
                    if "x" in data and "y" in data:
                        x, y = get_position(data)
                        pyautogui.moveTo(x, y)

                    pyautogui.mouseUp()
                    drag_active = False

            elif action == "scroll":
                amount = int(data["amount"])

                if not -10 <= amount <= 10:
                    raise ValueError()

                pyautogui.scroll(amount)

            elif action == "text":
                value = data["text"]

                if (
                    not isinstance(value, str)
                    or len(value) > 500
                ):
                    raise ValueError()

                pyautogui.write(
                    value,
                    interval=0.01
                )

            elif action == "key":
                key = data["key"]

                if key not in (
                    "enter",
                    "backspace",
                    "tab",
                    "esc"
                ):
                    raise ValueError()

                pyautogui.press(key)

    except (ValueError, KeyError, TypeError):
        return jsonify(
            error="Invalid input"
        ), 400

    except pyautogui.FailSafeException:
        drag_active = False

        return jsonify(
            error="Failsafe triggered"
        ), 409

    return jsonify(success=True)


if __name__ == "__main__":
    threading.Thread(
        target=capture_worker,
        daemon=True
    ).start()

    print()
    print("Seremote Server Started")
    print("http://127.0.0.1:5050")
    print()

    app.run(
        host="127.0.0.1",
        port=5050,
        threaded=True,
        debug=False,
        use_reloader=False
    )
