# HACK THE AI – Deployment Guide

Pick ONE target. They have different capabilities:

| Feature | Vercel | VPS / Docker Compose |
|---|---|---|
| Login, dashboard, quizzes, leaderboard, CyberLab challenge list | Yes | Yes |
| Docker lab containers (manual labs, uploaded labs) | **No** (no Docker on serverless) | Yes |
| Admin lab-zip upload (up to 100 MB) | **No** (Vercel body limit ≈ 4.5 MB) | Yes |
| CyberLab sim app (port 5050) | **No** | Yes (see note) |
| Data survives restarts | Only with hosted Postgres | Yes (volumes) |

If you only need the learning platform UI + accounts → Vercel is fine.
If you need the hands-on labs → use the VPS/Docker route.

---

## DEPLOYMENT FORM (fill this in first)

| # | Setting | Your value | Required? | How to get it |
|---|---|---|---|---|
| 1 | `SECRET_KEY` | ______________________ | **YES** | `python -c "import secrets; print(secrets.token_hex(32))"` |
| 2 | `ADMIN_PASSWORD` | ______________________ | **YES** (else random, printed once in logs) | choose a strong password |
| 3 | `DATABASE_URL` | ______________________ | **YES on Vercel** | Neon / Supabase / Vercel Postgres connection string (`postgres://` is auto-fixed to `postgresql://`) |
| 4 | `REDIS_URL` | ______________________ | **YES for Docker/VPS production** (compose sets it) | Upstash `rediss://…` or your Redis; the app refuses to start in production with per-process rate limits. On Vercel it is optional |
| 5 | `GEMINI_API_KEY` | ______________________ | No | Google AI Studio; empty = mock resume analysis |
| 6 | `SENTRY_DSN` | ______________________ | No | sentry.io project |
| 7 | `FORCE_HTTPS` | `false` | No | `true` only if YOUR nginx terminates TLS. Never needed on Vercel |
| 8 | `POSTGRES_PASSWORD` | ______________________ | **YES for Docker** | choose one (compose only) |
| 9 | Domain | ______________________ | No | for nginx / Vercel domain |

---

## Option A – Vercel

1. Create a free Postgres DB (Neon recommended) → copy the connection string into **row 3**.
2. Push this repo to GitHub (the `.gitignore`/`.vercelignore` keep the local DB, `.secret_key` and lab folders out).
3. Vercel → *Add New Project* → import the repo. Framework preset: **Other**. Leave build/output settings empty. Root directory = repo root (the folder containing `vercel.json`).
4. *Settings → Environment Variables* → add rows 1, 2, 3 (and any optional ones) for **Production**.
5. Deploy. The first request creates the tables and the `admin` account automatically.
6. Check `https://YOUR-APP.vercel.app/health` → `{"status":"ok","database":"ok"}`.
7. Log in as `admin` with the password from row 2.

If you skip `DATABASE_URL`, it still runs, but on a temporary SQLite file in `/tmp`: accounts and progress **disappear** whenever Vercel recycles the instance. Always use Postgres for real use.

## Option B – VPS with Docker Compose (full features)

```bash
cd CTFplatform
cp .env.example .env        # fill in SECRET_KEY, ADMIN_PASSWORD, POSTGRES_PASSWORD
docker compose up -d --build
docker compose logs -f web  # wait for "Seeded database successfully"
curl http://localhost/health
```

- Tables/seed run once in `docker-entrypoint.sh` before gunicorn starts (no 4-worker race).
- HTTPS: put certs in `./ssl`, enable the HTTPS block in `nginx/nginx.conf` and the `./ssl` volume in `docker-compose.yml`, then set `FORCE_HTTPS=true`.
- Labs launch on `127.0.0.1:10000-20000` of the server. Students on other machines can't reach those ports as-is; put a reverse proxy in front of them or run the platform on the same machine as the learner.
- The web container no longer mounts the raw Docker socket and runs as a non-root user. It reaches Docker through the `dockerproxy` service (an allow-list proxy on an internal network that blocks `exec`, volumes, swarm, secrets and system calls). Lab containers still need a dedicated server: they run uploaded code, so don't share the host with anything important.
- `lab_library/*.zip` holds the five sample labs; upload them from **Admin → Upload Lab** (the old pre-extracted copies and the shipped database were removed from the package).

