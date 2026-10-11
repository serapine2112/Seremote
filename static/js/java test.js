
const config = JSON.parse(
    document.getElementById("seremote-config").textContent
);

const token = config.token;

const screen = document.getElementById("screen");
const status = document.getElementById("status");
const resolution = document.getElementById("resolution");
const fps = document.getElementById("fps");
const quality = document.getElementById("quality");

const presets = {
    hemat: {
        resolution: 360,
        fps: 5,
        quality: 35
    },
    ringan: {
        resolution: 480,
        fps: 15,
        quality: 45
    },
    balanced: {
        resolution: 720,
        fps: 15,
        quality: 50
    },
    smooth: {
        resolution: 720,
        fps: 30,
        quality: 55
    },
    detail: {
        resolution: 1080,
        fps: 30,
        quality: 65
    }
};

let mode = "left";
let dragging = false;
let dragPointer = null;
let lastMove = 0;
let pending = Promise.resolve();


function setStatus(message, error = false) {
    status.textContent = message;
    status.style.color = error ? "#ff9ca8" : "#b4a8c6";
}


async function api(path, data) {
    try {
        const response = await fetch(path, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Remote-Token": token
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) {
            throw Error(result.error || "Request failed");
        }

        return result;
    } catch (error) {
        setStatus(error.message || "Connection error", true);
        return null;
    }
}


async function send(action, data = {}) {
    const result = await api("/control", {
        action,
        ...data
    });

    if (result) {
        setStatus("Perintah berhasil: " + action);
    }

    return Boolean(result);
}


function position(event) {
    const rect = screen.getBoundingClientRect();

    const naturalWidth = screen.naturalWidth || rect.width;
    const naturalHeight = screen.naturalHeight || rect.height;

    const scale = Math.min(
        rect.width / naturalWidth,
        rect.height / naturalHeight
    );

    const displayedWidth = naturalWidth * scale;
    const displayedHeight = naturalHeight * scale;

    const left = rect.left + (rect.width - displayedWidth) / 2;
    const top = rect.top + (rect.height - displayedHeight) / 2;

    return {
        x: Math.max(
            0,
            Math.min(
                1,
                (event.clientX - left) / displayedWidth
            )
        ),
        y: Math.max(
            0,
            Math.min(
                1,
                (event.clientY - top) / displayedHeight
            )
        )
    };
}


function selectMode(next) {
    mode = next;

    document.querySelectorAll(".tool").forEach(button => {
        button.classList.remove("active");
    });

    const modeButtons = {
        left: "leftBtn",
        right: "rightBtn",
        double: "doubleBtn",
        drag: "dragBtn"
    };

    document.getElementById(
        modeButtons[mode]
    ).classList.add("active");

    document.getElementById("modeHint").textContent =
        "✦ " + mode + " aktif";
}


const modeActions = [
    ["leftBtn", "left"],
    ["rightBtn", "right"],
    ["doubleBtn", "double"],
    ["dragBtn", "drag"],
    ["resetBtn", "left"]
];

for (const [id, next] of modeActions) {
    document.getElementById(id).onclick = () => {
        selectMode(next);
    };
}


screen.addEventListener("pointerdown", event => {
    if (event.button !== 0 || dragging) {
        return;
    }

    event.preventDefault();

    const pos = position(event);

    if (mode === "drag") {
        dragging = true;
        dragPointer = event.pointerId;

        screen.setPointerCapture(event.pointerId);

        pending = pending.then(() => {
            return send("down", pos);
        });
    } else {
        pending = pending.then(() => {
            return send(mode, pos);
        });
    }
});


screen.addEventListener("pointermove", event => {
    if (!dragging || event.pointerId !== dragPointer) {
        return;
    }

    const now = Date.now();

    if (now - lastMove < 60) {
        return;
    }

    lastMove = now;

    const pos = position(event);

    pending = pending.then(() => {
        return send("move", pos);
    });
});


function stopDrag(event) {
    if (!dragging || event.pointerId !== dragPointer) {
        return;
    }

    dragging = false;
    dragPointer = null;

    const pos = position(event);

    pending = pending.then(() => {
        return send("up", pos);
    });

    if (screen.hasPointerCapture(event.pointerId)) {
        screen.releasePointerCapture(event.pointerId);
    }
}


screen.addEventListener("pointerup", stopDrag);
screen.addEventListener("pointercancel", stopDrag);


window.addEventListener("blur", () => {
    if (dragging) {
        dragging = false;
        dragPointer = null;

        pending = pending.then(() => {
            return send("up");
        });
    }
});


document.getElementById("scrollUp").onclick = () => {
    send("scroll", { amount: 3 });
};

document.getElementById("scrollDown").onclick = () => {
    send("scroll", { amount: -3 });
};


screen.addEventListener("wheel", event => {
    event.preventDefault();

    send("scroll", {
        amount: event.deltaY < 0 ? 3 : -3
    });
}, { passive: false });


document.getElementById("keyboardBtn").onclick = () => {
    const panel = document.getElementById("keyboardPanel");

    panel.classList.toggle("visible");

    if (panel.classList.contains("visible")) {
        document.getElementById("textInput").focus();
    }
};


document.getElementById("sendText").onclick = async () => {
    const input = document.getElementById("textInput");

    if (
        input.value
        && await send("text", { text: input.value })
    ) {
        input.value = "";
    }
};


document.querySelectorAll("[data-key]").forEach(button => {
    button.onclick = () => {
        send("key", {
            key: button.dataset.key
        });
    };
});


document.getElementById("fullscreenBtn").onclick = async () => {
    try {
        if (document.fullscreenElement) {
            await document.exitFullscreen();
        } else {
            await document
                .getElementById("screenbox")
                .requestFullscreen();
        }
    } catch {
        setStatus(
            "Fullscreen tidak didukung browser ini",
            true
        );
    }
};


function syncPreset() {
    document.querySelectorAll("[data-preset]").forEach(button => {
        const preset = presets[button.dataset.preset];

        const selected = (
            Number(resolution.value) === preset.resolution
            && Number(fps.value) === preset.fps
            && Number(quality.value) === preset.quality
        );

        button.classList.toggle("active", selected);
    });
}


function updateUI() {
    document.getElementById("qualityValue").textContent =
        quality.value + "%";

    syncPreset();
}


for (const input of [resolution, fps, quality]) {
    input.addEventListener("input", updateUI);
}


document.querySelectorAll("[data-preset]").forEach(button => {
    button.onclick = () => {
        const preset = presets[button.dataset.preset];

        resolution.value = preset.resolution;
        fps.value = preset.fps;
        quality.value = preset.quality;

        updateUI();
    };
});


document.getElementById("applySettings").onclick = async () => {
    const result = await api("/settings", {
        resolution: Number(resolution.value),
        fps: Number(fps.value),
        quality: Number(quality.value)
    });

    if (result) {
        document.getElementById("streamInfo").textContent =
            result.resolution + "p · " + result.fps + " FPS";

        setStatus(
            "Pengaturan streaming berhasil diterapkan"
        );
    }
};


async function loadSettings() {
    try {
        const response = await fetch("/settings", {
            headers: {
                "X-Remote-Token": token
            }
        });

        if (!response.ok) {
            throw Error("Gagal mengambil pengaturan");
        }

        const settings = await response.json();

        resolution.value = settings.resolution;
        fps.value = settings.fps;
        quality.value = settings.quality;

        document.getElementById("streamInfo").textContent =
            settings.resolution + "p · "
            + settings.fps + " FPS";

        updateUI();
    } catch (error) {
        setStatus(error.message, true);
    }
}


loadSettings();
