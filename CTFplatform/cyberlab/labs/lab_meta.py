"""
Central metadata for all labs -- single source of truth so app.py and
each lab module don't duplicate flags/hints/security info.

Keeping this in one file also makes the student/instructor separation
easier to reason about: HINTS are meant for students (revealed
progressively, in-app). SOLUTIONS.md (full walkthroughs) lives in
instructor/ and is never imported by anything the web app serves.
"""

LAB_IDS = ["lab1", "lab2", "lab3", "lab4", "lab5"]

LAB_TITLES = {
    "lab1": "Leaky Backup File",
    "lab2": "Login Bypass",
    "lab3": "Peek at Anyone's Invoice",
    "lab4": "Escape the Downloads Folder",
    "lab5": "The YAML That Ran Code",
}

DIFFICULTY = {
    "lab1": "🟢 Easy",
    "lab2": "🟢 Easy",
    "lab3": "🟡 Medium",
    "lab4": "🟡 Medium",
    "lab5": "🔴 Hard",
}

# CSS badge class per lab, used by templates (avoids fragile string matching
# on the difficulty label text).
DIFFICULTY_CLASS = {
    "lab1": "beginner",
    "lab2": "beginner",
    "lab3": "mid",
    "lab4": "mid",
    "lab5": "hard",
}

# Order labs should be tackled in -- easiest concepts first. Same as the
# numeric order today, kept as an explicit list so the learning path is
# documented rather than implied by dict ordering.
LEARNING_ORDER = ["lab1", "lab2", "lab3", "lab4", "lab5"]


def lab_nav(lab_id):
    """(previous_lab, next_lab) info dicts (or None) for simple prev/next
    navigation between labs, in the recommended learning order. Purely
    informational -- students are never forced to follow this order."""
    def _info(lid):
        if lid is None:
            return None
        return {"id": lid, "title": LAB_TITLES[lid], "difficulty": DIFFICULTY[lid], "url": f"/{lid}/"}

    if lab_id not in LEARNING_ORDER:
        return None, None
    idx = LEARNING_ORDER.index(lab_id)
    prev_id = LEARNING_ORDER[idx - 1] if idx > 0 else None
    next_id = LEARNING_ORDER[idx + 1] if idx < len(LEARNING_ORDER) - 1 else None
    return _info(prev_id), _info(next_id)

# Three learning modes. Stored in the session; controls how much scaffolding
# (explanations, starter guidance, step tracker) each lab page shows.
MODES = ["beginner", "normal", "challenge"]
DEFAULT_MODE = "normal"
MODE_LABELS = {
    "beginner": "🟢 Beginner — full guidance",
    "normal": "🟡 Normal — standard hints",
    "challenge": "🔴 Challenge — minimal help",
}
# How many of a lab's hint levels are unlockable in each mode.
MODE_HINT_CAP = {"beginner": 3, "normal": 3, "challenge": 1}

FLAGS = {
    "lab1": "CYBERLAB{backups_are_not_hidden_theyre_just_unlinked}",
    "lab2": "CYBERLAB{quotes_in_user_input_are_never_just_quotes}",
    "lab3": "CYBERLAB{an_id_in_the_url_is_not_a_permission_check}",
    "lab4": "CYBERLAB{dot_dot_slash_still_works_if_nobody_checks}",
    "lab5": "CYBERLAB{yaml_load_without_safe_is_a_loaded_gun}",
}

# Three levels per lab: general direction -> more specific -> strong clue.
# None of these hand over the exact final payload -- that stays in
# instructor/SOLUTIONS.md.
STAGE_LABELS = [
    "Understand the objective",
    "Explore the application",
    "Identify the vulnerability",
    "Complete the challenge",
    "Learn the remediation",
]

