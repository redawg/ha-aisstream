#!/usr/bin/env python3
"""Load .deploy.env then run configure."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

env_file = Path(__file__).resolve().parent.parent / ".deploy.env"
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

raise SystemExit(
    subprocess.call([sys.executable, str(Path(__file__).with_name("configure_ha.py"))])
)
