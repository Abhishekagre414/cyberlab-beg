# Deploying HACK THE AI (step by step)

## What you need
* A Linux server (Ubuntu 22.04+ is fine) with **Docker + Docker Compose v2**, 2 CPU / 4 GB RAM or more.
* For real users: a **domain name** whose DNS A record points at the server, and ports **80 and 443** open.
* This server will run intentionally vulnerable lab containers. Use a dedicated or disposable machine,
  not one that holds anything else important.

## 1. Run the tests first (5 minutes, on any computer with Python 3.11+)
```bash
cd CTFplatform
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-core.txt pytest
python -m pytest -q
```
Everything should pass. If something fails, stop and fix it (or send me the output); the test
suite has never been run by the person who wrote these fixes, so this step matters.
(GitHub Actions in `.github/workflows/ci.yml` runs the same thing on every push.)

## 2. Deploy
Copy the `CTFplatform` folder to the server, then:
```bash
cd CTFplatform
# real users, HTTPS (recommended):
DOMAIN=ctf.example.com EMAIL=you@example.com ./deploy.sh
# private LAN / testing, plain HTTP:
./deploy.sh
```
The script: creates `.env` with random secrets, gets a Let's Encrypt certificate, builds and
starts everything, imports the five labs, runs a smoke test and prints the **admin password**.
It is safe to re-run.

## 3. Let learners reach the labs
Each learner gets a lab container on a random port 10000-20000 of the server.
* **Learners work on the server's own desktop / via SSH tunnel / VPN into the server:** nothing to do
  (default, safest).
* **Learners are on other computers:** run `LAB_REMOTE=yes LAB_PUBLIC_HOST=ctf.example.com ./deploy.sh`
  (or set `LAB_BIND_ADDR=0.0.0.0` and `LAB_PUBLIC_HOST=<name or IP>` in `.env` and
  `docker compose up -d`). Then in your firewall **allow TCP 10000-20000 only from your learners'
  IPs or VPN**, never from the whole internet. Labs open in a new tab over plain HTTP; this is by design.

## 4. Verify like a learner (5 minutes)
1. Open the site, log in as `admin`, change the password.
2. Register a normal account in a private window.
3. Open **Interactive Labs**, start "The Exposed Employee File", log in to the lab as `alex` / `Alex@123`,
   find the flag and submit it. The score should update.
Automated version of the same checks: `python3 scripts/smoke_test.py https://ctf.example.com`

## Day-2 operations
| Task | Command |
|---|---|
| Logs | `docker compose logs -f web` |
| Backup database | `scripts/backup.sh` (cron it daily) |
| Renew certificate | `scripts/get_cert.sh ctf.example.com you@example.com` (cron it monthly) |
| Update | replace the folder contents, then `./deploy.sh` |
| Stop / start | `docker compose down` / `docker compose up -d` |
| Change a lab | admin panel > Labs > Upload, or edit `lab_library/` and re-import |

## Known limits (read before opening it to the public)
* Lab flags are fixed strings, so one learner can share them with others.
* The Docker socket proxy still allows container creation and image builds (the labs need them).
  Only trusted admins may upload labs, and the server should be disposable.
* The page CSP still allows inline styles; there is no 2FA and no password-reset flow.
* The lab containers have no internet access (by design), but the server's firewall is still your
  main protection for the 10000-20000 port range.
