import { io } from "socket.io-client";
import "./style.css";

const imgStream = document.getElementById("imgStream");
const btnUp = document.getElementById("btnUp");
const btnLeft = document.getElementById("btnLeft");
const btnShoot = document.getElementById("btnShoot");
const btnRight = document.getElementById("btnRight");
const btnDown = document.getElementById("btnDown");

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
    socket.on("connect", () => console.log("Connected to controller"));
    socket.on("disconnect", () => console.log("Disconnected from controller"));
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

function attachButton(button, direction) {
    let isPressed = false;

    const start = (e) => {
        e.preventDefault();
        if (isPressed) return;
        isPressed = true;
        sendCommand(direction, "start");
    };

    const stop = (e) => {
        e.preventDefault();
        if (!isPressed) return;
        isPressed = false;
        sendCommand(direction, "stop");
    };

    button.addEventListener("mousedown", start);
    button.addEventListener("mouseup", stop);
    button.addEventListener("mouseleave", stop);
    button.addEventListener("touchstart", start);
    button.addEventListener("touchend", stop);
    button.addEventListener("touchcancel", stop);
}