# "Learn Before You Hack" — shown before a beginner ever touches a payload.
# Plain-language, no jargon. Kept short on purpose.
LEARN_BEFORE = {
    "lab1": {
        "what": "Sensitive information disclosure: a website accidentally shows files, credentials, or notes it never meant to publish.",
        "why": "Developers leave backup files, old configs, or debug notes inside folders the web server can still reach, assuming 'nobody will find it' is the same thing as 'nobody can find it.'",
        "example": "A company backs up its database config to `config_old.bak` in the same folder as its website, forgetting the web server can serve that file to anyone who requests it by name.",
        "impact": "Leaked credentials, internal hostnames, or API keys can give an attacker a foothold without needing to 'hack' anything at all.",
        "prevention": "Never store backups, credentials, or notes inside a web-servable folder. Delete rotated secrets instead of just renaming them. Don't rely on a file being 'unlinked' as protection.",
        "tools": "Your browser's 'View Page Source' (or DevTools → Elements) and the Network tab are all you need — no special software required.",
    },
    "lab2": {
        "what": "SQL Injection: user input is inserted directly into a database query, letting an attacker change what the query actually does.",
        "why": "Building SQL queries by gluing strings together (instead of using safe, parameterized queries) means anything a user types becomes part of the command the database executes.",
        "example": "A login form checks `password = 'whatever_you_typed'`. If you type `' OR '1'='1`, the query becomes always-true, and the check passes with no real password at all.",
        "impact": "Full authentication bypass, or reading/modifying any data in the database — often the single most damaging class of web vulnerability.",
        "prevention": "Always use parameterized queries / prepared statements. Never build SQL by string-formatting user input. Hash passwords so a bypass doesn't hand over plaintext credentials.",
        "tools": "Your browser's DevTools Network tab (to see the request being sent) and simple test characters like a single quote `'` to see how the app reacts.",
    },
    "lab3": {
        "what": "IDOR (Insecure Direct Object Reference): the app lets you access someone else's data just by changing an ID or a cookie value.",
        "why": "The app checks *that* something looks like an identity, but not whether it's the *real, trusted* identity — often trusting a value the browser itself is allowed to edit.",
        "example": "An online store shows your order at `/order/1024`. Changing the URL to `/order/1025` shows a stranger's order, because the server never checked whether order 1025 belongs to you.",
        "impact": "Any user can view or modify data belonging to any other user — a serious privacy and business-logic failure.",
        "prevention": "Authorization must always be based on the server-side, signed session — never on a plain cookie, hidden field, or URL parameter the client can edit.",
        "tools": "Your browser's DevTools → Application/Storage → Cookies panel, to view and edit cookie values directly.",
    },
    "lab4": {
        "what": "Path Traversal: crafted input tricks a file-serving feature into reading files outside the folder it was meant to stay in.",
        "why": "A filename or path comes from the user, and the code trusts it too much — sometimes after a 'sanitization' step that doesn't actually close every loophole.",
        "example": "A file-download feature accepts `?file=report.pdf`, but also accepts `?file=../../etc/passwd`, walking back up out of the intended folder.",
        "impact": "Reading configuration files, credentials, or other users' private documents that were never meant to be public.",
        "prevention": "Never build a safe path by blacklisting substrings. Resolve the final absolute path and verify it's still inside the intended folder before opening it. Prefer opaque IDs over raw filenames.",
        "tools": "Your browser's address bar or DevTools Network tab, to try different values for the file/path parameter and observe the response.",
    },
    "lab5": {
        "what": "Insecure Deserialization: a file format meant only for *data* (like YAML or Pickle) is parsed in a way that can *run code* instead.",
        "why": "Some parsers support special tags for advanced use cases (like constructing custom objects). If the parser trusts user input and those tags are enabled, a 'data file' becomes a way to execute arbitrary logic.",
        "example": "A settings-import feature calls `yaml.load()` (the full, unsafe loader) on a file a user uploads. A crafted YAML tag causes the server to call a system function instead of just storing data.",
        "impact": "In a real app, this is usually full remote code execution — the most severe class of vulnerability, since the attacker isn't just reading data, they're running commands as the server.",
        "prevention": "Always use the 'safe' variant of a deserializer for untrusted input (e.g. `yaml.safe_load()`), which has no concept of 'construct arbitrary object' or 'call a function' at all.",
        "tools": "A text editor to craft YAML payloads, and this lab's built-in response panel to see what got parsed.",
    },
}

