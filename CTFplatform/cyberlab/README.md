# CyberLab Sim

A small, local, beginner-friendly cybersecurity training platform — 5 labs, a
scoring/progress system, tiered hints, three learning modes, step-by-step
stage tracking, and per-vulnerability security writeups with side-by-side
vulnerable/secure code. Every lab recreates a real class of bug in a safe,
self-contained way; nothing here reaches the internet or touches your real
filesystem outside this project folder.

> **⚠️ Safety warning:** This project intentionally contains vulnerable
> applications for educational purposes. Run only in a controlled local
> environment. Do not expose it to the public internet.

## 1. Project overview

CyberLab Sim is a Flask app you run on your own machine at
`http://127.0.0.1:5000`. It ships 5 self-contained, intentionally vulnerable
labs, each teaching one real vulnerability class end-to-end: find it, exploit
it safely, capture a flag, and read the remediation.

## 2. Features

- **5 labs**, each a different vulnerability class (info disclosure, SQLi,
  broken access control / IDOR, path traversal, insecure deserialization).
- **"Learn Before You Hack"** panel per lab (Beginner mode) — what the bug
  is, why it happens, a real-world example, impact, prevention, and what
  tools to use, in plain language.
- **Three learning modes** — Beginner / Normal / Challenge — selectable from
  the top of every page, stored in your session.
- **Step-by-step stage tracker** (Beginner mode) — Understand objective →
  Explore application → Identify vulnerability → Complete challenge → Learn
  remediation, with a live `[✓]`/`[ ]` checklist. Each stage is backed by its
  own real action — see "Learning stage tracking" below.
- **Flag submission system** — find the flag in-app, submit it via the box
  at the bottom of any page, and the lab is marked complete.
- **Progress and score, tracked independently** — course *progress* is
  `completed_labs / total_labs`, and is never reduced by using a hint. Score
  is a separate 0–500 total. See "Progress vs. score" below.
- **Progressive 3-level hint system** per lab — general direction → stronger
  clue → what to investigate. Hints never hand over the exact final payload.
  Wrong flag submissions get a contextual nudge instead of just "try again."
- **Post-completion celebration screen** — what you learned (3 key
  concepts), score earned, the next recommended lab, and buttons to the
  dashboard, the next lab, or the full security writeup.
- **Achievements** — 4 simple badges (First Steps, Vulnerability Explorer,
  CyberLab Graduate, Perfect Score), computed live from your session, shown
  on the dashboard.
- **Progress dashboard** at `/dashboard` — overall progress %, labs
  completed, total score / max possible, total hints used, current mode,
  recommended next lab, and achievements, with a simple progress bar.
- **Prev/Next lab navigation** on every lab page, plus a difficulty badge
  (🟢/🟡/🔴) — the numbered order is a recommendation, never enforced.
- **Reset button** per lab — clears that lab's progress without touching
  the others.
- **Security writeup + secure vs. vulnerable code** — CWE, severity, impact,
  root cause, detection method, remediation, and a short side-by-side code
  comparison, shown once a lab is completed.
- **Burp Suite guide** at `/burp-guide` — beginner-friendly walkthrough for
  using an intercepting proxy against these labs specifically.
- **`/health` endpoint** — plain JSON liveness check, used by Docker's
  healthcheck.
- **Open-redirect protection** — every route that accepts a `next` parameter
  validates it through a single reusable helper (`redirect_safety.py`)
  before ever redirecting to it.
- **Configurable secret key** — via a `SECRET_KEY` environment variable
  (see `.env.example`), with an obviously-labeled, warning-logged fallback
  for quick local testing.
- **Student/instructor separation** — full walkthroughs live in
  `instructor/SOLUTIONS.md`, which is never served by the web app (there is
  no route that exposes it — verified by automated tests).

## 3. Learning objectives

By working through all 5 labs, a beginner should come away able to:

- Recognize the shape of information disclosure, SQL injection, broken
  access control, path traversal, and insecure deserialization bugs.
- Understand *why* each bug happens (a root-cause mental model, not just
  "run this payload").
- Use browser DevTools (and optionally Burp Suite) to inspect and modify
  requests, cookies, and responses.
- Explain, for each vulnerability class, the real remediation a developer
  would apply.

