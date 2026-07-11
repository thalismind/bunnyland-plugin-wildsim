from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER_SRC = ROOT / "server" / "src"
BUNNYLAND_SERVER_SRC = ROOT.parent / "bunnyland-server" / "src"
BUNNYLAND_3D_SRC = ROOT.parent / "bunnyland-3d" / "server" / "src"

for path in (SERVER_SRC, BUNNYLAND_SERVER_SRC, BUNNYLAND_3D_SRC):
    if path.exists():
        sys.path.insert(0, str(path))
