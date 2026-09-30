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
const badgeThermal = document.getElementById("badgeThermal");
const badgeHotPixel = document.getElementById("badgeHotPixel");
const connStatus = document.getElementById("connStatus");

// Thermal minimap (blank 8x8 grid; hottest pixel highlighted above threshold)
const thermalMinimap = document.getElementById("thermalMinimap");
const thermalMapCaption = document.getElementById("thermalMapCaption");
const THERMAL_GRID_SIZE = 8;
const thermalCells = [];

// Mode toggle element (ON = auto, OFF = manual)
const modeToggle = document.getElementById("modeToggle");
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

// Detection sensitivity (fire confidence threshold)
// Slider snaps across three presets, indexed 0..2 (High, Medium, Low).
const THRESHOLD_PRESETS = [0.85, 0.7, 0.6];
const THRESHOLD_LABELS = ["High", "Medium", "Low"];
const thresholdSlider = document.getElementById("thresholdSlider");
const thresholdValue = document.getElementById("thresholdValue");

// Client-side mirror of the turret mode, used to guard manual commands.
let isAutoMode = true;

initialize();

function initialize() {
    imgStream.src = "/video_feed";
    buildThermalMinimap();
    attachButton(btnUp, "up");
    attachButton(btnDown, "down");
    attachButton(btnLeft, "left");
    attachButton(btnRight, "right");
    attachButton(btnShoot, "shoot");

    // Mode toggle
    modeToggle.addEventListener("change", () => setMode(modeToggle.checked ? "auto" : "manual"));
    autoFireToggle.addEventListener("change", () => setAutoFire(autoFireToggle.checked));

    // Auto-capture toggle + gallery
    captureToggle.addEventListener("change", () => setCapture(captureToggle.checked));
    btnClearCaptures.addEventListener("click", clearCaptures);

    // Crosshair toggle (disabled by default)
    crosshairToggle.addEventListener("change", () => setCrosshair(crosshairToggle.checked));

    // Detection sensitivity — applied on release ("change", not "input").
    thresholdSlider.addEventListener("change", () => {
        const idx = Number(thresholdSlider.value);
        setThreshold(THRESHOLD_PRESETS[idx]);
    });

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
            updateThreshold(data.fire_conf_threshold);
            updateScanDirection(data.scan_direction, data.auto_mode, data.fire_active);
            updateThermal(data.max_temp_c, data.thermal_ok, data.thermal_enabled);
            updateHotPixel(data.thermal_row, data.thermal_col, data.thermal_enabled);
            updateMinimap(
                data.thermal_row,
                data.thermal_col,
                data.max_temp_c,
                data.thermal_threshold_c,
                data.thermal_enabled,
                data.thermal_ok
            );
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

function updateThermal(maxTempC, thermalOk, enabled) {
    // When the thermal layer is disabled, show it as inactive rather than
    // implying a reading is available.
    if (enabled === false) {
        badgeThermal.textContent = "Thermal: off";
        badgeThermal.classList.remove("badge-success", "badge-error");
        badgeThermal.classList.add("badge-outline");
        return;
    }

    const temp = Number.isFinite(maxTempC) ? `${maxTempC.toFixed(1)}°C` : "—";
    const ok = thermalOk === true;
    badgeThermal.textContent = `Thermal: ${temp} ${ok ? "OK" : "LOW"}`;
    badgeThermal.classList.toggle("badge-success", ok);
    badgeThermal.classList.toggle("badge-error", !ok);
    badgeThermal.classList.toggle("badge-outline", false);
}

function updateHotPixel(row, col, enabled) {
    // Show the AMG8833 hottest pixel's grid position, which drives aiming.
    if (enabled === false) {
        badgeHotPixel.textContent = "Hot pixel: off";
        badgeHotPixel.classList.remove("badge-success", "badge-error");
        badgeHotPixel.classList.add("badge-outline");
        return;
    }

    const hasPixel = Number.isFinite(row) && Number.isFinite(col);
    badgeHotPixel.textContent = hasPixel
        ? `Hot pixel: r${row} c${col}`
        : "Hot pixel: —";
    badgeHotPixel.classList.toggle("badge-success", hasPixel);
    badgeHotPixel.classList.toggle("badge-outline", !hasPixel);
}

function buildThermalMinimap() {
    // Build the blank 8x8 grid once; cells are updated in place afterwards.
    thermalMinimap.replaceChildren();
    thermalCells.length = 0;
    for (let i = 0; i < THERMAL_GRID_SIZE * THERMAL_GRID_SIZE; i++) {
        const cell = document.createElement("div");
        cell.className = "thermal-cell";
        thermalMinimap.appendChild(cell);
        thermalCells.push(cell);
    }
}

function updateMinimap(row, col, maxTempC, thresholdC, enabled, thermalOk) {
    // Clear any previous highlight.
    for (const cell of thermalCells) {
        cell.classList.remove("thermal-cell-hot");
    }

    if (enabled === false) {
        thermalMapCaption.textContent = "off";
        return;
    }

    const temp = Number.isFinite(maxTempC) ? maxTempC : null;
    const threshold = Number.isFinite(thresholdC) ? thresholdC : null;
    const hasPixel = Number.isFinite(row) && Number.isFinite(col);

    // Highlight only when the hottest pixel is at/above the threshold.
    // Fall back to the server's thermal_ok flag if no threshold is provided.
    const aboveThreshold = threshold !== null
        ? temp !== null && temp >= threshold
        : thermalOk === true;

    if (hasPixel && aboveThreshold) {
        const index = row * THERMAL_GRID_SIZE + col;
        if (thermalCells[index]) {
            thermalCells[index].classList.add("thermal-cell-hot");
        }
    }

    const tempText = temp !== null ? `${temp.toFixed(1)}°C` : "—";
    const thresholdText = threshold !== null ? `${threshold.toFixed(1)}°C` : "—";
    thermalMapCaption.textContent = `${tempText} / ${thresholdText}`;
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

    // Mode toggle + badge.
    modeToggle.checked = isAuto;
    badgeMode.textContent = isAuto ? "Auto mode" : "Manual mode";
    badgeMode.classList.toggle("badge-primary", !isAuto);
    badgeMode.classList.toggle("badge-outline", isAuto);

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

function updateThreshold(value) {
    // Match the current threshold to the closest preset and move the slider.
    const target = Number(value);
    let bestIdx = 0;
    let bestDiff = Infinity;
    for (let i = 0; i < THRESHOLD_PRESETS.length; i++) {
        const diff = Math.abs(THRESHOLD_PRESETS[i] - target);
        if (diff < bestDiff) {
            bestDiff = diff;
            bestIdx = i;
        }
    }
    if (Number(thresholdSlider.value) !== bestIdx) {
        thresholdSlider.value = String(bestIdx);
    }
    const label = THRESHOLD_LABELS[bestIdx];
    if (thresholdValue.textContent !== label) {
        thresholdValue.textContent = label;
    }
}

function setThreshold(value) {
    fetch("/api/threshold", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threshold: value }),
    })
        .then((res) => res.json())
        .then((data) => {
            updateThreshold(data.threshold);
            console.log("Detection threshold set to", data.threshold);
        })
        .catch((err) => console.error("Failed to set detection threshold:", err));
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