# Simplified before/after code snippets shown after a lab is completed.
# Kept short and focused on the one root-cause fix, not a full rewrite.
CODE_EXAMPLES = {
    "lab1": {
        "vulnerable": "# Backup files left inside the web-servable folder\nstatic/\n  backup/\n    config_prod_2026.yaml.bak   # never deleted, just renamed after rotation",
        "secure": "# Delete rotated secrets. Keep backups OUTSIDE the web root entirely.\nimport os\nos.remove('/var/backups/config_old.yaml.bak')  # done after rotation, not renamed\n# ...and store real backups in /var/backups/, never inside static/ or templates/",
    },
    "lab2": {
        "vulnerable": "query = f\"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'\"\ncur = conn.execute(query)",
        "secure": "query = \"SELECT * FROM users WHERE username = ? AND password = ?\"\ncur = conn.execute(query, (username, password))  # parameterized -- input can never change the query structure",
    },
    "lab3": {
        "vulnerable": "claimed_id = request.cookies.get('x_client_user_id', type=int)\nauthorized = (claimed_id == invoice_id)  # trusts a client-editable cookie",
        "secure": "user_id = session['user_id']  # from the signed, server-side session only\nauthorized = (user_id == invoice_id) and record_belongs_to(user_id, invoice_id)",
    },
    "lab4": {
        "vulnerable": "cleaned = filename.replace('../', '')  # single pass, easy to bypass\npath = os.path.join(DOWNLOADS_DIR, cleaned)",
        "secure": "resolved = os.path.realpath(os.path.join(DOWNLOADS_DIR, filename))\nif not resolved.startswith(os.path.realpath(DOWNLOADS_DIR) + os.sep):\n    abort(403)  # verify the FINAL resolved path, not the raw string",
    },
    "lab5": {
        "vulnerable": "parsed = yaml.load(user_input, Loader=yaml.Loader)  # full loader -- can call functions",
        "secure": "parsed = yaml.safe_load(user_input)  # safe loader -- only ever builds plain data types",
    },
}

# Short, non-spoiling nudge shown after an incorrect flag submission, to
# help students think about *why* an attempt might have failed instead of
# just guessing again.
WRONG_ATTEMPT_TIPS = {
    "lab1": "Think about how you found the credentials -- did you follow the chain all the way to the unlinked production file, or stop at a decoy?",
    "lab2": "Think about how the application processes your input, and whether the exact login response confirmed a full bypass (admin role) rather than a regular account.",
    "lab3": "Think about which value the authorization check actually reads -- and whether you've combined both flag fragments in the right order.",
    "lab4": "Think about whether your path really escaped the intended folder, and whether you picked the right sibling directory once you did.",
    "lab5": "Think about whether your YAML tag actually got resolved into a function call, and what argument you passed to it.",
}

# Achievements are computed live from session progress in progress.py --
# no separate state to keep in sync. "threshold" = labs completed needed
# (ignored for the perfect_score id, which has its own check).
ACHIEVEMENTS = [
    {"id": "first_steps", "icon": "🥉", "title": "First Steps", "description": "Complete your first lab.", "threshold": 1},
    {"id": "explorer", "icon": "🥈", "title": "Vulnerability Explorer", "description": "Complete 3 labs.", "threshold": 3},
    {"id": "graduate", "icon": "🥇", "title": "CyberLab Graduate", "description": "Complete all 5 labs.", "threshold": 5},
    {"id": "perfect_score", "icon": "🏆", "title": "Perfect Score", "description": "Complete all labs with maximum score (no hints used).", "threshold": 5},
]