## 4. Lab descriptions & difficulty levels

| # | Name | Vulnerability class | Difficulty |
|---|------|---------------------|------------|
| 1 | Leaky Backup File | Sensitive information disclosure + weak access control | 🟢 Easy |
| 2 | Login Bypass | SQL injection + account enumeration | 🟢 Easy |
| 3 | Peek at Anyone's Invoice | Broken access control (IDOR via a client-trusted cookie) | 🟡 Medium |
| 4 | Escape the Downloads Folder | Path traversal (incomplete-filter bypass) | 🟡 Medium |
| 5 | The YAML That Ran Code | Unsafe YAML deserialization — **simulated RCE, no real code execution** | 🔴 Hard/Advanced |

Labs are numbered in the intended learning order — work through them 1 → 5.
Each lab page has an **Objective**, a **Why this happens** explainer (hidden
in Challenge mode), a **Hints** panel (3 levels, revealed on request), and —
once completed — a **security writeup** with side-by-side vulnerable/secure
code. The lesson in every lab is the same at heart: trusting input (a URL, a
cookie, a filename, a config file, a keyword filter that only knows one
keyword) without truly verifying it.

## 5. Learning modes

Pick a mode from the selector at the top of any page. It's stored in your
session and applies to every lab immediately.

| Mode | What you get |
|------|---------------|
| **Beginner** | Full "Why this happens" explainer, the extended "Learn Before You Hack" panel, starter guidance, a step-by-step stage tracker, and all 3 hint levels. |
| **Normal** (default) | Standard "Why this happens" explainer, starter guidance, and all 3 hint levels — no extended explainer or stage tracker. |
| **Challenge** | Only the Objective and the challenge itself — no explainer, no starter guidance, no stage tracker, and hints capped at 1 level. |

## 5a. Progress vs. score

These are tracked **independently**, on purpose:

- **Progress** = `completed_labs / total_labs × 100`. Finishing all 5 labs
  is always 100% progress, whether you used zero hints or fifteen.
- **Score** = sum of each lab's score (100 points per lab, −10 per hint
  used, floor of 10 per lab). Shown separately on the dashboard as
  `total_score / max_possible`.

A student who grinds through every lab with heavy hints still sees
"100% progress" — hints affect score, never completion.

## 5b. Learning stage tracking

Each lab tracks 5 stages, each backed by its own real signal — **using a
hint never, by itself, marks a stage as done**:

| Stage | Marked by |
|-------|-----------|
| Understand Objective | Opening the lab's index page |
| Explore Application | Interacting with a secondary in-lab route (a login form, a file listing, an invoice page, etc.) |
| Identify Vulnerability | An explicit "✅ I found the vulnerability" self-report button — only enabled once you've explored, and never auto-checked by hint usage |
| Complete Challenge | Submitting the correct flag |
| Learn Remediation | Explicitly opening/marking the security writeup as read (only available once the lab is completed) |

Shown as a live `[✓]`/`[ ]` checklist in Beginner mode.

## 5c. Achievements

Computed live from your session on the dashboard — no separate state to
manage:

| Badge | Requirement |
|-------|-------------|
| 🥉 First Steps | Complete your first lab |
| 🥈 Vulnerability Explorer | Complete 3 labs |
| 🥇 CyberLab Graduate | Complete all 5 labs |
| 🏆 Perfect Score | Complete all 5 labs with no hints used on any of them |

## 6. Installation

Requires Python 3.9+.

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 6a. Environment variable setup

