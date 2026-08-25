import { io } from "socket.io-client";
import "./style.css";

const imgStream = document.getElementById("imgStream");
const btnUp = document.getElementById("btnUp");
const btnLeft = document.getElementById("btnLeft");
const btnShoot = document.getElementById("btnShoot");
const btnRight = document.getElementById("btnRight");
const btnDown = document.getElementById("btnDown");

// Status/alert elements
const statusX = document.getElementById("statusX");
const statusY = document.getElementById("statusY");
const barX = document.getElementById("barX");
const barY = document.getElementById("barY");
const fireAlert = document.getElementById("fireAlert");
const badgeMode = document.getElementById("badgeMode");
const badgeScan = document.getElementById("badgeScan");
const badgeFire = document.getElementById("badgeFire");
const connStatus = document.getElementById("connStatus");

// Mode toggle elements
const modeToggleLabel = document.getElementById("modeToggleLabel");
const modeAuto = document.getElementById("modeAuto");
const modeManual = document.getElementById("modeManual");
const autoFireRow = document.getElementById("autoFireRow");
const autoFireToggle = document.getElementById("autoFireToggle");

// Auto-capture + gallery elements
const captureToggle = document.getElementById("captureToggle");
const captureGallery = document.getElementById("captureGallery");
const captureEmpty = document.getElementById("captureEmpty");
const captureCount = document.getElementById("captureCount");
const btnClearCaptures = document.getElementById("btnClearCaptures");

// Crosshair overlay elements
const crosshair = document.getElementById("crosshair");
const crosshairToggle = document.getElementById("crosshairToggle");

// Client-side mirror of the turret mode, used to guard manual commands.
let isAutoMode = true;

initialize();

function initialize() {
    imgStream.src = "/video_feed";
    attachButton(btnUp, "up");
    attachButton(btnDown, "down");
    attachButton(btnLeft, "left");
    attachButton(btnRight, "right");
    attachButton(btnShoot, "shoot");

    // Mode toggles
    modeAuto.addEventListener("click", () => setMode("auto"));
    modeManual.addEventListener("click", () => setMode("manual"));
    autoFireToggle.addEventListener("change", () => setAutoFire(autoFireToggle.checked));

    // Auto-capture toggle + gallery
    captureToggle.addEventListener("change", () => setCapture(captureToggle.checked));
    btnClearCaptures.addEventListener("click", clearCaptures);

    // Crosshair toggle (disabled by default)
    crosshairToggle.addEventListener("change", () => setCrosshair(crosshairToggle.checked));

    // Open a persistent connection so the controller knows a user
    // is connected and pauses automatic scanning.
    const socket = io();
    socket.on("connect", () => {
        console.log("Connected to controller");
        setConnStatus(true);
    });
    socket.on("disconnect", () => {
        console.log("Disconnected from controller");
        setConnStatus(false);
    });

    // Live status polling.
    setInterval(pollStatus, 1000);
    pollStatus();

    // Gallery refresh.
    setInterval(refreshCaptures, 3000);
    refreshCaptures();

    // Keyboard shortcuts.
    window.addEventListener("keydown", (e) => handleKey(e, true));
    window.addEventListener("keyup", (e) => handleKey(e, false));
}

function setConnStatus(connected) {
    connStatus.classList.toggle("badge-error", !connected);
    connStatus.classList.toggle("badge-success", connected);
    connStatus.lastChild.textContent = connected ? " Connected" : " Disconnected";
}

function pollStatus() {
    fetch("/api/status")
        .then((res) => {
            if (res.status === 502) throw new Error("Servo offline");
            return res.json();
        })
        .then((data) => {
            updateAngles(data);
            updateFire(data.fire_active);
            updateMode(data.auto_mode, data.auto_fire);
            updateCapture(data.capture_enabled);
            updateScanDirection(data.scan_direction, data.auto_mode, data.fire_active);
        })
        .catch((err) => console.error("Status poll failed:", err));
}