# Three short "what you learned" bullets shown on the post-completion
# celebration screen. Deliberately plain-language, not a restatement of
# the CWE-heavy SECURITY_INFO writeup.
KEY_CONCEPTS = {
    "lab1": [
        "Files inside a web-servable folder are reachable by anyone who knows (or guesses) the name -- 'unlinked' is not the same as 'protected'.",
        "robots.txt and HTML comments are hints for crawlers and other developers, not access control.",
        "Rotating a credential means deleting the old one, not just renaming the file it lives in.",
    ],
    "lab2": [
        "Any feature that responds differently for 'valid account' vs. 'invalid account' leaks which accounts exist.",
        "String-building a SQL query from user input lets that input change the query's actual logic.",
        "A filter that blocks one exact pattern (like '--') doesn't block every way to achieve the same effect.",
    ],
    "lab3": [
        "The browser can edit almost anything client-side -- cookies, hidden fields, query params -- so none of them are safe to trust for authorization.",
        "A working login session doesn't guarantee every check on every page actually uses that session.",
        "'It looks like an ID' and 'it's a verified identity' are two very different things to a server.",
    ],
    "lab4": [
        "A single-pass string filter can be defeated by input engineered to produce the blocked pattern only after the filter runs once.",
        "The fix is to check the final, resolved path -- not to blacklist substrings in the raw input.",
        "Public-facing 'helpful' notes (READMEs, comments) can accidentally leak the names of things that were meant to stay private.",
    ],
    "lab5": [
        "Some data formats (YAML, Pickle) can be told to construct objects or call functions, not just store values.",
        "The 'safe' variant of a parser exists specifically because the full version trusts too much.",
        "A keyword filter that blocks one function name doesn't block every function that does the same thing.",
    ],
}

HINTS = {
    "lab1": [
        "Standard recon: check what a crawler is told to avoid, and don't trust the rendered page — sometimes the interesting part only shows up in the page source.",
        "There's a base64 string hidden in an HTML comment on the lab's main page. Decoding it gives you HTTP Basic Auth credentials for a folder mentioned in robots.txt.",
        "Once inside the backup folder, the real file (not the obviously-unrelated decoy) describes a filename pattern in its comments — one word in that pattern is ROT13-encoded, not plaintext.",
    ],
    "lab2": [
        "There's an account-related feature on this app besides the login form itself — something that reacts differently depending on whether a username is real.",
        "The admin account isn't named 'admin' and isn't one of the five teammates. Think ops/root-style naming, and confirm your guess with the enumeration feature.",
        "The login form strips out '--' from your input, but SQLite treats an *unclosed* /* block comment as 'ignore the rest of the statement' too — that's not filtered.",
    ],
    "lab3": [
        "You're logged in with a session, and there's a separate piece of client-side state involved in how the app decides you're allowed to see a given invoice.",
        "Check your browser's cookies for this site (DevTools → Application/Storage → Cookies). One of them looks like it's just there for display — but the server actually trusts it.",
        "Edit that cookie's value to a different invoice ID than the one your real session belongs to, then request that same ID's invoice page.",
    ],
    "lab4": [
        "Confirm the filter exists first — a plain '../' traversal attempt just quietly does nothing, no error either.",
        "Think about what a single, one-time string.replace('../', '') does to input that contains more dots/slashes than the exact pattern — could removing a match from the middle leave the pattern behind on the outside?",
        "There's more than one folder next to the public downloads folder. A public team note casually mentions the real one's name — the other is a decoy.",
    ],
    "lab5": [
        "Research YAML's tag syntax for constructing arbitrary Python objects / calling functions if it's new to you — this is a well-documented, named technique.",
        "You need a function that can run an arbitrary system command. There's more than one standard-library way to do that.",
        "The obvious first function name is blocked by a keyword filter. Try a different stdlib function that does the same thing (hint: subprocess, or the posix module).",
    ],
}

