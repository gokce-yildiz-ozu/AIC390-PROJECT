"""PostToolUse hook: format a Python file after Claude edits it.

Never blocks Claude: any problem (no ruff installed, bad input) exits 0 silently.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        path = Path(payload.get("tool_input", {}).get("file_path", ""))
    except (json.JSONDecodeError, AttributeError):
        return 0
    if path.suffix != ".py" or not path.is_file():
        return 0
    ruff = shutil.which("ruff")
    cmd = [ruff] if ruff else [sys.executable, "-m", "ruff"]
    try:
        subprocess.run([*cmd, "format", str(path)], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
