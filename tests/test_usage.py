"""CMD-GMG6 S2: the real-use log and `gmg export` -- turns and tool path kept; no image bytes, no paths, no keys."""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="gmg_usage_"))
os.environ["GMG_OUT"] = str(TMP / "out")
os.environ.setdefault("GMG_UPSTREAM", str(Path.home() / "gentleMonster"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from gmg import cli, ext_mcp, turn, upstream, usage  # noqa: E402

upstream.load()
FAIL = []


def ok(c, what):
    print(("  ok  " if c else "  FAIL ") + what)
    if not c:
        FAIL.append(what)


def call(name, args):
    r = ext_mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
    return json.loads(r["result"]["content"][0]["text"])


pics = TMP / "Users" / "someone" / "Pictures"
pics.mkdir(parents=True)
img = pics / "street.jpg"
Image.fromarray((np.random.default_rng(1).random((60, 80, 3)) * 255).astype("uint8")).save(img)
sha = hashlib.sha256(img.read_bytes()).hexdigest()
FAKE_KEY = "AIza" + "x" * 35
doc = pics / "notes.txt"
doc.write_text("private notes")

turn.record(f"이 사진으로 SECTOR A를 써라 @{img} 그리고 key {FAKE_KEY}", session="sess-1")
o = call("pf_photos", {"paths": [str(img)]})
ok(o["ok"], "a tool call in the session works as before")
call("pf_write", {"kind": "nonsense", "items": [{"text": f"see {doc} and https://example.com/a/b"}]})
pr = subprocess.run([sys.executable, str(ROOT / "hooks" / "verdict_gate.py")], input=json.dumps({"prompt_response": f"done, saved in {pics}/out.pdf"}),
                    capture_output=True, text=True, env=dict(os.environ), cwd=str(ROOT))
ok(pr.returncode == 0, "the AfterAgent hook still runs and logs")
turn.record("다시 시도", session="sess-1")
o = call("pf_write", {"kind": "answer", "register": "direct", "language": "ko", "items": [{"text": "몸에 맞는 옷."}]})
ok(o["ok"] is False and o["next"][0]["tool"] == "pf_choose", "a redirect happens as before")
turn.record("두 번째 세션", session="sess-2")
pr = subprocess.run([sys.executable, str(ROOT / "hooks" / "turn_note.py")], input=json.dumps({"prompt": "세 번째", "session_id": "sess-2"}),
                    capture_output=True, text=True, env=dict(os.environ), cwd=str(ROOT))
ok(any(r["kind"] == "turn" and r.get("prompt") == "세 번째" and r["session"] == "sess-2" for r in usage.read()),
   "the BeforeAgent hook logs the turn with the CLI's session id")

recs = usage.read()
ok({r["kind"] for r in recs} >= {"turn", "call", "gate"}, f"turns, tool calls and the gate are logged ({sorted({r['kind'] for r in recs})})")
ok(all(r["session"] in ("sess-1", "sess-2") for r in recs), "every record carries the CLI's session id")

dest = TMP / "export"
buf = io.StringIO()
with redirect_stdout(buf):
    rc = cli.main(["export", "--out", str(dest)])
files = sorted(dest.glob("*.jsonl"))
ok(rc == 0 and len(files) == 2 and "gm-photos" in buf.getvalue(), "gmg export: one file per session, and where to share it")
raw = "\n".join(f.read_text() for f in files)
ok(str(TMP) not in raw and "someone" not in raw and str(Path.home()) not in raw, "no file path survives the export")
ok("AIza" not in raw, "no key survives the export")
ok("https://example.com/a/b" in raw, "a URL is not mistaken for a path")
lines = {f: [json.loads(x) for x in f.read_text().splitlines()] for f in files}
s1 = next(v for v in lines.values() if v[1]["text"].startswith("이 사진"))
head, t1, t2 = s1
ok(head["schema"] == "gmg-usage/1" and head["version"].endswith("preview") and "sess-1" not in raw, "header: schema, preview version, session id hashed")
ok([i["sha256"] for i in head["images"]] == [sha] and "brightness" in head["images"][0]["measured"],
   "the image is listed by sha256 with measured values")
ok(not any(k in json.dumps(head["images"]) for k in ("data", "base64")) and all(len(x) < 5000 for x in raw.splitlines()), "no image bytes")
ok("이 사진으로 SECTOR A를 써라" in t1["text"] and f"[image sha256:{sha[:16]}]" in t1["text"], "the user's words are kept; the image is named by its hash")
ok(t1["path"] == ["pf_photos", "pf_write"] and t1["reasks"] == 1 and t1["failures"], "tool path, re-asks and failures are kept")
ok("[file sha256:" in json.dumps(t1["calls"], ensure_ascii=False), "a non-image file in an argument becomes its hash")
ok(t1["gates"] == ["pass"] and "[path]" in (t1["answer"] or "") and str(pics) not in (t1["answer"] or ""), "the gate and the answer are kept, paths removed")
ok(t2["text"] == "다시 시도" and t2["redirects"] == 1 and t2["reasks"] == 0, "a redirect is counted apart from re-asks")
ok(usage.Cleaner().text("see " + "QUJD" * 75) == "see [bytes removed]", "a long encoded blob is removed")
ok(usage.Cleaner().text("token: abcdefghijk123") == "***", "a key=value secret is removed")
usage.log("call", session="s", tool=object())
ok(True, "logging an odd value does not raise")
(TMP / "out" / "usage.jsonl").unlink()
ok(usage.export(TMP / "none") == [], "nothing logged -> nothing written")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("all passed" if not FAIL else f"{len(FAIL)} failed"))
sys.exit(1 if FAIL else 0)
