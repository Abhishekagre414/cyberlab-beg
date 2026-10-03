"""
Lab 3 — Peek at Anyone's Invoice (Insecure Direct Object Reference / IDOR)

v4: real broken authorization, not just "change the number in the URL."

Flow:
  Visit lab index -> server "logs you in" (sets a signed Flask session
  with your real user id) -> server ALSO sets a separate, plain,
  client-readable/editable cookie meant purely for display purposes
  ("so the UI can show your ID without hitting the session on every
  request", the kind of shortcut a real dev might take) -> the invoice
  route's authorization check uses THAT cookie instead of the trusted
  session to decide if you own the invoice you're requesting.

That's the vulnerability: authorization derived from a value the
client fully controls. Editing the cookie in DevTools (or curl -b) is
enough to impersonate any user id, regardless of what the real,
signed session says.
"""
from flask import Blueprint, render_template, request, session, make_response, abort

import progress

lab3_bp = Blueprint("lab3", __name__, template_folder="../templates/lab3")

FLAG_PART_1 = "CYBERLAB{an_id_in_the_url_"
FLAG_PART_2 = "is_not_a_permission_check}"
FULL_FLAG = FLAG_PART_1 + FLAG_PART_2

REAL_USER_ID = 4021  # your actual, authenticated identity (trusted, server-side)
DISPLAY_COOKIE = "x_client_user_id"  # NOT trusted -- but the vulnerable check trusts it anyway

INVOICES = {
    4014: {"owner": "sumit@trinetlayer.local", "amount": "$142.00", "note": "Consulting — March"},
    4021: {"owner": "abhishek@trinetlayer.local", "amount": "$89.00", "note": "Your subscription renewal"},
    4032: {"owner": "ayush@trinetlayer.local", "amount": "$204.50", "note": "Cloud infra — shared"},
    4055: {"owner": "sahil@trinetlayer.local", "amount": "$61.00", "note": "Reminder: flags are never stored on personal invoices, that would be silly"},
    4063: {"owner": "tejas@trinetlayer.local", "amount": "$310.00", "note": "Design tooling license"},
    4077: {"owner": "sayali@trinetlayer.local", "amount": "$45.00", "note": "Nice try, but this isn't it either — CYBERLAB{keep_looking_not_this_one}"},
    4090: {"owner": "ops-internal@trinetlayer.local", "amount": "$0.00", "note": f"Internal ops fragment (1 of 2) — keep looking for the other half: {FLAG_PART_1}"},
    4104: {"owner": "billing-archive@trinetlayer.local", "amount": "$0.00", "note": "Archived, nothing interesting, just old billing records from 2023"},
    4118: {"owner": "ops-internal@trinetlayer.local", "amount": "$0.00", "note": f"Internal ops fragment (2 of 2) — combine with the other half you found: {FLAG_PART_2}"},
    4133: {"owner": "sumit@trinetlayer.local", "amount": "$18.00", "note": "Coffee machine repair, don't ask"},
}


@lab3_bp.route("/")
def index():
    # Simulated login: real, trusted identity goes in the signed session.
    session["lab3_user_id"] = REAL_USER_ID

    ctx = progress.lab_context("lab3")
    resp = make_response(render_template("lab3/index.html", current_id=REAL_USER_ID, **ctx))
    # VULNERABLE ON PURPOSE: a plain, client-editable cookie, set with
    # good intentions ("let the frontend show the user's id without an
    # extra lookup") but about to be trusted somewhere it shouldn't be.
    resp.set_cookie(DISPLAY_COOKIE, str(REAL_USER_ID))
    return resp


@lab3_bp.route("/invoice/<int:invoice_id>")
def invoice(invoice_id):
    progress.mark_explored("lab3")
    data = INVOICES.get(invoice_id)
    if data is None:
        abort(404)

    # VULNERABLE AUTHORIZATION CHECK: uses the client-controlled cookie
    # instead of the trusted, signed session value. Looks like a real
    # check -- isn't one, because the client can set this cookie to
    # anything at all.
    claimed_id = request.cookies.get(DISPLAY_COOKIE, type=int)
    real_session_id = session.get("lab3_user_id")

    authorized = claimed_id is not None and claimed_id == invoice_id

    if not authorized:
        return render_template(
            "lab3/denied.html",
            invoice_id=invoice_id,
            claimed_id=claimed_id,
            real_session_id=real_session_id,
        ), 403

    is_own = invoice_id == real_session_id
    is_fragment = invoice_id in (4090, 4118)
    ctx = progress.lab_context("lab3")
    return render_template(
        "lab3/invoice.html",
        invoice_id=invoice_id,
        data=data,
        is_own=is_own,
        is_fragment=is_fragment,
        claimed_id=claimed_id,
        real_session_id=real_session_id,
        full_flag=FULL_FLAG,
        **ctx,
    )
