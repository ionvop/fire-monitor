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
const badgeManual = document.getElementById("badgeManual");
const badgeFire = document.getElementById("badgeFire");
const connStatus = document.getElementById("connStatus");

initialize();

function initialize() {
    imgStream.src = "/video_feed";
    attachButton(btnUp, "up");
    attachButton(btnDown, "down");
    attachButton(btnLeft, "left");
    attachButton(btnRight, "right");
    attachButton(btnShoot, "shoot");

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
            updateManual(data.manual_mode);
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

function updateManual(manual) {
    badgeManual.classList.toggle("badge-primary", !!manual);
    badgeManual.classList.toggle("badge-outline", !manual);
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
    if (pressed) startCommand(dir);
    else stopCommand(dir);
}

function sendCommand(direction, cmd) {
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
