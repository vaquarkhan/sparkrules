# Workbench UI login

The browser Workbench at `/workbench/` can require a **username and password** before API calls are accepted. This is **separate** from `SPARKRULES_API_KEY` (machine-to-machine) and from OIDC/mTLS `SPARKRULES_AUTH_MODE`.

**Shipped UI default:** The static Workbench shell sets **`WORKBENCH_LOGIN_UI_ENABLED = false`**, so the **sign-in form is hidden** and the app loads without a browser login step. The API may still enforce **`SPARKRULES_WORKBENCH_AUTH`** (use **`X-API-Key`** / unset auth for local dev). To show the login overlay again, set **`WORKBENCH_LOGIN_UI_ENABLED = true`** in `src/sparkrules/api/static/workbench/index.html` and redeploy the API assets.

**Workbench shell:** The left nav includes **Overview** (main **dashboard**: stats and charts), authoring, simulation, governance, and more. When login is **off**, you open **Overview** immediately. When login is **on**, you authenticate first, then the app loads and typically shows **Overview** (same dashboard).

---

## Default username and password (read this first)

| What | Value | When it applies |
|------|--------|------------------|
| **Default username** | **`admin`** | Used if `SPARKRULES_WORKBENCH_USER` is unset. |
| **Default password** | **`admin`** | When `SPARKRULES_WORKBENCH_PASSWORD` is **not** set, the expected password is **`admin`** unless you **opt out** with `SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS=0` (then login stays disabled until you set a real password). You do **not** need to set `DEFAULT_CREDENTIALS=1` anymore for that behavior. |

**Sign-in form:** use exactly **`admin`** / **`admin`** in those dev conditions. If you set `SPARKRULES_WORKBENCH_PASSWORD`, that value replaces the default password (username still defaults to `admin` unless you set `SPARKRULES_WORKBENCH_USER`).

---

## How to change to your own username and password

Credentials come from **environment variables** on the API process. There is no in-app “change password” screen—you **set env vars and redeploy** (restart the container/process so the new env is loaded).

1. **Choose** a username and a strong password (use a secret manager in production).
2. **Set** on the server:
   - `SPARKRULES_WORKBENCH_USER=<your-username>`
   - `SPARKRULES_WORKBENCH_PASSWORD=<your-password>` (from secrets, not committed to git)
3. **Turn off** implicit dev password: set `SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS=0` so `admin`/`admin` is not accepted until you set `SPARKRULES_WORKBENCH_PASSWORD`.
4. **Set** `SPARKRULES_WORKBENCH_SECRET` to a long random string (signing key for session tokens).
5. **Keep** `SPARKRULES_WORKBENCH_AUTH=1` if you want login required.
6. **Redeploy or restart** uvicorn/Docker/Kubernetes so all processes pick up the new variables. Existing browser sessions may need **Logout** and login again.

After this, operators sign in with **your** username and password, not `admin`/`admin`.

## Enable

Set on the API process:

| Variable | Purpose |
|----------|---------|
| `SPARKRULES_WORKBENCH_AUTH` | `1` / `true` to require a Workbench session token on API requests (except public routes and `/workbench` static files). |
| `SPARKRULES_WORKBENCH_USER` | Login username; default **`admin`** if unset. |
| `SPARKRULES_WORKBENCH_PASSWORD` | Login password. **Required in production** unless you allow the dev default (below). |
| `SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS` | Optional. Set to **`0`** / **`false`** / **`no`** to **disable** the implicit dev password **`admin`** when `SPARKRULES_WORKBENCH_PASSWORD` is unset (recommended in production until you set a real password). Leaving it unset still allows **`admin`** when no custom password is configured. |
| `SPARKRULES_WORKBENCH_SECRET` | Optional signing secret for session tokens; defaults to `SPARKRULES_API_KEY` or a dev placeholder. Set explicitly in production. |
| `SPARKRULES_DISABLE_WORKBENCH_GATE` | Set to **`1`** / **`true`** / **`yes`** to **turn off the HTTP gate** while leaving `SPARKRULES_WORKBENCH_AUTH` useful for `POST /api/workbench/auth/login`. API calls then work **without** `X-Workbench-Token` or `X-API-Key`. Use for rescue when another layer accidentally forces auth; prefer unsetting `SPARKRULES_WORKBENCH_AUTH` for normal open local dev. |

**UI:** The Workbench header includes **API access help** explaining **token vs X-API-Key** and open-local options.

**Local helper:** `python scripts/dev_server.py` starts uvicorn and **removes `SPARKRULES_WORKBENCH_AUTH` for that process by default** (so the dashboard works if your shell profile set it). Use `python scripts/dev_server.py --with-workbench-auth` to keep the variable from the environment.

## Quick dev setup: `admin` / `admin`

1. Set `SPARKRULES_WORKBENCH_AUTH=1`.
2. Leave `SPARKRULES_WORKBENCH_PASSWORD` unset (otherwise use that password, not `admin`).
3. Open `/workbench/` and sign in with **`admin`** / **`admin`** (only if you did not set `SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS=0`).
4. After login, the shell should show **Overview** (dashboard). If API calls fail with 401, confirm the token header is sent (use the UI’s Logout and sign in again).

### Copy-paste: local server with login enabled

**bash / zsh:**

```bash
export SPARKRULES_WORKBENCH_AUTH=1
python -m uvicorn sparkrules.api.app:create_app --factory --host 127.0.0.1 --port 8042
```

**Windows PowerShell:**

```powershell
$env:SPARKRULES_WORKBENCH_AUTH="1"
python -m uvicorn sparkrules.api.app:create_app --factory --host 127.0.0.1 --port 8042
```

Then open `http://127.0.0.1:8042/workbench/` and use **`admin`** / **`admin`** when no custom `WORKBENCH_PASSWORD` is set. Omit `SPARKRULES_WORKBENCH_AUTH` for a **no-login** local run (fastest smoke test).

## Production checklist (same as “change credentials” above)

1. Set `SPARKRULES_WORKBENCH_USER` and `SPARKRULES_WORKBENCH_PASSWORD` (via secrets manager / Kubernetes Secret).
2. **Unset** `SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS` (or set to `0`) so the dev default password is disabled.
3. Set `SPARKRULES_WORKBENCH_SECRET` to a long random string.
4. **Redeploy** the API so new environment variables take effect.

## Automation bypass

If `SPARKRULES_API_KEY` is configured on the server, clients can send **`X-API-Key`** (or `Authorization: Bearer <key>`) with the same value and **do not** need a Workbench session token. Use this for CI, `curl`, and integrations.

## API

- `GET /api/workbench/auth/config` — returns **`auth_enabled`** (workbench login configured), **`gate_active`** (whether the HTTP middleware requires token or `X-API-Key`; false when `SPARKRULES_DISABLE_WORKBENCH_GATE=1`), the **username hint**, and password flags.
- `POST /api/workbench/auth/login` — JSON `{"username":"...","password":"..."}` → `{"token":"...","principal":"..."}`. The UI stores the token and sends **`X-Workbench-Token`** on subsequent requests.

## Rule snippets (UI)

The **Author / validate** tab includes **draggable chips** that insert common DRL fragments into the Monaco editor; you can also drop `.drl` files on the drop zone. This does not replace full visual rule modeling (see roadmap for a future graph designer).
