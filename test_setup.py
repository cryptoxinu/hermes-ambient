#!/usr/bin/env python3
"""Tests for setup.py. Stdlib only:  python3 test_setup.py

The one invariant that matters: setup must NEVER corrupt a config or drop a
provider. It may only cleanly append a fresh block, or refuse and hand the user
the entry.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import setup  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None

_fail = 0


def check(name, ok):
    global _fail
    print(("  ok   " if ok else "  FAIL ") + name)
    if not ok:
        _fail += 1


def run(config_text):
    """Run setup.py against a temp config; return (exit, new_text, backup_exists)."""
    d = tempfile.mkdtemp()
    home = Path(d) / ".hermes"
    home.mkdir()
    cfg = home / "config.yaml"
    cfg.write_bytes(config_text.encode() if isinstance(config_text, str) else config_text)
    env = {**os.environ, "HERMES_HOME": str(home)}
    r = subprocess.run([sys.executable, str(HERE / "setup.py")], env=env,
                       capture_output=True, text=True)
    # read raw (no universal-newline translation) so a CRLF check is accurate
    return r.returncode, cfg.read_bytes().decode("utf-8"), (home / "config.yaml.bak").exists()


# --- pure predicates -------------------------------------------------------
print("points_at_ambient:")
check("plain base_url", setup.points_at_ambient("    base_url: https://api.ambient.xyz/v1"))
check("- base_url form", setup.points_at_ambient("  - base_url: https://api.ambient.xyz/v1"))
check("trailing slash", setup.points_at_ambient("    base_url: https://api.ambient.xyz/v1/"))
check("quoted + comment", setup.points_at_ambient('    base_url: "https://api.ambient.xyz/v1"  # x'))
check("other provider is not ambient", not setup.points_at_ambient("    base_url: http://localhost:11434/v1"))
check("a commented-out base_url does not count", not setup.points_at_ambient("    # base_url: https://api.ambient.xyz/v1"))

print("has_custom_providers (must catch EVERY header form -> never append a duplicate):")
check("bare", setup.has_custom_providers("custom_providers:\n  - name: x"))
check("trailing comment", setup.has_custom_providers("custom_providers:  # mine\n  - name: x"))
check("inline empty", setup.has_custom_providers("custom_providers: []"))
check("spaced colon", setup.has_custom_providers("custom_providers :\n"))
check("quoted key", setup.has_custom_providers('"custom_providers":\n'))
check("absent", not setup.has_custom_providers("model:\n  default: gpt-4\n"))
check("nested/indented is not a top-level key", not setup.has_custom_providers("  custom_providers:\n"))

# --- end-to-end ------------------------------------------------------------
print("append onto a fresh config:")
code, out, bak = run("model:\n  default: gpt-4\nterminal:\n  backend: local\n")
check("exit 0", code == 0)
check("backup made", bak)
if yaml:
    d = yaml.safe_load(out)
    check("parses", isinstance(d, dict))
    check("Ambient added", any(c.get("name") == "Ambient" for c in (d.get("custom_providers") or [])))
    check("key is an env ref, not written", (d["custom_providers"][0].get("key_env") == "AMBIENT_API_KEY"
                                             and "api_key" not in d["custom_providers"][0]))
    check("other keys preserved", "terminal" in d and "model" in d)

print("idempotent re-run:")
seeded = run("model:\n  default: gpt-4\n")[1]
code2, out2, _ = run(seeded)
if yaml:
    check("still exactly one Ambient", sum(
        1 for c in (yaml.safe_load(out2).get("custom_providers") or []) if c.get("name") == "Ambient") == 1)

print("REFUSES to touch an existing custom_providers block (no data loss):")
existing = "model:\n  default: gpt-4\ncustom_providers:  # mine\n  - name: Ollama\n    base_url: http://localhost:11434/v1\n"
code3, out3, _ = run(existing)
check("config unchanged", out3 == existing)
if yaml:
    check("Ollama survives", any(c.get("name") == "Ollama" for c in (yaml.safe_load(out3).get("custom_providers") or [])))
check("only one custom_providers key", out3.count("custom_providers:") == 1)

print("CRLF preserved:")
code4, out4, _ = run("model:\r\n  default: gpt-4\r\n")
check("still CRLF, no bare LF introduced", "\r\n" in out4 and "\n" not in out4.replace("\r\n", ""))

print("no trailing newline on the original:")
code5, out5, _ = run("model:\n  default: gpt-4")
if yaml:
    check("parses + Ambient present", any(
        c.get("name") == "Ambient" for c in (yaml.safe_load(out5).get("custom_providers") or [])))

print(f"\n{'ALL PASS' if _fail == 0 else str(_fail) + ' FAILED'}")
sys.exit(1 if _fail else 0)
