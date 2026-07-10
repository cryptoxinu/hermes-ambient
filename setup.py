#!/usr/bin/env python3
"""Point Hermes at Ambient inference, directly (no proxy).

Adds Ambient as a Hermes `custom_providers` entry in ~/.hermes/config.yaml,
pointed at https://api.ambient.xyz/v1. Hermes speaks the OpenAI API and fetches a
custom provider's `/v1/models`, so it then lists every Ambient model live -- no
hardcoded catalog. The API key is referenced by env var (`AMBIENT_API_KEY`), so
it is never written into the config file.

Safe by construction: backs up the config first, is idempotent (re-running does
nothing), writes atomically, and -- rather than risk corrupting a config it can't
cleanly edit -- prints the block to paste by hand. It only ever APPENDS a fresh
`custom_providers:` block when the file has none; if a block already exists (in
any form), it refuses and hands you the entry, so it can never create a duplicate
key or drop your other providers.

    python3 setup.py            # apply
    python3 setup.py --print    # just print the block, change nothing
"""
from __future__ import annotations

import os
import re
import stat
import sys
import tempfile
from pathlib import Path

BASE_URL = "https://api.ambient.xyz/v1"
PROVIDER_NAME = "Ambient"
DEFAULT_MODEL = "moonshotai/kimi-k2.7-code"
KEY_ENV = "AMBIENT_API_KEY"

ENTRY = f"""  - name: {PROVIDER_NAME}
    base_url: {BASE_URL}
    key_env: {KEY_ENV}
    model: {DEFAULT_MODEL}"""
BLOCK = f"custom_providers:\n{ENTRY}"

# A top-level `custom_providers:` key in any form: bare, trailing comment, inline
# list, or a quoted key. Anchored at column 0 (top-level), so a nested/commented
# occurrence does not match.
_CP_HEADER = re.compile(r"""^["']?custom_providers["']?\s*:""")
# A base_url line inside a sequence entry (`base_url: x` or `- base_url: x`).
_BASE_URL = re.compile(r"^-?\s*base_url\s*:\s*(.+?)\s*$")


def config_path() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes")) / "config.yaml"


def points_at_ambient(text: str) -> bool:
    """True if some entry's base_url already points at Ambient (quote/comment aware)."""
    want = BASE_URL.rstrip("/").lower()
    for line in text.splitlines():
        m = _BASE_URL.match(line.strip())
        if not m:
            continue
        val = m.group(1)
        hit = val.find(" #")            # drop an inline comment
        if hit != -1:
            val = val[:hit]
        val = val.strip().strip("'\"").rstrip("/").lower()
        if val == want:
            return True
    return False


def has_custom_providers(text: str) -> bool:
    return any(_CP_HEADER.match(line) for line in text.splitlines())


def _atomic_write(path: Path, data: str, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".ambient-", suffix=".tmp")
    try:
        os.chmod(tmp, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:  # keep CRLF/LF verbatim
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))     # atomic; swaps a symlink at `path` by name
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def paste_hint(block: str, cfg: Path | None = None) -> None:
    where = f"{cfg} " if cfg else "~/.hermes/config.yaml "
    print(f"Add this to {where}by hand (as a top-level key):\n")
    print(block)
    print(f"\nThen set your key:  export {KEY_ENV}=<your Ambient API key>")
    print('Run `hermes`, open /model, and pick a model under "Ambient".')


def main() -> int:
    if "--print" in sys.argv[1:]:
        paste_hint(BLOCK)
        return 0

    cfg = config_path()
    if not cfg.exists():
        print(f"No Hermes config at {cfg}. Install Hermes and run it once first.\n")
        paste_hint(BLOCK)
        return 1

    with open(cfg, "r", encoding="utf-8", newline="") as f:  # preserve line endings
        original = f.read()

    if points_at_ambient(original):
        print(f"Ambient is already configured in {cfg} -- nothing to do.")
        return 0

    if has_custom_providers(original):
        # We only auto-append when there is NO custom_providers block. Editing an
        # existing one as text risks a duplicate key / dropped providers, so hand
        # the single entry to the user to slot into their block.
        print(f"Your Hermes config already has a `custom_providers:` block.")
        print("Add this entry under it (indent to match your other entries):\n")
        print(ENTRY)
        print(f"\nThen set your key:  export {KEY_ENV}=<your Ambient API key>")
        return 0

    nl = "\r\n" if "\r\n" in original else "\n"
    sep = "" if (not original or original.endswith("\n")) else nl
    body = sep + nl.join(BLOCK.splitlines()) + nl
    mode = stat.S_IMODE(os.stat(cfg).st_mode)                # follow a symlink to its mode
    _atomic_write(cfg.with_suffix(".yaml.bak"), original, mode)
    _atomic_write(cfg, original + body, mode)

    print(f"Added Ambient to {cfg}  (backup: {cfg.with_suffix('.yaml.bak')})")
    if not os.environ.get(KEY_ENV):
        print(f"\nSet your key:  export {KEY_ENV}=<your Ambient API key>")
    print('Run `hermes`, open /model, and pick a model under "Ambient".')
    print("(Hermes auto-discovers the full model list from Ambient's /v1/models.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
