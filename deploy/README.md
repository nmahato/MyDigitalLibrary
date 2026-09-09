# Deploying to local IIS

The backend is an ASGI app (FastAPI), so IIS runs it through
**HttpPlatformHandler**: IIS starts one `uvicorn` process, injects a private port,
and reverse-proxies every request to it. FastAPI serves both `/api/*` and the
built React frontend, so there is a single IIS site.

```
browser ──▶ IIS  (site "PhotoLibrary", port 8090)
              └─ HttpPlatformHandler ──▶ python run.py ──▶ uvicorn ──▶ app.main:app
                                                                         ├─ /api/*        FastAPI
                                                                         └─ / , /assets/* frontend/dist
```

## Prerequisites (one time)

| Component | Notes |
|-----------|-------|
| IIS | "World Wide Web Services". `OptionalFeatures.exe` or `Enable-WindowsOptionalFeature`. |
| **HttpPlatformHandler** | <https://www.iis.net/downloads/microsoft/httpplatformhandler> — install the x64 MSI. This is the piece that runs Python. |
| Python 3.11+ | On PATH, to build the backend venv. |
| Node.js 18+ | On PATH, to build the frontend. |
| ffmpeg + ffprobe | On PATH when you deploy. The script bakes the resolved absolute paths into `web.config`. |

### Per-user Python / ffmpeg

If Python or ffmpeg are installed **for your user only** (under
`C:\Users\<you>\AppData\...` — the Python install-manager and `winget` both do
this), the default IIS `ApplicationPoolIdentity` cannot read them ("Access is
denied" in `logs\stdout*.log`). Two ways through, both handled by the script:

* **Recommended — run the pool as your account:**
  `.\Deploy-ToIIS.ps1 -Port 9090 -PoolUser "$env:COMPUTERNAME\$env:USERNAME"`
  It prompts for your Windows password (stored DPAPI-encrypted in IIS config) and
  grants "Log on as a batch job". Deletes then go to *your* Recycle Bin and
  everything under your profile just works.
* **Default — grant read-in:** without `-PoolUser`, the script grants the pool
  identity read/execute on the base-Python and ffmpeg folders plus traverse on the
  `C:\Users\<you>\...` path to reach them. Works, but breaks if those tools move
  (a Python or ffmpeg update); re-run the script to re-grant.

## Deploy

From an **elevated** PowerShell prompt:

```powershell
cd C:\Personal\projects\ImageViewer\deploy
.\Deploy-ToIIS.ps1 -Port 8099 -PhotoLibrary D:\PhotoLibrary
```

If PowerShell blocks the script: `Unblock-File .\*.ps1` first, or run it as
`powershell -ExecutionPolicy Bypass -File .\Deploy-ToIIS.ps1 ...`.

The script is idempotent. It:

1. Verifies HttpPlatformHandler is installed and you're elevated.
2. Creates `backend\.venv` and installs `requirements.txt` (skip with an existing venv unless `-Build`).
3. Builds the frontend (`npm ci && npm run build`) if `frontend\dist` is missing or `-Build`.
4. Writes `deploy\web.config` from `web.config.template` with this machine's paths.
5. Creates app pool **PhotoLibrary** — *No Managed Code*, `AlwaysRunning`, idle timeout 0, periodic recycle off (so the scan process is never killed underneath you).
6. Creates site **PhotoLibrary** on the given port, physical path = `deploy\`.
7. Grants the pool identity (`IIS AppPool\PhotoLibrary`):
   - read/execute on `backend\`, `frontend\dist\`, `deploy\`
   - modify on `deploy\data\`, `deploy\logs\`
   - **modify on the photo library** (import/convert/delete need to write there)
8. Restarts the pool and checks `http://localhost:<port>/api/health`.

After pulling new code:

```powershell
.\Deploy-ToIIS.ps1 -Build          # rebuilds frontend + refreshes deps, then restarts
```

Optional face recognition (large download):

```powershell
..\backend\.venv\Scripts\python.exe -m pip install -r ..\backend\requirements-faces.txt
Restart-WebAppPool PhotoLibrary
```

## First use

Open `http://localhost:8099/`, then **Settings → Full re-index** to scan
`D:\PhotoLibrary`. The scan runs inside the IIS-hosted process; progress shows in
the top bar.

## Where things live

| Path | What |
|------|------|
| `deploy\web.config` | generated, machine-specific, git-ignored |
| `deploy\data\library.db` | SQLite catalog (+ `-wal`/`-shm`) |
| `deploy\data\thumbnails\` | thumbnail cache |
| `deploy\data\settings.json` | runtime settings edited from the UI |
| `deploy\logs\stdout*.log` | uvicorn / app stdout+stderr |

Back up `deploy\data\` to keep your people names, tags, ratings and duplicate
decisions. Deleting it just forces a rescan.

## Troubleshooting

**502.3 / "process failed to start"** — check `deploy\logs\stdout*.log`.
Usually one of:
- `Access is denied` for a `...\AppData\Local\Python\...` path — per-user Python;
  see "Per-user Python / ffmpeg" above (use `-PoolUser`, or re-run to re-grant).
- wrong `processPath` (venv missing) — re-run with `-Build`.
- `run.py` can't import `app` — check `PYTHONPATH` in `web.config`.

**Pool keeps stopping ("disabled")** — 5 fast startup failures disable it. Fix the
cause above; the script sets `rapidFailProtection=false` and calls
`Start-WebAppPool`, so a re-run revives it.

**Blank page but `/api/health` works** — frontend not built. Run with `-Build`.

**Thumbnails missing for videos, or no video metadata** — ffmpeg/ffprobe not
visible to the pool identity. Put them on the System PATH (then
`Restart-WebAppPool`) or set `FFMPEG_BINARY` / `FFPROBE_BINARY` in
`web.config.template` and redeploy.

**"Access is denied" writing to the library / can't delete** — the pool identity
lacks NTFS rights on `D:\PhotoLibrary`. Re-run the script (it grants them), or
grant `IIS AppPool\PhotoLibrary` Modify manually.

**Deletes don't reach the Recycle Bin** — `send2trash` needs a user profile; the
script sets `processModel.loadUserProfile = true`. If deletes still error, run the
pool under a real user account (Advanced Settings → Identity) that has a profile
and library access.

**Scan seems to stop** — confirm the pool isn't recycling: the script disables
idle timeout and periodic restart, but a machine reboot or `iisreset` restarts
the process (and with `AlwaysRunning` it comes straight back; just rescan).

**Port already in use** — the script refuses to continue; pick another `-Port`.
Check with `Get-NetTCPConnection -State Listen -LocalPort 8099`.

## Remove

```powershell
.\Uninstall-FromIIS.ps1     # drops the site + pool + NTFS grants, keeps deploy\data and your photos
```

## Alternative: IIS serves static, proxies only the API

If you'd rather IIS serve the frontend files directly (marginally faster, lets you
add IIS auth in front): install **Application Request Routing** + **URL Rewrite**,
point the site at `frontend\dist`, run uvicorn as a Windows service
(e.g. via `nssm`), and add a rewrite rule sending `^api/(.*)` to
`http://127.0.0.1:<uvicorn port>/api/{R:1}`. The bundled script does not do this —
it's more moving parts for little gain on a local box.
