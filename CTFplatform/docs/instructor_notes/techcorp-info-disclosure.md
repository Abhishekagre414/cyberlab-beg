# INSTRUCTOR GUIDE (Do not distribute to learners)

## Intended Vulnerability

**Class:** Information Disclosure / Sensitive Data Exposure via predictable file paths and an
over-permissive file server (CWE-538 Exposure of Information Through Sent Data, CWE-548
Directory Listing, related to OWASP A01:2021 Broken Access Control and A05:2021 Security
Misconfiguration).

**Mechanism:**

- Authentication is implemented correctly: `POST /login` checks credentials against
  `werkzeug.security.check_password_hash` and sets a secure, signed Flask session cookie. You
  cannot forge a valid authenticated session without a real password.
- After login, the portal only advertises the current employee's own documents on `/documents`,
  each linked at a predictable path: `/files/EMP1042/profile.txt`, `.../training.pdf`,
  `.../payslip.pdf`.
- The file-serving route `/files/<path:subpath>` (see `app.py`, function `files()`) has **two
  intentional flaws**:
  1. **No per-resource authorization.** It serves any file under the `documents/` store to any
     authenticated user, without checking that the requested folder belongs to that user.
  2. **Directory listing enabled.** Requesting a folder (e.g. `/files/` or `/files/hr/`) returns
     an index of its contents instead of denying the request.
- Because the folder segment (employee ID) is predictable and the file server lists directories,
  an authenticated employee can walk up from their own document URL to `/files/`, discover an
  internal `hr/` folder that is never linked in the UI, and open the sensitive salary report.

**Safety:** `resolve_in_sandbox()` rejects `..` segments and absolute paths and confirms the
resolved path stays inside `documents/`. The exposure is therefore logical (within the lab's own
fictional data) and cannot read real files elsewhere on the host.

## Expected Exploitation Path

1. Log in as `alex` / `Alex@123`.
2. Open **My Documents** and click a file. Observe the URL, e.g.
   `http://127.0.0.1:5000/files/EMP1042/profile.txt`.
3. Edit the address bar (or use DevTools → Network) to request the **folder** instead of a file:
   - `http://127.0.0.1:5000/files/EMP1042/` → lists the employee's files.
   - `http://127.0.0.1:5000/files/` → lists **all** folders, including `hr/` and `EMP1043/`.
4. Open `http://127.0.0.1:5000/files/hr/` → lists `employee_salary_report.txt` and `README.txt`.
5. Open `http://127.0.0.1:5000/files/hr/employee_salary_report.txt`.
6. The server detects that the sensitive file was retrieved, sets `session['flag_captured']`,
   logs the event, and the file content reveals:

   ```
   FLAG: TECHCORP{hidden_file_found}
   ```

Submitting the flag in the Task 5 box then validates server-side.

## Flag

```
TECHCORP{hidden_file_found}
```

The flag is written **only** into the exposed file on disk
(`documents/hr/employee_salary_report.txt`, created by `init_docs()`). It is not present in any
template, static asset, comment served to the learner, `robots.txt`, or the README.

## Interface Notes

The lab presents as a single-page, TryHackMe-style shell (`templates/lab.html` + `static/lab.js`
+ `static/lab.css`):

- The left panel holds all mission/task content, a graded flag-submission box
  (`/api/submit-flag`), and a knowledge check (`/api/knowledge-check`).
- The right panel is a cosmetic "virtual desktop." Its Firefox icon opens the real vulnerable
  Flask routes inside an `<iframe>`; this is the actual attack surface. The Terminal icon is
  decorative/flavor only.
- `/api/submit-flag` only returns `correct: true` if the current session actually retrieved the
  sensitive file (`session['flag_captured']`) **and** the submitted string matches the flag
  exactly — this prevents guessing the flag without performing the disclosure.

## Progress / State Mapping

- **Task 1 (Briefing)** — ticks once the lab is started.
- **Task 2 (Mission 1: login)** — `mission >= 2`, set on successful login.
- **Task 3 (Mission 2: explore documents)** — `mission >= 3`, set on visiting `/dashboard` or
  `/documents`.
- **Task 4 (Mission 3: inspect paths)** — `mission >= 4`, set the first time a **directory
  listing** under `/files/` is rendered (i.e. the learner started browsing the store).
