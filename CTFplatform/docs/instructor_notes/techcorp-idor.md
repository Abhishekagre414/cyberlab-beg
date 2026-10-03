# INSTRUCTOR GUIDE (Do not distribute to learners)

## Intended Vulnerability

**Class:** Insecure Direct Object Reference — IDOR
(CWE-639: Authorization Bypass Through User-Controlled Key / OWASP A01:2021 – Broken Access
Control).

**Mechanism:**

- Authentication is implemented correctly: `POST /login` checks credentials against
  `werkzeug.security.check_password_hash` and, on success, sets a cryptographically signed Flask
  session cookie (`session['user_id']`). This part of the app is **not** vulnerable — you cannot
  forge a valid authenticated session without knowing a real password.
- Every employee record has a numeric **employee ID** (`emp_id`: 101, 102, 103, ...). The profile
  page is served from `GET /profile/<int:emp_id>`.
- The `profile()` route in `app.py` looks the record up **purely from the `emp_id` supplied in the
  URL** (`get_user_by_emp_id(emp_id)`) and renders it. It performs **no authorization check** that
  the authenticated user (`session['user_id']`) is allowed to view *that particular* record.
- Because the object reference (the ID) is directly user-controlled, a learner authenticated as
  `alex` (`emp_id` 101) can simply edit the URL:

  ```
  /profile/101   ->   /profile/102
  ```

  and the server returns Rahul Sharma's private profile (Finance, `emp_id` 102), which contains the
  flag.

## Expected Exploitation Path

1. Log in as `alex` / `Alex@123`.
2. Open **My Profile**; observe the URL `http://127.0.0.1:5000/profile/101`.
3. Recognize that the trailing `101` is a user-controlled employee identifier.
4. Change it to `102` (or use browser DevTools / the address bar) and request `GET /profile/102`.
5. The server renders another employee's profile. The app detects that the requested `emp_id`
   differs from the authenticated user's own `emp_id` (this check exists purely to award the flag
   and log the event — it does not affect the vulnerability itself) and the profile displays:

   ```
   FLAG: TECHCORP{idor_found}
   ```

## Seeded Employee Records

| emp_id | username | role          | department        | flag                   |
|--------|----------|---------------|-------------------|------------------------|
| 101    | alex     | employee      | IT Support        | — (learner's own)      |
| 102    | rahul    | employee      | Finance           | **TECHCORP{idor_found}** |
| 103    | priya    | employee      | Marketing         | —                      |
| 104    | sarah    | manager       | Security Team     | —                      |
| 105    | admin    | administrator | IT Administration | —                      |

Only `alex` / `Alex@123` is given to the learner. Accessing **any** record other than 101 sets
`session['flag_captured']` (demonstrating the IDOR); the flag string itself lives only in record
102, so the learner must enumerate to it.

## Interface Notes

The lab presents as a single-page, TryHackMe-style shell (`templates/lab.html` +
`static/lab.js` + `static/lab.css`):

- The left panel holds all mission/task content, a graded flag-submission box
  (`/api/submit-flag`), and the knowledge check (`/api/knowledge-check`).
- The right panel is a cosmetic "virtual desktop." Its Firefox icon opens the real vulnerable
  Flask routes (`/login`, `/dashboard`, `/profile/<id>`, etc.) inside an `<iframe>` styled as a
  browser window — this is the actual attack surface. The Terminal icon is decorative/flavor text
  only; it does not execute real shell commands, since the exploit only requires changing the
  numeric ID in real HTTP requests to `127.0.0.1:5000`.
- `/api/submit-flag` only returns `correct: true` if the current session actually triggered the
  vulnerability (`session['flag_captured']`) **and** the submitted string matches the flag exactly
  — this prevents learners from guessing the flag without exploiting the app.

## Flag

```
TECHCORP{idor_found}
```

The flag is only rendered inside `templates/profile.html` for the record that carries it
(`emp_id` 102). It is not present in any source file the learner is expected to read, comment,
static asset, or the learner README.

## Mission Solutions / Challenge Answers

- **What vulnerability did you discover?** IDOR — Insecure Direct Object Reference.
- **What part of the URL controlled which profile was displayed?** The numeric employee ID at the
  end of the path (`/profile/<id>`).
- **Were you authorized to access the other employee's profile?** No — authentication succeeded,
  but the account had no authorization to view another employee's record.
- **What is the flag?** `TECHCORP{idor_found}`.
- **Which server-side check was missing?** A per-object authorization check confirming that the
  logged-in user is permitted to view the requested `emp_id` (e.g. that the record is their own,
  or that their role grants access).
- **How should TechCorp prevent it?** Enforce server-side authorization on every object request;
  do not rely on hidden fields or client-side restrictions; verify the logged-in user is permitted
  to access the requested record; consider non-sequential / unguessable identifiers as defense in
  depth (but authorization is the real fix).

## Knowledge Check Answer Guidance

The MVP validator (`/api/knowledge-check` in `app.py`) does simple keyword matching:

- **Concept answer** (what is IDOR) must contain one of: `object`, `reference`, `identifier`,
  `id`, `direct`, `idor`.
- **Prevention answer** must contain one of: `authori(z/s)e`, `access control`, `permission`,
  `server-side`, `verif`, `owner`, `check`, `allow`, `right`.
- **Summary** must be at least 8 words.
- The knowledge check also requires `session['flag_captured']` to be true.

This is intentionally lenient for an MVP; tighten as needed for a real classroom setting.

## How to Verify the Vulnerability Yourself

```bash
./start.sh
# In another terminal:
curl -s -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5000/login \
  -d "username=alex&password=Alex@123"

# Your own profile (allowed and expected):
curl -s -b cookies.txt http://127.0.0.1:5000/profile/101 | grep -i "Employee ID"

# Another employee's profile via IDOR — the flag appears here:
curl -s -b cookies.txt http://127.0.0.1:5000/profile/102 | grep -i "FLAG"
```

You should see the flag text appear in the `/profile/102` response even though you authenticated
as `alex` (emp_id 101).

## Reset Verification

Run `./reset.sh`, then confirm:
- `database/techcorp.db` has been recreated with the five default employee records.
- The flag cannot be obtained from `/api/submit-flag` until a non-own profile has actually been
  requested in the current session (i.e., `flag_captured` must be set by visiting another record).

## Safety Notes

- The route uses `<int:emp_id>`, so only integer IDs are accepted; there is no path-traversal or
  arbitrary-object surface beyond the seeded employee table.
- The vulnerability is fully self-contained: it only exposes fictional records inside this app's
  own SQLite database on localhost.
