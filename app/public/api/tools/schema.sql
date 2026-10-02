CREATE TABLE `todos` (`id` INTEGER PRIMARY KEY AUTOINCREMENT, `task` TEXT NOT NULL, `is_completed` INTEGER DEFAULT 0, `created_at` INTEGER DEFAULT (unixepoch()));

CREATE TABLE `subscriptions` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `endpoint` TEXT NOT NULL UNIQUE,
    `p256dh` TEXT NOT NULL,
    `auth` TEXT NOT NULL,
    `created_at` TEXT DEFAULT (datetime('now'))
);

CREATE TABLE `fire_history` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `timestamp` TEXT NOT NULL DEFAULT (datetime('now')),
    `temperature_c` REAL,
    `status` TEXT NOT NULL DEFAULT 'detected'
);
