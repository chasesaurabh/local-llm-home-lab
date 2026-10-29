"""L05 candidate harness. --plan is default. Real inference requires both execution flags.
Uses synthetic prompts only. No package installation, server configuration or service control.
Follow Chapter 26 and README.md before execution. This file is not a benchmark result.
"""
import argparse
import concurrent.futures
import ctypes
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
BASE_HOST, BASE_PORT = "127.0.0.1", 11434
NOTE = ("Use only this note. If the answer is absent, say Not specified. "
        "Note: The lab maintenance window is Sunday at 09:00. "
        "Backups are stored in the lab-backups folder. Question: ")
PACKET = [
    ("day", NOTE + "On what day is maintenance?", "Sunday"),
    ("folder", NOTE + "What folder stores the backups?", "lab-backups"),
    ("absent", NOTE + "What is the support phone number?", "Not specified"),
]
METRICS = ("total_duration", "load_duration", "prompt_eval_count",
           "prompt_eval_cached_count", "prompt_eval_duration", "eval_count",
           "eval_duration", "done_reason")

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def request_json(route, body=None, timeout=15):
    con = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=timeout)
    try:
        raw = None if body is None else json.dumps(body).encode()
        con.request("GET" if body is None else "POST", route, raw,
                    {} if raw is None else {"Content-Type": "application/json"})
        response = con.getresponse()
        payload = response.read(2_000_000)
        if response.status != 200:
            raise RuntimeError("HTTP " + str(response.status) + " at " + route)
        return json.loads(payload)
    finally:
        con.close()

def selected_ps():
    # No process command lines, environment variables, credentials or prompt content.
    value = request_json("/api/ps", timeout=3)
    keys = ("name", "model", "digest", "size", "size_vram", "context_length", "runner", "expires_at")
    return [{k: x.get(k) for k in keys} for x in value.get("models", [])]

