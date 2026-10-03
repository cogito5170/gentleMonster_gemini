"""gentleMonster_gemini -- gentleMonster on Gemini (default gemini-3-flash-preview; built and first measured on gemini-3.1-flash-lite).

The model fills narrow slots (pick one of the listed options, or write a few lines to a schema).
Plan, geometry, consistency and every pass/fail are code. Status comes only from the job ledger.
"""
import os

MODEL = "gemini-3-flash-preview"      # default since BD-212 (user decision); bench results before it are gemini-3.1-flash-lite
FLASH_LITE = "gemini-3.1-flash-lite"  # the model of every earlier bench number
CLI_PIN = "0.62.0"                    # the newest Gemini CLI that serves gemini-3-flash-preview unchanged (README, "Which model serves")


def asked_model() -> str:
    """The model this run asked for: the launcher exports GENTLEMONSTER_MODEL; GMG_MODEL is the harness override."""
    return os.environ.get("GENTLEMONSTER_MODEL") or os.environ.get("GMG_MODEL") or MODEL

VERSION = "0.4.0-preview"
