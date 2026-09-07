# Fire Monitor — PWA Frontend (`app/`)

The installable web app for the **Fire Monitor** turret system. It renders the
live fire-detection history, shows connection status, and lets a user subscribe
to Web Push notifications. It is the **Phase 2** component of the project (see
[`docs/proposal.md`](docs/proposal.md)).

Built with **React 19 + Vite 6 + TypeScript + Tailwind CSS v4 + DaisyUI 5**.

> **For agents working in `../controller/`:** the API contract you need to POST
> fire detections to is documented in the
> [API Reference for the Controller](#api-reference-for-the-controller) section
> below. The controller currently does **not** call this API yet — wiring it up
> is the integration point.

---

## What this app does

- Polls `GET /api/fire_history/` every **5 seconds** (`POLL_INTERVAL_MS`) and
  renders the newest alerts (capped at `MAX_ALERTS = 50`).
- Shows a **live / offline** badge based on whether the last poll succeeded.
- Lets the user **subscribe to Web Push** notifications. The browser subscribes
  using the embedded VAPID public key, then persists the subscription to the
  backend via `POST /api/subscriptions/`.
- Runs as a PWA: `public/manifest.json` + `public/sw.js` (service worker) +
  generated icons.

---

## Project structure

```
app/
├── index.html                 # Vite entry point
├── package.json
├── vite.config.ts
├── tsconfig.json / tsconfig.node.json
├── docs/
│   └── proposal.md            # Phase 1–3 plan
├── public/                    # Copied verbatim into dist/ (incl. PHP backend)
│   ├── manifest.json          # PWA manifest
│   ├── sw.js                  # Service worker (handles push events)
│   ├── icons/                 # Generated app icons
│   └── api/                   # PHP + SQLite3 backend (see below)
├── scripts/
│   └── generate-icons.mjs     # Pure-Node icon generator
└── src/
    ├── main.tsx               # Entry
    ├── App.tsx                # Polls history, renders list + status
    ├── config.ts              # VAPID_PUBLIC_KEY, POLL_INTERVAL_MS, MAX_ALERTS
    ├── types.ts               # FireAlert, PushSubscriptionPayload, ...
    ├── styles.css             # Tailwind + DaisyUI entry
    ├── api/client.ts          # fetchFireHistory(), saveSubscription()
    ├── services/push.ts       # SW registration, permission, subscribe
    └── components/            # AlertCard, ConnectionStatus, EmptyView,
                               # ErrorView, SubscribeButton
```

---

## Getting started

```bash
npm install
npm run dev        # Vite dev server
npm run build      # tsc && vite build  -> dist/
npm run preview    # Preview the built app
```

### Serving the PHP backend locally

The `public/api/` folder is copied verbatim into `dist/`, so the PHP backend
ships alongside the built frontend. Serve the whole `dist/` folder with PHP's
built-in server:

```bash
npm run build
php -S 127.0.0.1:8080 -t dist
```

Then open `http://127.0.0.1:8080/`.

### Initialize the database

```bash
cd public/api
php tools/init.php     # Recreates database.db from tools/schema.sql
```

---

## Configuration (`src/config.ts`)

| Key                 | Purpose                                                                  |
| ------------------- | ------------------------------------------------------------------------ |
| `VAPID_PUBLIC_KEY`  | Public half of the Web Push VAPID key pair, embedded so the browser can subscribe. The **private** key must stay server-side (Phase 3 push sender) — never ship it in this bundle. |
| `POLL_INTERVAL_MS`  | How often (ms) the fire-history list polls the API. Default `5000`.      |
| `MAX_ALERTS`        | Max alerts kept in the on-screen list. Default `50`.                     |

Generate a VAPID key pair with:

```bash
npx web-push generate-vapid-keys --json
```

---

## Backend overview (`public/api/`)

A dependency-free **PHP + SQLite3** backend designed for
[InfinityFree](https://www.infinityfree.com/) shared hosting. It stores data in
a local SQLite file (`database.db`) and exposes JSON endpoints. See
[`public/api/README.md`](public/api/README.md) for the full scaffold docs.

### Hosting constraints (important)

1. **Same-origin only.** InfinityFree sends no CORS headers, so the frontend
   must be served from the **same domain** as the API. All requests use
   relative `/api/...` paths — no CORS needed.
2. **Only `GET` and `POST` are accepted.** `PUT`/`PATCH`/`DELETE` are rejected
   outright. Full CRUD is achieved via **method tunneling**: the real verb is
   carried in a JSON body field named `_method` (e.g. `_method=DELETE`).

### Database schema (`public/api/tools/schema.sql`)

```sql
CREATE TABLE `fire_history` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `timestamp` TEXT NOT NULL DEFAULT (datetime('now')),  -- UTC
    `confidence_score` REAL,
    `status` TEXT NOT NULL DEFAULT 'detected',            -- 'detected' | 'retracted'
    `x` REAL,                                             -- servo pan angle
    `y` REAL,                                             -- servo tilt angle
    `capture_image_url` TEXT
);

CREATE TABLE `subscriptions` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `endpoint` TEXT NOT NULL UNIQUE,
    `p256dh` TEXT NOT NULL,
    `auth` TEXT NOT NULL,
    `created_at` TEXT DEFAULT (datetime('now'))
);

CREATE TABLE `todos` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `task` TEXT NOT NULL,
    `is_completed` INTEGER DEFAULT 0,
    `created_at` INTEGER DEFAULT (unixepoch())
);
```

### Maintenance tools (`public/api/tools/`)

```bash
php tools/init.php     # Recreate database.db from schema.sql (destroys data)
php tools/export.php   # Regenerate schema.sql from the current database
```

---

## API Reference

All endpoints return JSON. Errors use the shape `{ "message": "..." }` with an
appropriate HTTP status code. Because of the hosting constraints above, **only
`GET` and `POST` are real HTTP verbs**; `_method` in the JSON body tunnels
`PUT`/`DELETE`.

### `GET /api/`

Health check. Returns `{ "message": "Hello, world!" }`.

### `GET /api/fire_history/`

List fire-detection history, **newest first** (ordered by `id DESC`).

**Response:** `200` — JSON array of `fire_history` rows:

```json
[
  {
    "id": 1,
    "timestamp": "2026-09-07 12:34:56",
    "confidence_score": 0.87,
    "status": "detected",
    "x": 90.0,
    "y": 80.0,
    "capture_image_url": null
  }
]
```

### `GET /api/fire_history/?id=1`

Get a single record. **`200`** with the row, or **`404`** `{ "message": "Record not found." }`.

### `POST /api/fire_history/`

Insert a fire-detection record. **This is the endpoint the controller posts to.**

**Request body (all fields optional; defaults applied):**

```json
{
  "timestamp": "2026-09-07 12:34:56",
  "confidence_score": 0.87,
  "status": "detected",
  "x": 90.0,
  "y": 80.0,
  "capture_image_url": "https://example.com/captures/1.jpg"
}
```

- `timestamp` — ISO-8601 UTC string; defaults to server time (`datetime('now')`).
- `status` — `"detected"` or `"retracted"`; defaults to `"detected"`.
- `x` / `y` — servo pan/tilt angles at detection (optional).
- `capture_image_url` — URL of the annotated capture image (optional).

**Response:** `200` — `{ "message": "Record created." }`.

### `POST /api/fire_history/?id=1`

Delete a record via method tunneling. Body: `{ "_method": "DELETE" }`.
**`400`** if `id` is missing, otherwise **`200`** `{ "message": "Record deleted." }`.

### `GET /api/subscriptions/`

List all push subscriptions (newest first). Optional `?id=1` returns one row
(**`404`** if not found).

### `POST /api/subscriptions/`

Save (upsert) a Web Push subscription, keyed on the unique `endpoint`. Used by
the PWA's `SubscribeButton`.

**Request body:**

```json
{
  "endpoint": "https://fcm.googleapis.com/...",
  "p256dh": "<base64url>",
  "auth": "<base64url>"
}
```

**`400`** if `endpoint`, `p256dh`, or `auth` is missing. Otherwise **`200`**
`{ "message": "Subscription saved." }`. Re-subscribing with the same endpoint
updates the existing row (no UNIQUE-constraint error).

### `POST /api/subscriptions/?id=1`

Delete a subscription via method tunneling. Body: `{ "_method": "DELETE" }`.

### `GET/POST /api/tasks/`

A full CRUD example over the `todos` table demonstrating the API conventions
(`_method=PUT` / `_method=DELETE` tunneling). See
[`public/api/README.md`](public/api/README.md) for the endpoint table.

---

## API Reference for the Controller

This is the contract for agents working in **`../controller/`** (the Python
YOLOv8 detection loop). The controller currently does **not** call this API —
it should POST a record to `fire_history` on each detection/retraction so the
PWA can render it.

### Reporting a fire detection

`POST /api/fire_history/` with a JSON body:

```python
import requests

API_BASE = "https://YOUR-DOMAIN.tk/api"  # same-origin as the PWA

def report_fire(status: str, confidence: float, x: float, y: float,
                capture_url: str | None = None) -> None:
    """status: 'detected' or 'retracted'."""
    requests.post(
        f"{API_BASE}/fire_history/",
        json={
            "status": status,
            "confidence_score": confidence,
            "x": x,
            "y": y,
            "capture_image_url": capture_url,
            # "timestamp" is optional; the server defaults to UTC now.
        },
        timeout=5,
    )
```

### Contract notes

- **Base URL:** the same InfinityFree domain as the PWA (same-origin). Use the
  relative path `/api/fire_history/` when the controller is served from the same
  host, or the absolute `https://<domain>/api/fire_history/` otherwise.
- **Method:** `POST` only. No `_method` field is needed for inserts.
- **`status`:** send `"detected"` when a fire is first confirmed, and
  `"retracted"` when it is no longer detected. The PWA treats `"detected"` as
  an active alert and `"retracted"` as resolved.
- **`confidence_score`:** the YOLO confidence (0.0–1.0) at detection.
- **`x` / `y`:** the servo pan/tilt angles at detection, if available.
- **`capture_image_url`:** optional URL of the annotated capture image. The
  controller already saves screenshots to `controller/captures/` — if those are
  served over HTTP(S), pass their URL here.
- **Idempotency / cooldown:** the controller's `config.py` already has a
  `FIRE_ALERT_COOLDOWN_SECONDS` concept for Firestore alerts. Apply the same
  idea here: send `"detected"` at most once per cooldown window, and always
  send the matching `"retracted"` so the app can resolve the active alert.
- **Errors:** a non-`2xx` response returns `{ "message": "..." }`. Treat
  network failures as non-fatal — the detection loop should keep running.

---

## Commands

| Command                          | Purpose                                  |
| -------------------------------- | ---------------------------------------- |
| `npm run dev`                    | Start the Vite dev server                |
| `npm run build`                  | Type-check (`tsc`) and build to `dist/`  |
| `npm run preview`                | Preview the built app                    |
| `node scripts/generate-icons.mjs`| Regenerate `public/icons/`               |
| `npx web-push generate-vapid-keys --json` | Generate a VAPID key pair      |
| `php tools/init.php`             | Recreate the SQLite database             |
| `php tools/export.php`           | Export the current schema to `schema.sql`|