```bash
cp .env.example .env
# then edit .env and set a real SECRET_KEY, e.g.:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

`python-dotenv` (in `requirements.txt`) loads `.env` automatically if
present — plain `export SECRET_KEY=...` works too, and `.env` is already in
`.gitignore` so it's never committed.

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Signs the session cookie (progress, mode, hints) | An obviously-labeled dev fallback — a startup warning is logged if this isn't set |
| `FLASK_DEBUG` | `1` enables Flask debug mode | `0` (off) |
| `HOST` | Interface to bind to | `127.0.0.1` |

## 7. requirements.txt

Dependencies are pinned by minimum version in `requirements.txt`:

```
flask>=3.0
pyyaml>=6.0
pytest>=8.0
python-dotenv>=1.0
```

Install with `pip install -r requirements.txt` (add `--break-system-packages`
if pip refuses to install outside a virtual environment on Debian/Ubuntu).

## 8. How to run locally

```bash
python3 app.py
```

Open **http://127.0.0.1:5000**.

Progress, learning mode, and hint state are all stored in your browser's
session cookie — no database, no account system. Clearing cookies (or
opening a private/incognito window) gives you a fresh start.

Debug mode is **off by default**, even outside Docker. To turn it on while
actively developing this project:

```bash
FLASK_DEBUG=1 python3 app.py
```

## 9. How to run with Docker

A `Dockerfile` and `docker-compose.yml` are included, using a non-root user,
`requirements.txt` for dependencies, a container healthcheck against
`/health`, and exposing only port 5000 bound to `127.0.0.1` on the host.
**These have not been built or run** in the environment this project was
developed in (no Docker daemon / restricted network access there) — treat
them as a reasonable starting point to verify yourself, not as tested
artifacts.

```bash
docker compose up --build
```

Then open **http://127.0.0.1:5000** — the container is never reachable from
outside your machine. Set a real `SECRET_KEY` in `docker-compose.yml` (or an
`.env` file next to it) for anything beyond quick local testing.

## 10. How to run tests

```bash
pip install -r requirements.txt   # includes pytest
python3 -m pytest tests/ -v
```

Every test gets a brand-new Flask test client (and therefore an empty
cookie jar) via a function-scoped `client` fixture — since all state lives
in the signed session cookie, a fresh client has no session at all, so
tests can't inherit progress, score, hints, mode, or completion from each
other. This is verified directly by
`test_sessions_are_isolated_between_tests_a/b`.

Covers: app/dashboard/lab pages load, correct/incorrect flag handling per
lab, reset behavior, hint progression and scoring penalty, hints/reset/mode
being POST-only, learning-mode selection and its effect on page content,
challenge mode's hint cap, dashboard summary stats (including the
progress/score split), the Burp Suite guide page, vulnerable/secure code
display after completion, instructor solutions unreachable via any web
route, open-redirect rejection on every `next`-accepting route, stage
tracking independence from hint usage, achievement unlocking, the `/health`
endpoint, the actual vulnerable behavior for each lab (including the
filter-bypass techniques), and a check that no stray route exposes source
files. All 78 tests pass as of this writing.

## 10a. Health check

```bash
curl http://127.0.0.1:5000/health
# {"status": "ok", "service": "cyberlab"}
```

A plain, no-session-data liveness check. Docker Compose's `healthcheck`
block polls this automatically; you can also use it to confirm the app is
up before pointing a browser or proxy at it.

## 11. Using Burp Suite / DevTools with these labs

Visit `/burp-guide` in the running app for the full beginner walkthrough
(start Burp → configure the browser proxy → enable interception → visit the
lab → observe requests → send to Repeater → modify parameters/cookies →
analyze the response). In short:

- **Lab 3** requires editing a cookie — do this via your browser's
  DevTools (Application/Storage → Cookies) or by intercepting and modifying
  the request in Burp.
- **Lab 1** requires HTTP Basic Auth — Burp's Repeater or your browser's
  network panel will show you the `Authorization: Basic ...` header once
  you're authenticated.
- Success pages across the labs include an **HTTP Request/Response** panel
  showing the actual request that loaded the page, as a reference point for
  what you'd see in a real proxy tool.
- **Only ever point Burp Suite (or any proxy/scanner) at this local lab or
  systems you own/have explicit permission to test.**

## 12. Safety warning

> This project intentionally contains simulated or vulnerable cybersecurity
> training challenges for educational purposes. Run only in a controlled
> local environment. Do not expose the application to the public internet.

Lab 5's "RCE" is entirely simulated — no real shell commands are ever
executed, regardless of what payload you send. Nothing in this project sends
data externally, modifies files outside the project folder, or requires
elevated privileges. Docker Compose binds the port to `127.0.0.1` only, by
design — do not change this to `0.0.0.0` for a public-facing deployment.

## 13. Project structure

```
cyberlab/
  app.py                  # entry point, routes for flags/hints/reset/dashboard/mode/
                           # stages/health/burp-guide
  progress.py              # session-based progress, score, mode, achievements, stages
  redirect_safety.py       # reusable open-redirect validation helper
  labs/
    lab_meta.py            # flags, hints, learn-before content, code examples, key
                            # concepts, achievements, difficulty (single source of truth)
    lab1_creds.py ... lab5_deserialization.py
  templates/
    base.html               # shared layout + nav + mode selector
    burp_guide.html          # Burp Suite walkthrough page
    partials/
      lab_widgets.html        # hints / stages / reset / completion / writeup / code compare
      learn_before.html       # "Learn Before You Hack" panel (beginner mode)
      stage_tracker.html      # step-by-step stage checklist (beginner mode)
      completion_banner.html  # post-completion celebration screen
      lab_nav.html             # prev/next lab navigation
      http_panel.html         # request/response reference panel
    lab1/ ... lab5/
  server_files/            # sandboxed file storage used by Lab 4
  tests/
    test_app.py             # automated test suite (pytest, 78 tests)
  instructor/
    SOLUTIONS.md             # full walkthroughs -- NOT web-reachable
  requirements.txt
  .env.example
  .gitignore
  Dockerfile
  docker-compose.yml