function updateAngles({ x, y }) {
    const xi = Number.isFinite(x) ? Math.round(x) : "--";
    const yi = Number.isFinite(y) ? Math.round(y) : "--";
    statusX.textContent = `${xi}°`;
    statusY.textContent = `${yi}°`;
    barX.value = Number.isFinite(x) ? x : 0;
    barY.value = Number.isFinite(y) ? y : 0;
}

function updateFire(active) {
    fireAlert.classList.toggle("hidden", !active);
    badgeFire.textContent = active ? "Fire: ACTIVE" : "Fire: inactive";
    badgeFire.classList.toggle("badge-error", !!active);
    badgeFire.classList.toggle("badge-outline", !active);
    if (active) badgeFire.classList.toggle("badge-outline", false);
}

function updateScanDirection(direction, auto, fireActive) {
    // Only meaningful while the scanner is actively sweeping: automatic mode
    // and no fire currently being tracked/fired.
    const scanning = auto !== false && !fireActive;
    const labels = {
        up: "↑ Up",
        right: "→ Right",
        down: "↓ Down",
        left: "← Left",
    };

    badgeScan.textContent = scanning && labels[direction]
        ? `Scan: ${labels[direction]}`
        : "Scan: —";
    badgeScan.classList.toggle("badge-primary", scanning && !!labels[direction]);
    badgeScan.classList.toggle("badge-outline", !(scanning && !!labels[direction]));
}

function updateMode(auto, autoFire) {
    const isAuto = auto !== false;
    const isAutoFire = autoFire !== false;
    isAutoMode = isAuto;

    // Mode badge + dropdown label.
    modeToggleLabel.textContent = isAuto ? "Auto" : "Manual";
    badgeMode.textContent = isAuto ? "Auto mode" : "Manual mode";
    badgeMode.classList.toggle("badge-primary", !isAuto);
    badgeMode.classList.toggle("badge-outline", isAuto);
    modeAuto.classList.toggle("active", isAuto);
    modeManual.classList.toggle("active", !isAuto);

    // Auto-fire toggle only visible in manual mode.
    autoFireRow.classList.toggle("hidden", isAuto);
    autoFireRow.classList.toggle("flex", !isAuto);
    if (autoFireToggle.checked !== isAutoFire) {
        autoFireToggle.checked = isAutoFire;
    }

    // Enable/disable manual controls.
    const manualDisabled = isAuto;
    [btnUp, btnDown, btnLeft, btnRight, btnShoot].forEach((btn) => {
        btn.classList.toggle("btn-disabled", manualDisabled);
        btn.disabled = manualDisabled;
    });
}

function setMode(mode) {
    fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
    })
        .then((res) => res.json())
        .then((data) => {
            updateMode(data.auto_mode, data.auto_fire);
            console.log("Mode set to", mode);
        })
        .catch((err) => console.error("Failed to set mode:", err));
}

function setAutoFire(enabled) {
    fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "manual", auto_fire: enabled }),
    })
        .then((res) => res.json())
        .then((data) => {
            updateMode(data.auto_mode, data.auto_fire);
            console.log("Auto-fire set to", enabled);
        })
        .catch((err) => console.error("Failed to set auto-fire:", err));
}

function updateCapture(enabled) {
    const isEnabled = enabled !== false;
    if (captureToggle.checked !== isEnabled) {
        captureToggle.checked = isEnabled;
    }
}

function setCrosshair(enabled) {
    crosshair.classList.toggle("hidden", !enabled);
}

function setCapture(enabled) {
    fetch("/api/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
    })
        .then((res) => res.json())
        .then((data) => {
            updateCapture(data.enabled);
            console.log("Auto-capture set to", enabled);
        })
        .catch((err) => console.error("Failed to set auto-capture:", err));
}