---

## Hardening pass (security review follow-up)

| Area | Change |
|---|---|
| Shipped data | `hacktheai.db` (real accounts + audit log) removed from the package. A fresh DB is created and seeded on first start. |
| Docker access | Raw `docker.sock` mount replaced by `tecnativa/docker-socket-proxy`; `web` and `reaper` use `DOCKER_HOST=tcp://dockerproxy:2375`; `web` runs as `appuser`. |
| Native lab fallback | Previously, if Docker was down, uploaded lab code ran **directly on the web host with the full environment (SECRET_KEY, DB URL...)**. Now disabled unless `ALLOW_NATIVE_LABS=true` (dev only), and even then it gets an allow-listed environment. |
| Lab containers | All now get `cap_drop=ALL`, `no-new-privileges`, tmpfs `/tmp`, plus the existing CPU/RAM/PID limits and loopback-only ports. |
| Admin "add lab" | `lab_id` validated as a slug (was joined into a filesystem path unchecked); ZIP extracted with zip-slip, symlink, size and file-count checks (reuses the same checks as the other upload route). Duplicated error-rendering code refactored. |
| CSP | Scripts: no `'unsafe-inline'`; inline scripts use a per-request nonce; all inline `onclick`/`onsubmit`/`onmouseover` handlers replaced by `data-*` attributes + delegated listeners. Added `object-src 'none'`, `base-uri`, `form-action`, tighter `default-src`. Styles still allow inline (templates use `style=""`). |
| XSS | `innerHTML` sinks now escape server/lab-supplied text via `escapeHtml()`. |
| Auth | Session cleared on login/register/logout (fixation), 8h session lifetime, username/email/password validation (letter + number, no username-as-password), constant-time-ish login (dummy hash for unknown users), blank email stored as `NULL` (a 2nd user without email used to hit the UNIQUE index). |
| Flags | Compared with `hmac.compare_digest`; non-string JSON values no longer raise. |
| DB schema | `users.password` widened to `VARCHAR(255)`: scrypt hashes are 162 chars, so the old `VARCHAR(128)` would have failed registration on Postgres. |
| Dependencies | Bumped Flask 3.0.3, Werkzeug 3.0.6 (older had a debugger RCE fix), gunicorn 22 (request-smuggling fix), pypdf 5.1, python-dotenv 1.0.1, docker 7.1. Split into `requirements-core.txt` (web app), `CTFplatform/requirements.txt` (core + gunicorn/docker/psutil/Gemini) and a lean root `requirements.txt` for Vercel. `docker` is now an optional import. |
| Repo hygiene | Removed identical duplicate lab folders, generated `native_fallback.log`/`run_native.py`, empty dirs; analysis `.md` files moved to `CTFplatform/docs/`. |
| Tests | 7 -> 68. New suites: auth, flags, admin access control + upload safety, CSP/headers (including a scan that fails if an inline handler or un-nonced script is ever added), Docker hardening. |

Known limits (by design / not changed): flags are stored in plaintext (admins need to read them); styles keep `'unsafe-inline'`; `docker-compose.yml` has not been run against a live Docker daemon in this review (the Docker calls are unit-tested with a mock client).

## What was fixed earlier (root causes of the post-deploy errors)

