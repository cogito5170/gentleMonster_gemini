"""The pinned gentleMonster checkout. We wrap it; we never copy or edit it.

Where it is: $GMG_UPSTREAM (an existing checkout), else ~/.cache/gentleMonster_gemini/<commit> (made by `gmg setup`).
Either way HEAD must be the commit in lock.json -- a checkout at any other commit is refused, not used.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

LOCK = json.loads((Path(__file__).with_name("lock.json")).read_text())
CACHE = Path(os.environ.get("GMG_HOME") or (Path.home() / ".cache" / "gentleMonster_gemini"))


class NotReady(RuntimeError):
    pass


def root() -> Path:
    return Path(os.environ["GMG_UPSTREAM"]) if os.environ.get("GMG_UPSTREAM") else CACHE / LOCK["commit"]


def _git(*a, cwd=None) -> str:
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def head(r: Path) -> str:
    try:
        return _git("rev-parse", "HEAD", cwd=r)
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return ""


def setup(log=print) -> Path:
    """Fetch the pinned commit into the cache (or check $GMG_UPSTREAM). Refuses a dirty or moved checkout."""
    r = root()
    if not (r / ".git").exists():
        if os.environ.get("GMG_UPSTREAM"):
            raise NotReady(f"GMG_UPSTREAM={r} is not a git checkout")
        r.parent.mkdir(parents=True, exist_ok=True)
        log(f"[setup] cloning {LOCK['url']} -> {r}")
        _git("clone", "--quiet", "--no-checkout", LOCK["url"], str(r))
        _git("checkout", "--quiet", LOCK["commit"], cwd=r)
    if head(r) != LOCK["commit"]:
        raise NotReady(f"{r} is at {head(r)[:12] or '?'}, not the pinned {LOCK['commit'][:12]}")
    if _git("status", "--porcelain", "--untracked-files=no", cwd=r):
        raise NotReady(f"{r} has local changes; the pinned code must be used as committed")
    log(f"[setup] gentleMonster @ {LOCK['commit'][:12]} ok ({r})")
    return r


def ready() -> Path:
    r = root()
    if head(r) != LOCK["commit"]:
        raise NotReady(f"gentleMonster is not at the pinned commit {LOCK['commit'][:12]} in {r} -- run `gmg setup`")
    return r


def load(out_dir: "str | None" = None):
    """Import the pinned gentle_monster package. Outputs go to out_dir (GENTLE_MONSTER_OUT), never into the checkout."""
    r = ready()
    os.environ["GENTLE_MONSTER_OUT"] = str(Path(out_dir or os.environ.get("GMG_OUT") or (Path.home() / "gentleMonster_gemini_out")).resolve())
    if str(r) not in sys.path:
        sys.path.insert(0, str(r))
    import gentle_monster.spec as spec          # noqa: E402
    import gentle_monster.paths as paths        # noqa: E402
    if Path(paths.REPO).resolve() != r.resolve():
        raise NotReady(f"gentle_monster was imported from {paths.REPO}, not the pinned checkout {r}")
    return spec, paths
