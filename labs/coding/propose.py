"""Send two synthetic files; save text only. Never execute model output."""
import json
import sys
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
context = "\n\n".join(
    name + "\n" + (ROOT / name).read_text(encoding="utf-8")
    for name in ["retention.py", "test_retention.py"]
)
tests = subprocess.run(
    [sys.executable, "-m", "unittest", "-v"], cwd=ROOT,
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    timeout=30,
)
test_output = tests.stdout + tests.stderr
(ROOT / "baseline-tests.txt").write_text(test_output, encoding="utf-8")
if tests.returncode != 1 or "FAILED" not in test_output:
    raise SystemExit("Expected the deliberately failing baseline; inspect tests.")
prompt = (
    "Repair the supplied Python function so its existing tests pass. "
    "Policy: snapshots whose age is at most keep_days are kept. "
    "Only strictly older snapshots are candidates, and only after restore verification. "
    "Keep the type/value validation and the unverified early return. "
    "Fix the boundary bug; do not change the tests. "
    "Return only the complete corrected expired_names function in a Python code block. "
    "No explanation or other files. You are proposing text, not executing it.\n"
    + context + "\n\nACTUAL BASELINE TEST OUTPUT:\n" + test_output
)

body = {
    "model": MODEL, "stream": False, "think": False,
    "messages": [{"role": "user", "content": prompt}],
    "options": {
        "temperature": 0, "seed": 7, "num_ctx": 4096,
        "num_predict": 512,
    },
    "keep_alive": "2m",
}
out = ROOT / "proposal.json"
if out.exists():
    raise SystemExit("Preserve proposal.json or choose a new run folder.")
(ROOT / "request.json").write_text(json.dumps(body, indent=2), "utf-8")
request = Request(
    "http://127.0.0.1:11434/api/chat",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    with urlopen(request, timeout=120) as response:
        reply = json.load(response)
except (HTTPError, URLError) as exc:
    error = {"error": str(exc)}
    if isinstance(exc, HTTPError):
        error.update(status=exc.code, body=exc.read().decode(errors="replace"))
    out.write_text(json.dumps(error, indent=2), encoding="utf-8")
    raise
out.write_text(json.dumps(reply, indent=2), encoding="utf-8")
print(reply["message"]["content"])