1. **500 on every page with a session** – `FLASK_ENV=production` forced Redis sessions pointing at host `redis:6379`, which exists only in docker-compose. Now Redis is used only if `REDIS_URL` is set **and** answers a ping; otherwise signed cookies.
2. **Database never created** – `init_db()` only ran under `python app.py`. Under gunicorn/Vercel there were no tables. It now runs automatically on first request (or once in the Docker entrypoint) and tolerates seed races.
3. **Read-only filesystem** – SQLite file, uploaded labs and secret key were written next to the code. On serverless they now go to `/tmp`; `DATABASE_URL` (Postgres) is supported and the legacy `postgres://` scheme is auto-corrected.
4. **Redirect loops / insecure links behind a proxy** – added `ProxyFix`; Talisman only forces HTTPS when `FORCE_HTTPS=true`; cookies are `Secure` on Vercel.
5. **Random logouts** – the secret key was regenerated per instance on read-only hosts. Now it must come from `SECRET_KEY` (clear warning in logs if missing).
6. **Hardcoded credentials** – `admin/admin123` and `Alex/password123` were seeded. Admin password now comes from `ADMIN_PASSWORD` (or is random); the demo user is opt-in.
7. **Startup crash if Gemini SDK fails** – import is now optional with fallback to the mock analyser.
8. **Lab settings missing in production** – upload limits/paths lived only in `DevelopmentConfig`; moved to the base config.
9. **Docker compose** – removed the `.:/app` mount that overrode the built image, added volumes (uploads, redis), DB healthcheck, `.env`-based passwords, Docker socket for `web`, healthchecks, `unless-stopped`.
10. **nginx 413 on lab upload** – `client_max_body_size 100m` added.
11. **Upload path traversal** – the admin lab upload used the raw filename in a file path; it now uses `secure_filename`.
12. **Labs on serverless** – lab start/upload now return a clear 503/501 message instead of crashing or silently losing files.
13. **Tests** – rewritten to run on an isolated temp database and no longer touch `hacktheai.db` (now 68 tests, see above).
14. **Cleanup** – unused scratch files (`*_sync*.py`, `test_*.py` debug scripts, `fix_progress.py`) removed from the package.
15. **Vercel bundle** – `vercel.json` now sets `maxDuration` and excludes labs/cyberlab/data/DB/tests/pycache to stay under the size limit.

## Do this before going live

- **Rotate secrets.** `database/.secret_key` and `hacktheai.db` (real user accounts) were committed to git earlier (they are no longer in this package). Treat that key as compromised (use a new `SECRET_KEY`), and consider purging them from history (`git filter-repo`) since the repo history still contains them.
- Change the `admin` password after first login if you let it be auto-generated.
- Run the tests with `cd CTFplatform && python -m pytest tests -q` (safe: uses a temporary database).

---

## Security features added in v3

| Feature | How it works | Config |
|---|---|---|
| Login lockout | 5 failed logins per username in 15 min -> HTTP 429. Same for unknown names (no user enumeration). | `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_MINUTES` |
| Per-user flags | Put `{{TAG}}` in a lab flag, e.g. `FLAG{sqli_{{TAG}}}`. Each learner has a different tag, also passed to the lab container as env `LAB_FLAG_TAG`, so the lab app can print the matching flag. Flags without the token work as before. | - |
| Server-side hints | The server picks the next hint and charges XP once; clients can't skip or replay. | - |
| Restricted lab network | Uploaded labs run on `ctf_uploaded_labs`: no internet egress, no lab-to-lab traffic. Lab start fails closed if the network can't be created. | `LAB_ALLOW_OPEN_NETWORK=true` to override |
| Body limits | 2 MB everywhere (app and nginx) except `/admin/` (100 MB lab uploads). | `DEFAULT_MAX_BODY_BYTES` |

Known remaining risks: the Docker socket proxy still permits container creation and image builds (needed to run labs), so only
trusted admins may upload labs and the lab host should be disposable; CSP still allows inline styles; no 2FA or password reset.

---

## The five bundled labs (`lab_library/`)

| Order | Lab | Topic | Flag |
|---|---|---|---|
| 1 | The Exposed Employee File | Information disclosure / directory listing | `TECHCORP{hidden_file_found}` |
| 2 | The Missing Employee Access Control | IDOR | `TECHCORP{idor_found}` |
| 3 | The Missing Access Control | Broken access control (client-trusted role cookie) | `TC{broken_access_control}` |
| 4 | The Support Desk Incident | Reflected XSS | `TECHCORP{xss_ticket_found}` |
| 5 | The Suspicious Email | Phishing awareness | `TECHCORP{human_firewall}` |

Import them once on the server (idempotent; skips labs that already exist):

    docker compose exec web python import_lab_library.py --publish

Each zip has a `metadata.json` (title, storyline, 5 missions with questions, hints and the flag), a
Dockerfile at the zip root, and runs as a non-root user on port 5000. Instructor solution guides are
**not** inside the zips; they live in `docs/instructor_notes/`. The flags are fixed strings inside each lab app,
so they are the same for every learner (see "Per-user flags" above if you later adapt a lab to read `LAB_FLAG_TAG`).