```

## 14. Accidental vs. intentional vulnerabilities

This project intentionally contains 5 vulnerable labs — those are the
product, not bugs. Separately, the *platform code around* the labs (routing,
sessions, redirects) is held to normal secure-coding standards. As of this
version:

- **Open redirects — fixed.** Every route accepting a `next` parameter
  (`/submit-flag`, `/hint/<id>/<level>`, `/reset/<id>`, `/mode`,
  `/stage/<id>/identify`, `/stage/<id>/remediation`) validates it through
  `redirect_safety.safe_redirect_target()` before redirecting. Only
  same-site relative paths are allowed; external URLs, protocol-relative
  URLs (`//evil.example`), and backslash tricks all fall back to a safe
  default.
- **Hardcoded secret key — fixed.** `SECRET_KEY` now comes from the
  environment, with a clearly-labeled dev fallback that logs a startup
  warning rather than silently shipping a real-looking secret.
- **Debug mode — off by default**, opt-in only via `FLASK_DEBUG=1`.
- **Instructor solutions — confirmed unreachable** by any web route
  (automated test).
- **No public exposure by default** — `127.0.0.1` binding both locally and
  in Docker Compose.

## Scoring system

- Each lab starts at 100 points.
- Each hint revealed costs 10 points (hints are capped at 3 per lab in
  Beginner/Normal mode, 1 in Challenge mode — worst case is 70 points if all
  3 are used, floor enforced at 10).
- Score is locked in at the moment of first correct submission; resubmitting
  the same correct flag doesn't change it.
- **Score never affects progress percentage** — see section 5a.

## Instructor information

- `instructor/SOLUTIONS.md` has full, spoiler-level walkthroughs for all 5
  labs, including exact payloads. It is **not served by the Flask app** —
  there is no route anywhere that maps to the `instructor/` directory, and
  this is covered by an automated test (`tests/test_app.py`).
- `labs/lab_meta.py` is the single source of truth for flags, in-app hints,
  learn-before content, code examples, key concepts, achievements, and the
  CWE/severity/remediation writeups shown after completion.
- To reset a student's progress remotely, they just need to clear cookies
  for the site or use a fresh browser profile — there's no server-side
  account state to clean up.

## Any remaining issues or recommended future improvements

- Docker artifacts are untested in this environment (no daemon available) —
  verify `docker compose up --build` works on your machine before relying
  on it for a class.
- The "Explore Application" stage is inferred from hitting any secondary
  in-lab route, which is a reasonable proxy but not a guarantee of genuine
  engagement — good enough for a learning nudge, not a precise telemetry
  system.
- All state is client-session-based (no server-side accounts), which is
  intentional for a simple, local, single-user tool, but means there's no
  way for an instructor to see a *class's* aggregate progress without an
  additional (out-of-scope) reporting layer.
- `SECRET_KEY` rotation invalidates all existing sessions (everyone's
  progress resets) — expected behavior for a signed-cookie-only design, but
  worth knowing before rotating it mid-class.
