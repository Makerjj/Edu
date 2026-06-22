#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
REMOTION_BIN = WORKSPACE_ROOT / "node_modules" / ".bin" / "remotion"
CHROME_BIN = (
    WORKSPACE_ROOT
    / "node_modules"
    / ".remotion"
    / "chrome-headless-shell"
    / "mac-arm64"
    / "chrome-headless-shell-mac-arm64"
    / "chrome-headless-shell"
)


def main():
    if not REMOTION_BIN.exists():
        raise SystemExit("Shared Remotion dependency is missing. Run `npm install` from `pre_lesson`.")
    if not CHROME_BIN.exists():
        raise SystemExit(
            "Shared Remotion browser is missing. Run `npm exec -- remotion browser ensure` from `pre_lesson`."
        )

    args = [str(REMOTION_BIN), *sys.argv[1:]]
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in {"render", "still", "compositions", "preview", "studio"}:
        args.extend(["--browser-executable", str(CHROME_BIN)])
    subprocess.run(args, check=True)


if __name__ == "__main__":
    main()
