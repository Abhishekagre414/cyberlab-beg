# HACK THE AI - CTF training platform

A self-hosted cybersecurity training platform: learners start isolated vulnerable labs, answer
mission questions and submit flags. Five beginner labs are bundled.

**Deploy it: read [`DEPLOY.md`](DEPLOY.md)** (about 15 minutes, one command).

```
CTFplatform/            the application (Flask + Postgres + Redis + nginx, all in docker-compose)
CTFplatform/lab_library the 5 bundled labs (zip files, imported by deploy.sh)
CTFplatform/deploy.sh   one-command deployment
CTFplatform/scripts/    TLS certificates, backup, end-to-end smoke test
DEPLOYMENT.md           deeper reference (env vars, Vercel notes, security features)
```
