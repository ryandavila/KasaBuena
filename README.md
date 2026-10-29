# KasaBuena

A modern, containerized web app for controlling TP-Link Kasa smart home devices
on your local network — no cloud account required.

A **FastAPI** backend ([`api/`](api/)) talks to your devices via
[python-kasa](https://github.com/python-kasa/python-kasa) and serves a
**SvelteKit** single-page frontend ([`web/`](web/)) that streams live state.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/devices-dark.png">
    <img src="docs/screenshots/devices-light.png" alt="KasaBuena devices tab, showing a lamp, bulb, power strip, and plugs" width="100%">
  </picture>
</p>
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/energy-dark.png">
    <img src="docs/screenshots/energy-light.png" alt="KasaBuena energy tab, showing whole-home totals, insights, and per-device usage charts" width="100%">
  </picture>
</p>

<sub>Screenshots are generated from seeded fake devices (no real hardware) —
regenerate with <code>just screenshots</code>.</sub>

## Features

- **Local control** — discover and control Kasa devices on your LAN, no cloud
- **Live state** — the UI streams device state over Server-Sent Events, so
  changes made elsewhere (the Kasa app, a physical switch) show up automatically
- **Full device support** — plugs, dimming, bulb color, and individual outlets
  on power strips
- **Rooms & favorites** — group devices into rooms and star the ones you reach
  for most
- **Scenes** — snapshot device states and re-apply them in one tap
- **Schedules** — server-side rules on fixed times, sunrise/sunset, or one-shot
  timers
- **Energy** — live power draw, daily/monthly charts, and server-side history
  retained beyond what each device remembers
- **Alerts** — offline/recovery and power-draw alerts, in-app and via an
  optional webhook
- **Vacation mode** — presence simulation that randomly lights an empty home
- **Persistent discovery** — devices added by IP survive restarts
- **Backup & restore** — all server state as one JSON download, plus the raw
  energy-history database
- **Light/dark theme** with an instant, no-flash toggle
- **Docker-ready** — one multi-stage image, one port

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/ryandavila/KasaBuena.git
cd KasaBuena
docker compose up -d
# open http://localhost:8080
```

> **Newer plugs (including KP125M Matter plugs):** some firmware requires both
> TP-Link account credentials and **Third-Party Compatibility** enabled in the
> Kasa/Tapo app. See [setup and troubleshooting](#newer-plugs-and-third-party-compatibility)
> if power strips work but individual plugs do not.

> **Discovery & networking:** Docker's default bridge network can't carry the
> UDP broadcast discovery uses, so add devices by IP in the **Discovery** tab —
> or, on a Linux host, switch to host networking (see the commented
> `network_mode: host` in [`compose.yml`](compose.yml)). If your devices live on
> a separate subnet or VLAN, set `KASA_SCAN_SUBNET` and the server sweeps it by
> unicast instead.

### Prebuilt container (after the first GHCR release)

Release images are published to `ghcr.io/ryandavila/kasabuena` for Linux amd64
and arm64. Once version `1.0.0` has been published and made public, use the
same checkout and data directories with the image override:

```bash
docker compose -f compose.yml -f compose.ghcr.yml pull
docker compose -f compose.yml -f compose.ghcr.yml up -d --no-build
```

The override defaults to `1.0.0`. Set `KASABUENA_IMAGE_TAG` in `.env` to select
another release or `latest` (the most recently published stable release).
Use the same two `-f` arguments for subsequent Compose commands. The standard
`compose.yml` continues to support local builds. Maintainers can follow the
[publishing instructions](docs/publishing.md).

### Local (without Docker)

```bash
git clone https://github.com/ryandavila/KasaBuena.git
cd KasaBuena
uv sync
just run          # builds the frontend, then serves it from the API at :8080
```

## Upgrading from Kasa-Nice

KasaBuena 1.0.0 renames the installed command to `kasabuena` and the Docker
Compose service to `kasabuena`. Update scripts that use `kasa-nice` or
`docker compose exec kasa-nice`.

1. Download both backups from Settings (configuration JSON and energy history).
2. Before updating the checkout, stop the old deployment with `docker compose down`
   from its existing directory. For a local installation, stop its server process.
3. Update the checkout. Keep your `.env`, `data/`, and `logs/` in that directory;
   if moving to a new checkout, copy them while the old server is stopped.
   Compose mounts these paths relative to the checkout, including the complete
   `data/` directory, so an empty new directory would appear to lose your settings.
4. For Docker, run `docker compose up -d --build`. For a local installation,
   run `uv sync`, `cd web && bun install --frozen-lockfile && cd ..`, then `just run`.
5. Verify your devices, rooms, schedules, and energy history before removing any
   old deployment files.

Existing JSON and energy-history backups remain compatible; only download
filenames change. Environment variables, persisted filenames, and browser
storage keys remain unchanged. Keep the same browser URL (scheme, hostname,
and port) to retain browser preferences. An installed PWA may need to be
reinstalled to display its updated name.

## API

All endpoints live under `/api`; the full interactive reference (every route,
schema, and example) is served at `http://localhost:8080/docs`. In brief:

| Area | Endpoints |
| --- | --- |
| Devices | list, live state, discover, power/brightness/color, per-outlet control, rename |
| Energy | per-device usage & recorded history, whole-home summary, derived insights |
| Live updates | `GET /api/events` (Server-Sent Events) |
| Rooms & favorites | room CRUD, per-room power, starred devices |
| Schedules & scenes | rule and scene CRUD, scene apply |
| Alerts | recent alerts, per-device power thresholds |
| Backup | full JSON backup/restore, energy-database snapshot |
| Vacation | presence-simulation config and live status |

## Configuration

The KasaBuena rebrand preserves all `KASA_*` environment variables, browser
localStorage keys (such as `kasa-grouping` and `kasa-theme`), and persisted
`data/` filenames. Existing configuration, preferences, and backups remain
compatible. The log path stays `logs/kasa_nice.log` as well.

| Variable | Default | Purpose |
| --- | --- | --- |
| `KASA_HOST` / `KASA_PORT` | `127.0.0.1` (`0.0.0.0` in Docker) / `8080` | Bind address and port |
| `KASA_*_FILE` | `data/…` | Per-store persistence paths: known devices, rooms, schedules, scenes, alert thresholds, vacation config, and the energy-history SQLite database |
| `TPLINK_USERNAME` / `TPLINK_PASSWORD` | _(unset)_ | TP-Link cloud credentials, required for newer SMART-protocol devices (e.g. KP125M) |
| `KASA_SCAN_SUBNET` | _(unset)_ | CIDR subnet swept by unicast on startup and from the Discovery tab |
| `KASA_CLOUD_FALLBACK` / `KASA_CLOUD_MODELS` / `KASA_CLOUD_POLL_INTERVAL` | `0` / `HS300` / `30` | Cloud control for devices that dropped local auth — see below |
| `KASA_ENERGY_RATE` / `KASA_ENERGY_CURRENCY` | _(unset)_ / `$` | Flat price per kWh (and symbol) for cost estimates — see below |
| `KASA_ENERGY_SAMPLE_INTERVAL` | `300` | Seconds between energy-history samples (min `10`) |
| `KASA_ALERT_INTERVAL` / `KASA_ALERT_WEBHOOK_URL` | `60` / _(unset)_ | Alert evaluation cadence and optional [ntfy](https://ntfy.sh)-compatible webhook |
| `KASA_LATITUDE` / `KASA_LONGITUDE` | _(unset)_ | Location (decimal degrees) for sunrise/sunset schedules |

Put credentials in a `.env` at the repo root (copy `.env.example`); the server
loads it on every start, with real environment variables taking precedence.
Without credentials, only legacy plugs are reachable. `.env` is gitignored.

### Newer plugs and Third-Party Compatibility

**For KP125M Matter plugs on affected firmware, configure both the app setting
and your TP-Link account credentials.** A working HS300 power strip does not
prove the individual plugs are configured correctly; firmware and authentication
requirements can differ. KasaBuena uses python-kasa's local protocol, not Matter
pairing, even when the plug also supports Matter.

1. Enable **Third-Party Compatibility** in the phone app:
   - **Kasa:** Me → Settings → Third-Party Compatibility.
   - **Tapo:** Me → Third-Party Services → Third-Party Compatibility.
   This permits third-party local access. Availability depends on the device and
   firmware; see [TP-Link's explanation](https://www.tapo.com/uk/faq/714/?app=iframe).
2. Create `.env` in the repository root **if it does not already exist**, using
   `.env.example` as the template. Set `TPLINK_USERNAME` to your TP-Link account
   email and `TPLINK_PASSWORD` to its password. Keep existing values when editing
   an existing file. `.env` is Git-ignored and is not included when cloning the
   repository. Docker Compose treats it as optional, so the app can start without
   credentials if the file is missing.
3. After saving `.env`, recreate the Docker container to load the new environment:
   `docker compose up -d --force-recreate kasabuena`. A plain `docker compose restart`
   does not reload environment variables. For a local run, restart the API process.
4. Refresh the browser and rescan your subnet in **Discovery**.

The scan result distinguishes the two blockers:

| Result | What to check |
| --- | --- |
| `unsupported` with `TPAP` | The device advertises an encryption protocol this python-kasa version cannot use. Check the app's Third-Party Compatibility setting, then rescan. Credentials alone do not add TPAP support. |
| `auth_failed` | Check that both TP-Link credentials are set and loaded by the running server. This can also indicate rejected credentials or a device's local-auth restriction. |
| No responses | Check the subnet, device power, and network reachability from the server. |

In a verified KP125M setup, enabling compatibility changed the plugs from
`unsupported` to `auth_failed`; loading the missing `.env` credentials then
restored control. Both steps were needed. Firmware updates can change local
access requirements, so revisit the setting if previously working plugs stop
connecting. This local setup does not require enabling `KASA_CLOUD_FALLBACK`.

### Cloud fallback

Some devices (notably the **HS300** strip) shipped firmware that
[removed the local auth python-kasa can speak](https://github.com/python-kasa/python-kasa/issues/1604).
Set `KASA_CLOUD_FALLBACK=1` and the server attaches them through TP-Link's cloud
after local discovery — they appear, toggle, and report energy like local
devices, just a little slower and refreshed every `KASA_CLOUD_POLL_INTERVAL`
seconds rather than every poll.

### Energy cost

Set `KASA_ENERGY_RATE` to show an estimated cost next to energy usage. It's a
**flat-rate approximation** — no tiered or time-of-use pricing, fees, or taxes —
so treat the figures as an estimate, not a bill. Unset, the UI shows kWh only.

### Idle draw & the "Vampire" tag

The Energy tab lists each device's **overnight idle draw** — the median power
between 1–5am over the last 14 days. A median above **15W** earns a red
**Vampire** tag: roughly 11 kWh a month burned while idle, enough to cost real
money, and above typical always-on gear like routers and aquarium pumps. The tag
can't tell intentional heavy loads from wasteful ones — treat it as a prompt to
check, not a verdict.

### Schedules

Rules fire at a **fixed time**, at **sunrise/sunset** with an offset (requires
`KASA_LATITUDE`/`KASA_LONGITUDE`), or **once** at a date & time; each switches a
device or room on/off or applies a scene. Rules run server-side once a minute
against the server's local time, so they fire with no browser open and tolerate
unreachable devices when fanning out across a room. Device cards also carry a
**"turn off in N minutes"** sleep timer, which posts a one-shot rule.

### Scenes

Save the current state of any set of devices — power, plus brightness and color
where supported — and re-apply it in one tap. Applying fans out concurrently and
tolerates per-device failure, reporting `{succeeded, failed}`.

### Alerts

A background task (every `KASA_ALERT_INTERVAL` seconds) watches for devices
dropping offline or recovering, and for power draw crossing a per-device
threshold set from the header **bell** dropdown. Alerts are debounced — one
incident, one alert. They appear in the bell (an in-memory buffer, not persisted
across restarts) and optionally POST to `KASA_ALERT_WEBHOOK_URL` in an
[ntfy](https://ntfy.sh)-compatible shape.

### Backup & restore

The **Settings** panel downloads everything the server persists as one versioned
JSON document, and restores it in two steps: a client-side summary of the file's
contents, then a confirmed upload the server re-validates whole — invalid
documents are rejected with no partial writes. The energy-history database is
separate (`GET /api/backup/energy.db`): a consistent SQLite snapshot for your
own archival, with no restore path.

### Vacation mode

Presence simulation: within a nightly window (fixed start time or sunset, until
a fixed end), the server randomly toggles a configured set of lights and rooms
with per-device jitter so an empty home looks lived-in, then turns everything
off when the window closes. If a light is changed from elsewhere — a schedule,
the Kasa app, a wall switch — the simulation adopts that state and backs off for
a cooldown rather than fighting it.

## Project Structure

```
├── api/                  # FastAPI backend
│   ├── main.py           # App factory, lifespan discovery, SPA serving
│   ├── routers/          # REST endpoints under /api, one module per domain
│   ├── kasa_service.py   # Device discovery & control
│   └── …                 # stores, scheduler, alerts, energy history, schemas
├── web/                  # SvelteKit frontend (Svelte 5, Tailwind v4, bun)
├── tests/                # pytest suite (python-kasa is faked; no devices needed)
├── Dockerfile            # Multi-stage: bun builds web/, Python serves it
└── compose.yml           # Docker Compose
```

## Development

Prerequisites: Python 3.14+, [uv](https://docs.astral.sh/uv/),
[bun](https://bun.sh/), [just](https://just.systems) (run `just` to list all
recipes), and optionally Docker.

```bash
just setup     # one-time: install Python + frontend deps
just dev       # API autoreload + frontend HMR in one terminal (http://localhost:5173)
just fix       # apply lint fixes, format, then run all checks
just check     # verify formatting, lint, types, and unit tests (also: just ci)
```

Unprefixed quality commands cover both apps: `format`, `format-check`, `lint`,
`lint-fix`, and `test`. Formatting and lint fixes are explicit; `lint` and
`check` do not modify source files. Use `api-*` or `web-*` for one app, such as
`just api-test -k discovery`, `just web-test`, or `just web-test-watch`.
Type checking currently covers only the frontend.

`just dev 8090` chooses a different API port; `api-dev` and `web-dev` accept
the same port when run separately. `just run` builds and serves the frontend,
while `just api-run` reuses the existing build. Browser workflows stay separate:
`just e2e` runs integration tests and `just screenshots` regenerates README
images, each using temporary state and fake devices. Both accept an optional port.

Docker tasks use the `docker-` prefix (`docker-up`, `docker-down`,
`docker-rebuild`, `docker-logs`, `docker-shell`). The original short names still
work, as do `install`, `dev-install`, and `ci`. Use `api-install-prod` when you
only need Python runtime dependencies; `setup` installs development dependencies
for both apps. `clean` removes project caches and builds without traversing
installed dependencies.

The backend tests fake `python-kasa`, so they run with no devices or network.
To contribute: fork, branch, add tests where applicable, run `just ci`, and
open a pull request.

## Supported Devices

All devices supported by python-kasa, including:

- **Plugs:** HS100/103/105/107/110, KP105/115/125/401, EP10
- **Power strips:** EP40, HS300, KP303, KP200, KP400, KP405
- **Wall switches:** ES20M, HS200/210/220, KS200M/220M/230
- **Bulbs:** LB100/110/120/130/230, KL50/60/110/120/125/130/135
- **Light strips:** KL400/420/430

## Troubleshooting

**No devices found**
- Confirm devices are powered on and on the same network segment as the host.
- In Docker (bridge mode), broadcast discovery won't work — add devices by IP in
  the Discovery tab, or use host networking on Linux.
- Verify with python-kasa directly: `docker compose exec kasabuena uv run kasa discover`.

**Permission issues**
- Ensure `./logs` and `./data` are writable by the container/user (both are
  mounted as volumes in Docker).

Logs go to the console and `./logs/kasa_nice.log` (rotated, 10 MB × 5).

## License

This project remains licensed under GPL-3.0; see [LICENSE](LICENSE).

## Credits

Originally forked from
[uni-byte/Kasa-Nice](https://github.com/uni-byte/Kasa-Nice) by
[uni-byte](https://github.com/uni-byte), since rebuilt as a FastAPI + SvelteKit
application. Built on
[python-kasa](https://github.com/python-kasa/python-kasa),
[FastAPI](https://fastapi.tiangolo.com/),
[SvelteKit](https://svelte.dev/), and [Tailwind CSS](https://tailwindcss.com/).

### Discovery reports

`POST /api/discover` (broadcast or a `target`) and `POST /api/discover/subnet`
return `{ devices, skipped, stats }`. Other device-list endpoints retain their
array responses. Skipped entries contain `host`, `reason`, `detail`, and optional
`model`, `device_type`, and `encrypt_type`. Reasons are `unsupported`,
`auth_failed`, `unreadable` (discovered but state could not be read), or `error`.
Successful probes populate `devices`; ordinary discovery timeouts are omitted.

Stats include `hosts_probed` (null for broadcast), `responded` (unique hosts with
confirmed discovery/read responses, excluding unexpected probe errors), and
`duration_seconds`. Broadcast responses continue to include cached cloud devices;
scan stats describe local discovery only. The latest scan report is held in
server and browser memory, replaced by the next scan, and is not persisted or
added to `/api/status`. The Scan tab retains its report when switching tabs.
TPAP entries link to the bundled [protocol note](web/static/discovery-help.html).
Log naming, diagnostics, metrics, tracing, and cloud controls are unchanged.

### Logs and request correlation

Set `KASA_LOG_FORMAT=text|json` and `KASA_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL`.
Local runs default to text/INFO; the Docker image defaults to JSON/INFO. Console,
rotating file, and uvicorn access/error logs use the same format. Logs now go to
`logs/kasabuena.log` (10 MiB, five backups); existing `kasa_nice.log` files are
left intact. Update any log collectors that watch the old filename.

Every HTTP response includes `X-Request-ID`. Clients may supply an ID containing
1–128 ASCII letters, digits, `.`, `_`, `:`, or `-`; missing or invalid IDs are
replaced. API error JSON includes `request_id` alongside `detail`. Logs carry the
request ID and, during device operations, `device_id`, `host`, and `operation`.
Background work has no request ID. Correlation stays local to each async task.

Log levels: INFO for completed state changes and scan summaries; WARNING for
handled degradation; ERROR for failed operations; DEBUG for read/probe details
and tolerated exceptions. Ordinary discovery timeouts remain silent.

### Readiness and diagnostics

`GET /api/health` is process liveness. `GET /api/ready` returns 503 until startup
initialization and discovery complete successfully, then 200. An initialization
failure remains not-ready until restart. Docker Compose checks readiness with a
60-second start period; large subnet sweeps may need a longer period.

Open **Settings → Diagnostics** for app/library versions, the latest scan,
per-device last-seen/error timestamps and consecutive failures, cloud fallback
state, background-task state, and recent job results. **Copy report** copies the
same JSON served by `GET /api/diagnostics`. It contains local host addresses and
device IDs, but no credentials or webhook URLs. Unreachable cards show a reason
on hover. Successful device reads reset the failure streak; the previous error
and its timestamp remain available as history.

The latest 200 completed job/delivery records are kept in memory, newest first:
schedule runs (including missed one-shots), scene applications, vacation switches,
and alert webhook deliveries with HTTP status, duration, and outcome. Failed
background cycles also appear. Diagnostics highlights failed/missed schedules and
sunrise/sunset schedules that lack a location. This history and device health
reset on restart; existing saved schedules still retain their `last_fired` entry.

API error toasts show the server detail and request ID. Set `KASA_CLIENT_ERRORS=1`
to additionally log uncaught browser errors and failed requests through
`POST /api/client-errors`; it returns 404 when disabled (the default). Reports
include a bounded message and kind, not stacks, URLs, or request bodies. The
browser caps reporting at 20 events per minute and silently drops delivery
failures. Uncaught error messages may contain application-specific text.

The observability rollout implements plan phases 0, 1, 2, 4 and 5. Prometheus
metrics (phase 3) and OpenTelemetry tracing (phase 6) remain deferred: ordinary
operation and diagnostics require no external monitoring services.