def sample_host():
    record = {"utc": utc(), "monotonic_ns": time.perf_counter_ns()}
    if os.name == "nt":
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
        mem = Memory()
        mem.length = ctypes.sizeof(mem)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
            record["host_ram_total_bytes"] = mem.total
            record["host_ram_available_bytes"] = mem.available
        idle, kernel, user = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
        if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            record["cpu_ticks_100ns"] = {"idle": idle.value, "kernel_including_idle": kernel.value, "user": user.value}
    start = time.perf_counter_ns()
    try:
        r = subprocess.run([
            "nvidia-smi", "--query-gpu=index,name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5, check=False)
        record["gpu_query"] = {"return_code": r.returncode,
            "csv": r.stdout.strip() if r.returncode == 0 else None,
            "columns": ["index", "name", "driver_version", "total_MiB", "used_MiB", "free_MiB", "gpu_percent", "temperature_C", "power_W"]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        record["gpu_query"] = {"error_type": type(exc).__name__}
    record["gpu_query_duration_ms"] = (time.perf_counter_ns() - start) / 1e6
    try:
        record["runtime_models"] = selected_ps()
    except Exception as exc:
        record["runtime_query_error_type"] = type(exc).__name__
    record["sample_end_utc"] = utc()
    return record

def sampler(stop, path, interval):
    previous = None
    with path.open("x", encoding="utf-8") as stream:
        while not stop.is_set():
            t0 = time.perf_counter()
            record = sample_host()
            ticks = record.get("cpu_ticks_100ns")
            if ticks and previous:
                total = ticks["kernel_including_idle"] + ticks["user"] - previous["kernel_including_idle"] - previous["user"]
                idle = ticks["idle"] - previous["idle"]
                record["host_cpu_busy_percent_between_samples"] = 100 * (total - idle) / total if total > 0 else None
            previous = ticks
            stream.write(json.dumps(record) + "\n")
            stream.flush()
            stop.wait(max(0, interval - (time.perf_counter() - t0)))

def stream_one(model, prompt, request_id, timeout, barrier=None):
    if barrier:
        barrier.wait(timeout=15)
    begin = time.perf_counter_ns()
    record = {"id": request_id, "utc_start": utc(), "start_monotonic_ns": begin,
              "first_content_ms": None, "first_thinking_ms": None, "events": [],
              "status": "started", "output": ""}
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": True, "think": False, "keep_alive": "10m",
            "options": {"num_ctx": 2048, "num_predict": 96,
                        "num_thread": 4, "temperature": 0, "seed": 7}}
    record["request"] = body
    con = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=timeout)
    try:
        con.request("POST", "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
        response = con.getresponse()
        record["http_status"] = response.status
        record["headers_received_ms"] = (time.perf_counter_ns() - begin) / 1e6
        if response.status != 200:
            record["error_body"] = response.read(4096).decode("utf-8", errors="replace")
            raise RuntimeError("HTTP status " + str(response.status))
        while True:
            remaining = timeout - (time.perf_counter_ns() - begin) / 1e9
            if remaining <= 0:
                raise TimeoutError("request deadline exceeded")
            # HTTPResponse owns the socket after headers; adjust its read timeout too.
            response.fp.raw._sock.settimeout(remaining)
            line = response.readline(2_000_001)
            observed_ms = (time.perf_counter_ns() - begin) / 1e6
            if not line:
                raise RuntimeError("stream ended without done=true")
            if len(line) > 2_000_000:
                raise RuntimeError("oversized NDJSON event")
            if not line.strip():
                continue
            event = json.loads(line)
            record["events"].append({"observed_ms": observed_ms, "event": event})
            if event.get("error"):
                raise RuntimeError("server reported streaming error")
            message = event.get("message", {})
            content = message.get("content", "")
            thinking = message.get("thinking", "")
            if content and record["first_content_ms"] is None:
                record["first_content_ms"] = observed_ms
            if thinking and record["first_thinking_ms"] is None:
                record["first_thinking_ms"] = observed_ms
            record["output"] += content
            if event.get("done"):
                record["server_metrics"] = {key: event.get(key) for key in METRICS}
                record["status"] = "complete"
                break
    except Exception as exc:
        record["status"] = "error"
        record["error_type"] = type(exc).__name__
        record["error"] = str(exc)[:300]
    finally:
        con.close()
        end = time.perf_counter_ns()
        record["end_monotonic_ns"] = end
        record["client_total_ms"] = (end - begin) / 1e6
        record["utc_end"] = utc()
    return record

def unload_selected(model):
    request_json("/api/generate", {"model": model, "keep_alive": 0, "stream": False}, timeout=30)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        models = selected_ps()
        if all(x.get("name") != model and x.get("model") != model for x in models):
            return {"utc": utc(), "models": models, "selected_model_absent": True}
        time.sleep(0.25)
    raise RuntimeError("selected model still resident; cold condition unproven")

def fresh_dir(text, lab_root):
    root = Path(lab_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("--lab-root must be the existing reader lab directory")
    path = Path(text).expanduser().resolve()
    if root not in path.parents:
        raise ValueError("output must be a NEW strict descendant of the supplied --lab-root")
    if not path.parent.is_dir():
        raise ValueError("output parent must already exist; create your measurements directory first")
    if path.exists():
        raise ValueError("output already exists; never overwrite a run")
    path.mkdir(exist_ok=False)
    return path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["qwen3:0.6b", "qwen3:1.7b", "qwen3:4b-instruct-2507-q4_K_M"], default="qwen3:4b-instruct-2507-q4_K_M")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--exclusive-lab-window", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--lab-root", help="Existing reader lab directory; all run output must remain beneath it")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--warm-repeats", type=int, default=2)
    parser.add_argument("--concurrent", type=int, default=2)
    parser.add_argument("--concurrent-batches", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--sample-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if not (1 <= args.cycles <= 10 and 1 <= args.warm_repeats <= 10 and
            1 <= args.concurrent <= 2 and 1 <= args.concurrent_batches <= 10 and
            10 <= args.timeout <= 300 and 1 <= args.sample_seconds <= 10):
        parser.error("bounded run limits exceeded")
    if not args.execute or args.plan:
        print(json.dumps({"mode": "plan_only_no_queries", "model": args.model,
            "requests": args.cycles * (1 + args.warm_repeats) + args.concurrent * args.concurrent_batches + 3,
            "changes_when_executed": "unload only selected model, then inference; retain selected model for up to 10 minutes",
            "requires": "exclusive lab request window, existing --lab-root, and a new --output whose parent exists; other host workloads remain untouched"}, indent=2))
        return
    if not args.exclusive_lab_window or not args.output or not args.lab_root:
        parser.error("execution requires --exclusive-lab-window, --lab-root and a fresh --output")
    # Read-only checks occur before any unload or inference.
    version = request_json("/api/version")
    tags = request_json("/api/tags")
    selected = [x for x in tags.get("models", []) if x.get("name") == args.model]
    if len(selected) != 1:
        raise RuntimeError("selected model is not already installed; this harness never downloads")
    expected = {"qwen3:0.6b": "7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435",
                "qwen3:1.7b": "8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7",
                "qwen3:4b-instruct-2507-q4_K_M": "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"}
    if version.get("version") != "0.40.12" or selected[0].get("digest") != expected[args.model]:
        raise RuntimeError("runtime/model differs from locked lab evidence; review before changing expectations")
    before = selected_ps()
    if any(x.get("name") != args.model and x.get("model") != args.model for x in before):
        raise RuntimeError("another model is resident; coordinate, do not unload it here")
    out = fresh_dir(args.output, args.lab_root)
    manifest = {"status": "started", "utc": utc(), "arguments": vars(args), "runtime": version,
                "model": selected[0], "before": before,
                "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "limits": ["shared host", "no OS cache flush", "sampled maxima are not peaks",
                           "client concurrency does not establish server parallel inference",
                           "time to first content NDJSON event is not an exact tokenizer timestamp",
                           "bounded request/read deadline; client disconnect may not immediately cancel server work"]}
    write_json(out / "manifest.json", manifest)
    stop = threading.Event()
    worker = threading.Thread(target=sampler, args=(stop, out / "samples.jsonl", args.sample_seconds), daemon=True)
    worker.start()
    runs = []
    def save(record):
        try:
            record["runtime_after_request"] = selected_ps()
        except Exception as exc:
            record["runtime_after_request_error_type"] = type(exc).__name__
        runs.append(record)
        write_json(out / (record["id"] + ".json"), record)
        if record["status"] != "complete":
            raise RuntimeError("request failed; stop scheduling further work and inspect evidence")
    try:
        time.sleep(2)  # Two seconds of bounded baseline sampling; no hardware-idle claim.
        for cycle in range(1, args.cycles + 1):
            marker = unload_selected(args.model)
            write_json(out / ("unload-%02d.json" % cycle), marker)
            save(stream_one(args.model, PACKET[0][1], "cold-%02d" % cycle, args.timeout))
            for repeat in range(1, args.warm_repeats + 1):
                save(stream_one(args.model, PACKET[0][1], "repeat-%02d-%02d" % (cycle, repeat), args.timeout))
        for batch in range(1, args.concurrent_batches + 1):
            barrier = threading.Barrier(args.concurrent)
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrent) as pool:
                futures = [pool.submit(stream_one, args.model, PACKET[0][1],
                    "concurrent-%02d-%02d" % (batch, n), args.timeout, barrier)
                    for n in range(1, args.concurrent + 1)]
                results = [future.result() for future in futures]
            wall_seconds = (max(r["end_monotonic_ns"] for r in results) - min(r["start_monotonic_ns"] for r in results)) / 1e9
            counts = [r.get("server_metrics", {}).get("eval_count") for r in results]
            batch_metrics = {"client_window_seconds": wall_seconds, "requests": len(results),
                "sum_output_tokens": sum(counts) if all(isinstance(n, int) for n in counts) else None,
                "runtime_after_batch": selected_ps()}
            if batch_metrics["sum_output_tokens"] is not None and wall_seconds > 0:
                batch_metrics["aggregate_output_tokens_per_client_window_second"] = batch_metrics["sum_output_tokens"] / wall_seconds
            write_json(out / ("batch-%02d.json" % batch), batch_metrics)
            for result in results:
                write_json(out / (result["id"] + ".json"), result)
                runs.append(result)
            if any(r["status"] != "complete" for r in results):
                raise RuntimeError("bounded batch failed; no further batches scheduled")
        for name, prompt, expected_answer in PACKET:
            result = stream_one(args.model, prompt, "quality-" + name, args.timeout)
            result["expected_answer"] = expected_answer
            result["automatic_contains_hint_only"] = expected_answer.lower() in result["output"].lower()
            result["manual_quality_grade"] = "pending: factual correctness, unsupported additions, abstention, truncation"
            save(result)
        manifest["status"] = "measurement_complete_quality_review_pending"
    except Exception as exc:
        manifest["status"] = "incomplete"
        manifest["failure_type"] = type(exc).__name__
        manifest["failure"] = str(exc)[:300]
        raise
    finally:
        stop.set()
        worker.join(timeout=12)
        manifest["sampler_joined"] = not worker.is_alive()
        manifest["utc_end"] = utc()
        manifest["completed_requests"] = sum(r["status"] == "complete" for r in runs)
        write_json(out / "manifest.json", manifest)
        groups = {}
        for label, prefix in [("cold_after_unload", "cold-"), ("repeat", "repeat-"), ("concurrent", "concurrent-")]:
            valid = [r for r in runs if r["id"].startswith(prefix) and r["status"] == "complete"]
            values = [r["client_total_ms"] for r in valid]
            first = [r["first_content_ms"] for r in valid if r["first_content_ms"] is not None]
            groups[label] = {"n": len(values), "client_total_median_ms": statistics.median(values) if values else None,
                "client_total_min_ms": min(values) if values else None, "client_total_max_ms": max(values) if values else None,
                "first_content_median_ms": statistics.median(first) if first else None}
        write_json(out / "summary.json", {"groups": groups, "percentiles": "not reported for small sample",
            "quality": "manual review required", "pass": None})

if __name__ == "__main__":
    main()