- **Task 5 (Mission 4: exposed file)** — `flag_captured`, set when the sensitive file is read.
- **Task 6 / 7 (Mission 5 + knowledge check)** — `knowledge_check_passed`, set on a passing
  final check, which also completes the lab.

## Mission Solutions / Challenge Question Answers

1. **What type of vulnerability?** Information Disclosure / Sensitive Data Exposure (files
   reachable via predictable paths with no authorization; directory listing enabled).
2. **Why was the sensitive file accessible?** The file server served documents by path to any
   logged-in user without verifying the resource belonged to them, and directory listing exposed
   the folder's existence.
3. **What information was exposed?** An internal HR consolidated salary report
   (`hr/employee_salary_report.txt`) that should never be on the employee portal.
4. **What is the flag?** `TECHCORP{hidden_file_found}`.
5. **What control should TechCorp implement?** Enforce authorization on every file request
   (check the file belongs to the authenticated user / their role), disable directory listing,
   store sensitive files outside the web-served store, and avoid predictable/guessable paths
   (use non-enumerable identifiers or signed URLs).

## Knowledge Check Answer Guidance

The MVP validator (`/api/knowledge-check`) does lenient keyword matching:

- **"Information Disclosure is"** must contain one of: `expos*`, `disclos*`, `leak*`,
  `sensitive`, `unauthoris/zed`, `reveal*`.
- **"A control that would have prevented it"** must contain one of: `authoris/zation`,
  `access control`, `permission*`, `acl`, `restrict*`, `authenticat*`, `privat*`, `encrypt*`,
  `random*`, `stor*`, `non-predictable`.
- **Summary** must be at least 8 words.
- The learner must also have captured the flag first.

Tighten these for a real classroom setting as needed.

## How to Verify the Vulnerability Yourself

```bash
./start.sh
# In another terminal:
curl -s -c cookies.txt -b cookies.txt -X POST http://127.0.0.1:5000/login \
  -d "username=alex&password=Alex@123" -o /dev/null

# Directory listing is exposed:
curl -s -b cookies.txt http://127.0.0.1:5000/files/ | grep -i "hr/"

# Sensitive file is reachable by predictable path:
curl -s -b cookies.txt http://127.0.0.1:5000/files/hr/employee_salary_report.txt | grep -i "FLAG"
```

You should see the `hr/` folder in the listing and the flag inside the salary report.

## Reset Verification

Run `./reset.sh`, then confirm:
- `database/techcorp.db` is recreated with the default users.
- `documents/` is recreated with `EMP1042/`, `EMP1043/`, and `hr/`.
- The flag can be obtained only by reaching `hr/employee_salary_report.txt`, and
  `/api/submit-flag` rejects the flag until that file has actually been retrieved in-session.

## Troubleshooting

- **`documents/` missing / file 404s:** Run
  `python3 -c "from app import init_docs; init_docs()"`, or just run `./start.sh`, which rebuilds
  the store on every start.
- **Flag box says "Find and open the exposed sensitive file first":** The learner must actually
  open `hr/employee_salary_report.txt` in-session before the flag validates. This is by design.
- **Directory listing not appearing:** Ensure the trailing behavior of the URL — requesting a
  folder path (with or without a trailing slash) returns the index; requesting a file returns the
  file.
- **Port already in use:** Another process may be bound to 5000. Stop it or change the port in
  the `app.run(...)` call in `app.py`.

## Scoring

The lab awards a maximum of **100 points**. Scoring is server-side and every milestone is awarded only once per session.

| Milestone | Points | Backend trigger |
|---|---:|---|
| Login completed | 10 | Successful employee login while the lab is running |
| Documents explored | 10 | Visit `/documents` while the lab is running |
| Other employee document | 20 | Read a document under an employee folder other than the learner's |
| Directory listing discovered | 15 | Request any directory under `/files/` |
| HR repository discovered | 15 | Request `/files/hr/` |
| Sensitive document accessed | 20 | Read `hr/employee_salary_report.txt` |
| Flag submitted | 10 | Submit the exact flag after retrieving the sensitive file |

The read-only score endpoint is `GET /api/lab/score`. It does not accept a score from the client. `/lab/reset` clears the session, including score milestones.
