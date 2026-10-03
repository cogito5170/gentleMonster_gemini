#!/usr/bin/env python3
"""Gemini CLI starts this: the gentlemonster MCP server (gmg.ext_mcp). Needs Python >= 3.10."""
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.stderr.write("gentlemonster needs Python 3.10 or newer\n")
    sys.exit(1)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gmg.ext_mcp import main  # noqa: E402

sys.exit(main())