SECURITY_INFO = {
    "lab1": {
        "vulnerability": "Sensitive Information Disclosure / Weak Access Control",
        "cwe": "CWE-200 (Information Exposure), CWE-522 (Insufficiently Protected Credentials)",
        "severity": "Medium",
        "impact": "Full admin account takeover via leaked production credentials.",
        "root_cause": "Backup/config files containing real credentials were left reachable inside the web-servable directory. The only things standing in the way were obscurity (unlinked filenames) and HTTP Basic Auth credentials that were themselves exposed client-side — neither is real authorization.",
        "detection": "Recon: robots.txt review, directory/file enumeration, reading HTML source and file comments carefully.",
        "remediation": "Never leave backups, config files, or credentials inside a web-servable directory — rotate AND delete, don't just rename. Don't rely on obscurity or embed credentials (even 'read-only' ones) in client-visible source. Enforce real server-side authorization.",
    },
    "lab2": {
        "vulnerability": "SQL Injection (Authentication Bypass) + Account Enumeration",
        "cwe": "CWE-89 (SQL Injection), CWE-204 (Observable Response Discrepancy)",
        "severity": "High",
        "impact": "Complete authentication bypass — full admin access without any valid credential.",
        "root_cause": "User input is concatenated directly into a SQL query string instead of being parameterized, and a secondary 'forgot password' feature reveals account existence through differing response text.",
        "detection": "Send a single quote and observe behavior changes; test comment-injection with various SQL comment styles; probe secondary account features for behavioral differences.",
        "remediation": "Use parameterized queries / prepared statements everywhere, never string-format user input into SQL. Give identical responses regardless of account existence. Hash passwords so injection alone can't compare against a known plaintext.",
    },
    "lab3": {
        "vulnerability": "Broken Access Control — Insecure Direct Object Reference (IDOR) via client-trusted identity",
        "cwe": "CWE-639 (Authorization Bypass Through User-Controlled Key), CWE-807 (Reliance on Untrusted Inputs in a Security Decision)",
        "severity": "High",
        "impact": "Any authenticated user can read any other user's (or internal ops') private records.",
        "root_cause": "The authorization check trusts a plain, client-editable cookie to determine 'who is asking' instead of relying solely on the signed, server-side session — so the identity used for the permission check can be forged by the client.",
        "detection": "Inspect cookies/local storage for anything that looks identity-related; try modifying it and requesting resources that shouldn't belong to you.",
        "remediation": "Never make authorization decisions based on client-controlled values (cookies, headers, hidden form fields) unless they're cryptographically signed and verified server-side. Authorization must be derived entirely from the trusted server-side session.",
    },
    "lab4": {
        "vulnerability": "Path Traversal (via incomplete sanitization)",
        "cwe": "CWE-22 (Path Traversal), CWE-697 (Incorrect Comparison / incomplete blacklist)",
        "severity": "High",
        "impact": "Read arbitrary files outside the intended public directory, including internal/confidential documents.",
        "root_cause": "The filter attempts to block '../' with a single non-recursive string replace, which can be defeated by input engineered to produce the blocked pattern only after the first pass runs.",
        "detection": "Test traversal payloads with varying dot/slash patterns; if a filter blocks the obvious pattern, test overlapping/nested variants.",
        "remediation": "Never sanitize paths via blacklist string replacement. Resolve the final path with os.path.realpath()/abspath() and verify it's still inside the intended base directory before use. Prefer opaque IDs over raw filenames entirely.",
    },
    "lab5": {
        "vulnerability": "Unsafe YAML Deserialization — Simulated RCE",
        "cwe": "CWE-502 (Deserialization of Untrusted Data)",
        "severity": "Critical",
        "impact": "In a real vulnerable app, this pattern leads to full remote code execution. This lab simulates the function-call step only — nothing here actually executes commands.",
        "root_cause": "yaml.load() with the full (non-safe) loader allows YAML tags to construct arbitrary Python objects and invoke functions with attacker-controlled arguments.",
        "detection": "Check whether YAML/pickle/similar deserialization is used on user-controlled input, and whether the 'safe' variant of the loader is actually being used.",
        "remediation": "Always use yaml.safe_load() for untrusted YAML. Never unpickle untrusted data. If custom types are genuinely needed, use an explicit allowlist of constructors rather than the full loader.",
    },
}
