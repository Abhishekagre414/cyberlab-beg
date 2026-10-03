"""Vercel serverless entrypoint.

Vercel looks for a WSGI callable called `app` in this module. All the real
work (DB creation, seeding, sessions) is done lazily by CTFplatform/app.py on
the first request, so importing it here must stay side-effect free.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATFORM_DIR = os.path.join(ROOT, 'CTFplatform')

# Make `import app`, `import config`, `import routes...` resolve to CTFplatform/
sys.path.insert(0, PLATFORM_DIR)
# Templates/static are resolved relative to the app module; be explicit anyway.
os.chdir(PLATFORM_DIR)

from app import app  # noqa: E402  (Vercel picks up the `app` WSGI object)

__all__ = ["app"]
