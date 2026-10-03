"""gentleMonster inside Antigravity CLI (`agy`, CMD-GMG7): the same MCP servers and instructions, no fork.

agy signs in with the user's Google account; it has no API-key auth. So no Gemini API quota is spent.

**Verified** in the agy repo's CHANGELOG (google-antigravity/antigravity-cli):
- `.agents/` customizations: skills, rules, hooks.json, agents;
- `mcp_config.json` with stdio servers;
- `--model <slug>`, with the list from `agy models --output-format json`;
- `-p` with `--output-format json|stream-json`;
- `-p "/usage"` / `"/quota"`, which spend no quota.

**Assumptions**, until a run on the Mac checks them:
- the workspace file `.agents/mcp_config.json` with `mcpServers.{name}.{command,args,env}`;
- rules read from `.agents/rules/*.md`;
- the JSON shapes parsed below.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WANTED = "gemini-3-flash-preview"
RULE = "gentlemonster.md"


def ext_dir() -> Path:
    """The extension checkout that holds server.py and GEMINI.md: GENTLEMONSTER_EXT, else ~/.gentlemonster/ext (the agy
    install), else this package's own checkout."""
    import os
    for d in (os.environ.get("GENTLEMONSTER_EXT"), Path.home() / ".gentlemonster" / "ext", Path(__file__).resolve().parent.parent):
        if d and (Path(d) / "server.py").is_file() and (Path(d) / "GEMINI.md").is_file():
            return Path(d)
    raise FileNotFoundError("the gentleMonster extension checkout (server.py, GEMINI.md) was not found; set GENTLEMONSTER_EXT")


def files(workspace: Path, python: str, ext: "Path | None" = None) -> "dict[str, str]":
    """The workspace files agy reads: MCP servers (the extension's own server.py, one per tool group) and the rules."""
    ext = Path(ext or ext_dir())
    env = {"GENTLEMONSTER_HOST": "agy"}
    servers = {name: {"command": python, "args": [str(ext / "server.py"), "--tools", group], "env": env}
               for name, group in (("gentlemonster", "store"), ("gentlemonster-portfolio", "portfolio"))}
    rules = (ext / "GEMINI.md").read_text(encoding="utf-8")
    rules += ("\n## In Antigravity CLI\nThe tools above come from the `gentlemonster` and `gentlemonster-portfolio` MCP servers of this "
              "workspace. Use them for every gentleMonster task; do not write the files they write yourself.\n")
    return {".agents/mcp_config.json": json.dumps({"mcpServers": servers}, indent=2) + "\n",
            f".agents/rules/{RULE}": rules}


def setup(workspace, python: str, ext=None) -> "list[str]":
    """Write the workspace files when they differ (rerun-safe). Returns the paths changed."""
    workspace = Path(workspace)
    changed = []
    for rel, text in files(workspace, python, ext).items():
        p = workspace / rel
        if p.is_file() and p.read_text(encoding="utf-8") == text:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        changed.append(rel)
    return changed


def _strings(x, keys=("slug", "id", "name", "model", "label", "display_name", "displayName")) -> "list[str]":
    out = []
    if isinstance(x, dict):
        for k, v in x.items():
            if k in keys and isinstance(v, str):
                out.append(v)
            out += _strings(v, keys)
    elif isinstance(x, list):
        for v in x:
            out += _strings(v, keys)
    elif isinstance(x, str):
        out.append(x)
    return out


def _load(text: str):
    """JSON or JSON lines; anything else is read as one name per line."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    rows = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            rows.append(ln.split("\t")[0].split()[0])
    return rows


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", (s or "").lower()).strip("-")


def is_flash_3(name: str) -> bool:
    """gemini-3-flash(-preview) / "Gemini 3 Flash", not 3.x (3.5, 3.8 ...) and not flash-lite."""
    n = _norm(name)
    return bool(re.search(r"(^|-)gemini-3-flash(-preview)?($|-)", n)) and "lite" not in n


def pick_model(models_text: str) -> "tuple[str | None, list[str]]":
    """agy's own slug for gemini-3-flash-preview, if it offers one; and every name it offers."""
    names = list(dict.fromkeys(s for s in _strings(_load(models_text)) if s and len(s) < 80))
    hits = [s for s in names if is_flash_3(s)]
    slug = next((s for s in hits if " " not in s), hits[0] if hits else None)
    return slug, names


def served_models(output: str) -> "list[str]":
    """Models named in an agy `-p --output-format json|stream-json` output (shape assumed; any `model` key, str or object)."""
    found = []

    def walk(x):
        if isinstance(x, dict):
            m = x.get("model")
            if isinstance(m, str):
                found.append(m)
            elif isinstance(m, dict):
                v = next((m[k] for k in ("id", "slug", "name", "display_name", "displayName") if isinstance(m.get(k), str)), None)
                if v:
                    found.append(v)
            for k, v in x.items():
                if k != "model":
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(_load(output))
    return found


def same_model(asked: str, served: str) -> bool:
    a, s = _norm(asked), _norm(served)
    return bool(a and s) and (a in s or s in a or (is_flash_3(a) and is_flash_3(s)))


def tools_called(output: str) -> "list[str]":
    """gentleMonster tool names that appear in the output (gm_* / pf_*)."""
    return sorted(set(re.findall(r"(?<![a-z0-9])((?:gm|pf)_[a-z]+)(?![a-z0-9])", output or "")))


def main_model() -> int:
    """`gmg agy-model`: stdin = `agy models --output-format json`; prints the slug, or stops with the choice for the user."""
    slug, names = pick_model(sys.stdin.read())
    if slug:
        print(slug)
        return 0
    sys.stderr.write(f"gentlemonster-agy: agy offers no {WANTED}; it offers: {', '.join(names) or '(nothing listed)'} -- "
                     "choosing one is your decision: export GENTLEMONSTER_AGY_MODEL= followed by one of them, then run again\n")
    return 2


def main_served() -> int:
    """`gmg agy-served`: stdin = an agy -p --output-format json run; records and prints the served model."""
    from gmg import asked_model, served
    out = sys.stdin.read()
    models = served_models(out)
    called = tools_called(out)
    asked = asked_model()
    denied = "denied_actions" in out and not re.search(r'"denied_actions"\s*:\s*(\[\s*\]|null)', out)
    hint = (" -- agy refused the tool call (permission): run gentlemonster-agy, allow the gentlemonster tools once, then --check again"
            if denied else "")
    if not models:
        print(f"served model: unknown (not in agy's output) -- asked {asked}; gentleMonster tools called: {', '.join(called) or 'none'}{hint}")
        return 1
    served.record(models[-1], "agy", same=same_model(asked, models[-1]))
    ok = same_model(asked, models[-1])
    print(f"served model: {models[-1]} ({'as asked' if ok else 'NOT ' + asked}); gentleMonster tools called: {', '.join(called) or 'none'}{hint}")
    return 0 if ok and called and not denied else 1
