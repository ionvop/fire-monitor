# InfinityFree Internal API Scaffold

A lightweight, dependency-free PHP + SQLite3 backend scaffold designed to run on
[InfinityFree](https://www.infinityfree.com/) shared hosting. This directory is
intended to be uploaded to the `htdocs/api/` folder of your InfinityFree domain.

## Requirements

- PHP with the built-in `sqlite3` extension enabled (default on InfinityFree).
- No Composer dependencies — everything uses PHP's native standard library.
- A MySQL/MariaDB database is **not** required; data is stored in a local
  SQLite file (`database.db`).

## Project structure

```
api/
├── common.php       # Shared code: opens $db (SQLite3) and any functions/variables used across the project
├── index.php        # Simple entry point that returns a JSON "Hello, world!" message
├── tasks/
│   └── index.php    # Full CRUD example (todos) demonstrating the API conventions
├── tools/           # CLI maintenance scripts (run from the command line only)
│   ├── schema.sql   # Generated DB schema (table definitions)
│   ├── init.php     # Recreates database.db from schema.sql
│   └── export.php   # Dumps the current schema out to schema.sql
├── .htaccess        # Denies web access to everything except index.php files
└── .gitignore       # Keeps the local database.db out of version control
```

## Getting started

1. Initialize the database: `php tools/init.php` (destroys and rebuilds the local
   `database.db` from the current schema).
2. Upload the contents of this folder to `htdocs/api/` on your InfinityFree
   account.
3. Verify the API by opening `https://YOUR-DOMAIN.tk/api/` in a browser — you
   should see the JSON hello-world response.

> Because InfinityFree does not send CORS headers, the frontend must be served
> from the **same domain** as this API (same-origin). Don't call this API from
> a different origin.

## Working with the database

The SQLite database file (`database.db`) is stored locally and is the single
source of truth for your data.

- **Modify the schema**: edit `tools/schema.sql`, then run
  `php tools/init.php` to rebuild the database. Use `php tools/export.php` to
  regenerate `tools/schema.sql` from the current database if you've changed the
  schema directly.

## Architecture

- **`common.php`** — the project-wide share point. It opens the `$db`
  SQLite3 connection and is the place to define reusable helpers. In this
  scaffold, `executePreparedQuery()` serves only as an **example** of the kind
  of shared function you'd store here — it prepares a parameterized query,
  binds each `:placeholder` value, and executes it to mitigate SQL injection.
- **`index.php`** — a minimal response that emits JSON, useful as the API
  root or a health check.
- **`tasks/index.php`** — a full CRUD example over the `todos` table,
  showing how to read the JSON request body and dispatch requests.

### InfinityFree constraints & workarounds

InfinityFree's web server imposes two limitations that this project is built
around:

1. **Same-origin only.** No CORS headers are sent, so browsers block
   cross-origin calls. The frontend must be deployed on the same InfinityFree
   domain as the API.
2. **Only `GET` and `POST` are accepted.** `PUT`, `PATCH`, and `DELETE` are
   rejected outright. To still cover the full CRUD surface:
   - `GET` is used for reading (a single task via `?id=`, or a full list).
   - `POST` is used for everything else, with the real verb carried in a form
     field named `_method` (e.g. `_method=PUT`, `_method=DELETE`).

### Example endpoints

| Verb  | URL                | Body / Query                                | Action             |
|-------|--------------------|---------------------------------------------|--------------------|
| GET   | `/api/tasks/`      | —                                           | List all tasks     |
| GET   | `/api/tasks/?id=1` | —                                           | Get one task       |
| POST  | `/api/tasks/`      | JSON `{ "task": "...", "_method": "POST" }` | Create a task      |
| POST  | `/api/tasks/?id=1` | JSON `{ "task": "...", "_method": "PUT" }`  | Update a task      |
| POST  | `/api/tasks/?id=1` | JSON `{ "_method": "DELETE" }`              | Delete a task      |

Responses are JSON, matching the shape `{ "message": "..." }`, and the same
method-tunnelling pattern can be reused for future resource endpoints.

### Security notes

- Queries use prepared statements with parameter binding to guard against SQL
  injection (see the example in `common.php`).
- `.htaccess` denies access to everything except `index.php` files, so
  `database.db` and the helper scripts are not directly reachable via the web.
- `database.db` is kept out of version control via `.gitignore`. Rebuild it on
  deploy with `init.php`.

## Development

These CLI helpers are guarded so they only run from the shell:

```bash
php tools/init.php    # Recreate the database from schema.sql
php tools/export.php  # Regenerate schema.sql from the current database
```