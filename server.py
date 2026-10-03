#!/usr/bin/env python3
"""Gemini CLI starts this: the gentlemonster MCP server (gmg.ext_mcp). Needs Python >= 3.9.

The extension's Python parts live in their own venv (USAGE.md: ~/.gentlemonster/venv). Gemini CLI starts `python3`;
when that venv exists and this is not it, the server re-starts itself under the venv's Python (GMG_VENV overrides
the folder, GMG_NO_REEXEC=1 turns this off)."""
import os
import sys
from pathlib import Path

VENV = Path(os.environ.get("GMG_VENV") or (Path.home() / ".gentlemonster" / "venv"))
PY = VENV / "bin" / "python3"
if PY.is_file() and Path(sys.prefix).resolve() != VENV.resolve() and not os.environ.get("GMG_NO_REEXEC"):
    os.execv(str(PY), [str(PY)] + sys.argv)
if sys.version_info < (3, 9):
    sys.stderr.write("gentlemonster needs Python 3.9 or newer\n")
    sys.exit(1)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gmg.ext_mcp import main  # noqa: E402

sys.exit(main())
