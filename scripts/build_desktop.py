from __future__ import annotations

import os
import subprocess
import sys


SEP = ";" if os.name == "nt" else ":"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "ResumeAdjuster",
        "--onefile",
        "--console",
        "--collect-all",
        "weasyprint",
        "--add-data",
        f"app/templates{SEP}app/templates",
        "--add-data",
        f"app/static{SEP}app/static",
        "desktop_launcher.py",
    ]

    print("Running:")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    print("Build complete. Output binary is in dist/ResumeAdjuster")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
