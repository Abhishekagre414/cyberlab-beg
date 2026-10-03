"""
Lab 5 — The YAML That Ran Code (Insecure Deserialization)

Real-world inspiration: an app that accepts user-supplied YAML (e.g. a
"config upload" or "settings import" feature) and parses it with
`yaml.load()` using the full loader instead of `yaml.safe_load()`. The
full loader understands special tags that can construct arbitrary
Python objects and call functions -- which is exactly how a config
parser turns into remote code execution.

SAFETY DESIGN: this lab is 100% safe to run. It never calls the real
`yaml.load()` with the dangerous loader, and it never executes real
shell commands. Instead it uses a small custom loader that recognizes
the *shape* of the classic dangerous tags (the ones that would call
os.system / subprocess in a truly vulnerable app) and routes them to a
`simulate_command()` function that returns canned, fake output. You
get the real "aha" moment -- your YAML controlled what function got
called -- without any actual code execution risk.
"""
import yaml
from flask import Blueprint, render_template, request

import progress

lab5_bp = Blueprint("lab5", __name__, template_folder="../templates/lab5")

FLAG = "CYBERLAB{yaml_load_without_safe_is_a_loaded_gun}"

# Tags that a REAL vulnerable app (using yaml.load with the full Loader)
# would resolve into an actual function call. Here they're just labels
# we pattern-match on, mapped to a fake command simulator instead.
DANGEROUS_TAG_PREFIXES = (
    "tag:yaml.org,2002:python/object/apply:os.system",
    "tag:yaml.org,2002:python/object/apply:subprocess.check_output",
    "tag:yaml.org,2002:python/object/apply:subprocess.Popen",
    "tag:yaml.org,2002:python/object/apply:posix.system",
)


def simulate_command(cmd: str) -> str:
    """Fake command execution -- no real shell, no real filesystem access
    outside this function's own little script."""
    cmd_lower = (cmd or "").lower()
    if "flag" in cmd_lower and ("cat" in cmd_lower or "type" in cmd_lower or "read" in cmd_lower):
        return f"[simulated shell] {FLAG}"
    if "whoami" in cmd_lower:
        return "[simulated shell] app-service-account"
    if "id" in cmd_lower:
        return "[simulated shell] uid=999(app-service-account) gid=999(app)"
    if "ls" in cmd_lower or "dir" in cmd_lower:
        return "[simulated shell] config.yaml  flag.txt  app.py"
    return f"[simulated shell] (no output configured for: {cmd!r} — try something like 'cat flag.txt')"


class TrackingLoader(yaml.SafeLoader):
    """A loader that behaves like the SAFE loader for everything, except
    it also recognizes the dangerous tag *shapes* so we can show the
    student what would have happened, safely."""
    pass


def _make_dangerous_constructor():
    def constructor(loader, node):
        # node holds the args passed to the "function" being called.
        args = loader.construct_sequence(node) if isinstance(node, yaml.SequenceNode) else [loader.construct_scalar(node)]
        cmd = args[0] if args else ""
        return {"__simulated_call__": True, "command": cmd, "output": simulate_command(cmd)}
    return constructor


for prefix in DANGEROUS_TAG_PREFIXES:
    TrackingLoader.add_constructor(prefix, _make_dangerous_constructor())


def _find_simulated_call(node):
    """Walk the parsed YAML structure looking for our simulated-call
    marker, since it could appear nested inside a dict/list rather than
    at the top level."""
    if isinstance(node, dict):
        if node.get("__simulated_call__"):
            return node
        for v in node.values():
            hit = _find_simulated_call(v)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = _find_simulated_call(v)
            if hit is not None:
                return hit
    return None


@lab5_bp.route("/")
def index():
    ctx = progress.lab_context("lab5")
    return render_template("lab5/index.html", **ctx)


BLOCKED_SUBSTRING = "os.system"  # a naive keyword filter, easy to route around


@lab5_bp.route("/import", methods=["GET", "POST"])
def import_config():
    progress.mark_explored("lab5")
    result = None
    error = None
    raw_input = ""
    triggered_sim = False
    sim_output = None
    blocked_keyword = False

    if request.method == "POST":
        raw_input = request.form.get("yaml_input", "")
        if BLOCKED_SUBSTRING in raw_input.lower():
            blocked_keyword = True
        else:
            try:
                parsed = yaml.load(raw_input, Loader=TrackingLoader)
                result = parsed
                hit = _find_simulated_call(parsed)
                if hit is not None:
                    triggered_sim = True
                    sim_output = hit["output"]
            except yaml.YAMLError as e:
                error = f"YAML parse error: {e}"

    found_flag = bool(sim_output and FLAG in sim_output)

    return render_template(
        "lab5/import.html",
        raw_input=raw_input,
        result=result,
        error=error,
        blocked_keyword=blocked_keyword,
        triggered_sim=triggered_sim,
        sim_output=sim_output,
        found_flag=found_flag,
        flag=FLAG,
    )

