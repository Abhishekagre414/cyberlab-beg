"""Optional per-user ("dynamic") flags.

A stored flag may contain the token ``{{TAG}}``. Each learner gets their own
tag, derived from the server secret, the user and the lab, so a flag shared
on Discord is worthless to anyone else. The same tag is handed to the lab
container as the ``LAB_FLAG_TAG`` environment variable so the lab can build
the identical flag, e.g. ``FLAG{sqli_{{TAG}}}`` -> ``FLAG{sqli_3fa91c0b7d22}``.
Flags without the token behave exactly as before.
"""
import hashlib
import hmac

TOKEN = '{{TAG}}'


def user_flag_tag(secret_key, user_id, lab_id):
    msg = f'flag-tag:{user_id}:{lab_id}'.encode('utf-8')
    return hmac.new(str(secret_key).encode('utf-8'), msg, hashlib.sha256).hexdigest()[:12]


def expand_flag(template, tag):
    return (template or '').replace(TOKEN, tag)
