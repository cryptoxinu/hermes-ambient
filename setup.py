#!/usr/bin/env python3
"""Point Hermes at Ambient inference, directly (no proxy).

Adds Ambient as a Hermes `custom_providers` entry in ~/.hermes/config.yaml,
pointed at https://api.ambient.xyz/v1. Hermes speaks the OpenAI API and fetches a
custom provider's `/v1/models`, so it then lists every Ambient model live -- no
hardcoded catalog. The API key is referenced by env var (`AMBIENT_API_KEY`), so
it is never written into the config file.

Safe by construction: backs up the config first, is idempotent (re-running does
nothing), writes atomically, and -- rather than risk corrupting a config it can't
cleanly edit -- prints the block to paste by hand.

    python3 setup.py            # apply
    python3 setup.py --print    # just print the block, change nothing
"""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

BASE_URL = "https://api.ambient.xyz/v1"
PROVIDER_NAME = "Ambient"
DEFAULT_MODEL = "moonshotai/kimi-k2.7-code"
KEY_ENV = "AMBIENT_API_KEY"

BLOCK = f"""custom_providers:
  - name: {PROVIDER_NAME}
    base_url: {BASE_URL}
    key_env: {KEY_ENV}
    model: {DEFAULT_MODEL}
"""


def config_path() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")) / "config.yaml"


def already_configured(text: str) -> bool:
    """True if some custom_providers entry already points at Ambient."""
    want = BASE_URL.rstrip("/").lower()
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("base_url:"):
            val = s.split(":", 1)[1].strip().strip("'\"").rstrip("/").lower()
            if val == want:
                return True
    return False


def _atomic_write(path: Path, data: str, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ambient-", suffix=".tmp")
    try:
        os.chmod(tmp, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def manual_hint() -> None:
    print("Add this to ~/.hermes/config.yaml yourself (top-level key):\n")
    print(BLOCK)
    print(f"Then set your key:  export {KEY_ENV}=<your Ambient API key>")
    print("Run `hermes`, open /model, and pick a model under \"Ambient\".")


def main() -> int:
    if "--print" in sys.argv[1:]:
        manual_hint()
        return 0

    cfg = config_path()
    if not cfg.exists():
        print(f"No Hermes config at {cfg}. Install Hermes and run it once first.\n")
        manual_hint()
        return 1

    # newline="" preserves the file's existing CRLF/LF verbatim.
    with open(cfg, "r", encoding="utf-8", newline="") as f:
        original = f.read()

    if already_configured(original):
        print(f"Ambient is already configured in {cfg} -- nothing to do.")
        return 0

    lines = original.splitlines()
    has_block = any(ln.rstrip() == "custom_providers:" for ln in lines)
    if has_block:
        # We only safely edit a plain `custom_providers:` block. Anything else
        # (an inline list, a quoted key) -> hand it to the user rather than risk it.
        print("Your config already has a `custom_providers:` block. To avoid")
        print("corrupting it, add the entry by hand:\n")
        print("  - name: {}\n    base_url: {}\n    key_env: {}\n    model: {}\n".format(
            PROVIDER_NAME, BASE_URL, KEY_ENV, DEFAULT_MODEL))
        return 0

    # Append a fresh block. Preserve the source file's permissions.
    nl = "\r\n" if "\r\n" in original else "\n"
    sep = "" if (not original or original.endswith("\n")) else nl
    body = sep + nl.join(BLOCK.splitlines()) + nl
    mode = stat.S_IMODE(os.stat(cfg).st_mode)
    _atomic_write(cfg.with_suffix(".yaml.bak"), original, mode)
    _atomic_write(cfg, original + body, mode)

    print(f"Added Ambient to {cfg}  (backup: {cfg.with_suffix('.yaml.bak')})")
    if not os.environ.get(KEY_ENV):
        print(f"\nSet your key:  export {KEY_ENV}=<your Ambient API key>")
    print("Run `hermes`, open /model, and pick a model under \"Ambient\".")
    print("(Hermes auto-discovers the full model list from Ambient's /v1/models.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
