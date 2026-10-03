#!/usr/bin/env python3
"""Gemini CLI AfterAgent hook -> gmg.hook (the answer may only state the ledger's verdict)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gmg.hook import main  # noqa: E402

sys.exit(main())