function refreshCaptures() {
    fetch("/api/captures")
        .then((res) => res.json())
        .then((data) => renderCaptures(data.captures || []))
        .catch((err) => console.error("Failed to load captures:", err));
}

function renderCaptures(captures) {
    captureCount.textContent = `${captures.length} saved`;

    // Remove existing thumbnails (keep the empty-state paragraph).
    captureGallery.querySelectorAll(".capture-item").forEach((el) => el.remove());

    captureEmpty.classList.toggle("hidden", captures.length > 0);

    captures.forEach((cap) => {
        const item = document.createElement("figure");
        item.className = "capture-item card bg-base-100 shadow";

        const img = document.createElement("img");
        img.src = `/captures/${encodeURIComponent(cap.filename)}`;
        img.alt = `Fire capture ${cap.timestamp}`;
        img.className = "h-32 w-full object-cover";
        img.loading = "lazy";

        const caption = document.createElement("figcaption");
        caption.className = "p-1 text-center text-[10px] opacity-70";
        caption.textContent = cap.timestamp;

        const del = document.createElement("button");
        del.className = "btn btn-xs btn-ghost btn-error absolute right-1 top-1";
        del.textContent = "✕";
        del.title = "Delete capture";
        del.addEventListener("click", () => deleteCapture(cap.filename));

        item.appendChild(img);
        item.appendChild(caption);
        item.appendChild(del);
        captureGallery.appendChild(item);
    });
}

function deleteCapture(filename) {
    fetch(`/api/captures/${encodeURIComponent(filename)}`, { method: "DELETE" })
        .then((res) => {
            if (!res.ok) throw new Error("Delete failed");
            refreshCaptures();
        })
        .catch((err) => console.error("Failed to delete capture:", err));
}

function clearCaptures() {
    if (!confirm("Delete all fire captures?")) return;
    fetch("/api/captures", { method: "DELETE" })
        .then((res) => {
            if (!res.ok) throw new Error("Clear failed");
            refreshCaptures();
        })
        .catch((err) => console.error("Failed to clear captures:", err));
}

function handleKey(e, pressed) {
    const dir = {
        ArrowUp: "up",
        ArrowDown: "down",
        ArrowLeft: "left",
        ArrowRight: "right",
        " ": "shoot",
    }[e.key];

    if (!dir) return;
    e.preventDefault();
    if (isAutoMode) return;
    if (pressed) startCommand(dir);
    else stopCommand(dir);
}

function sendCommand(direction, cmd) {
    if (isAutoMode) {
        console.warn("Manual commands are disabled in automatic mode.");
        return;
    }

    let url;

    if (direction === "shoot") {
        const state = cmd === "start" ? "fire" : "retract";
        url = `/api/servo/trigger?state=${state}`;
    } else {
        const mapping = {
            up:    { axis: "y", dir: "up" },
            down:  { axis: "y", dir: "down" },
            left:  { axis: "x", dir: "left" },
            right: { axis: "x", dir: "right" }
        };
        const m = mapping[direction];
        url = `/api/move?axis=${m.axis}&dir=${m.dir}&cmd=${cmd}`;
    }

    fetch(url)
        .catch(err => console.error("Request failed:", err))
        .then(res => res.text())
        .then(data => console.log(data));
}

function startCommand(direction) {
    sendCommand(direction, "start");
}

function stopCommand(direction) {
    sendCommand(direction, "stop");
}

function attachButton(button, direction) {
    let isPressed = false;

    const start = (e) => {
        e.preventDefault();
        if (isPressed) return;
        isPressed = true;
        startCommand(direction);
    };

    const stop = (e) => {
        e.preventDefault();
        if (!isPressed) return;
        isPressed = false;
        stopCommand(direction);
    };

    button.addEventListener("mousedown", start);
    button.addEventListener("mouseup", stop);
    button.addEventListener("mouseleave", stop);
    button.addEventListener("touchstart", start);
    button.addEventListener("touchend", stop);
    button.addEventListener("touchcancel", stop);
}
