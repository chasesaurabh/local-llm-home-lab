"""Read-only probe of one synthetic collection/file with one login identity."""
import argparse
import getpass
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

CANARY = "ACCESS014-COPPER-HERON-4827"


def call(base, path, token=None, data=None):
    headers = {"Cache-Control": "no-cache"}
    if token:
        headers["Authorization"] = "Bearer " + token
    raw = None
    if data is not None:
        raw = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = Request(base + path, data=raw, headers=headers)
    try:
        with urlopen(req, timeout=60) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("collection_id", type=uuid.UUID)
    parser.add_argument("output")
    parser.add_argument("--file-id", type=uuid.UUID)
    parser.add_argument("--port", type=int, choices=[3103, 3106], default=3103)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise SystemExit("Preserve the prior result; choose a new filename")
    base = "http://127.0.0.1:" + str(args.port)
    status, raw = call(base, "/api/v1/auths/signin", data={
        "email": input("Synthetic account email: "),
        "password": getpass.getpass("Password (not saved): "),
    })
    if status != 200:
        raise SystemExit("Sign-in failed: HTTP " + str(status))
    token = json.loads(raw)["token"]
    del raw
    cid = str(args.collection_id)
    if args.file_id:
        fid = str(args.file_id)
    else:
        code, content = call(base, "/api/v1/knowledge/" + cid + "/files",
                             token=token)
        if code != 200:
            raise SystemExit("Owner must record the file ID first")
        matches = [item for item in json.loads(content).get("items", [])
                   if item.get("filename") == "permission-note.md"]
        if len(matches) != 1:
            raise SystemExit("Expected one permission-note.md in the test collection")
        fid = matches[0]["id"]
        print("Use this exact file ID for all later probes:", fid)
    routes = [
        ("metadata", "/api/v1/knowledge/" + cid, None),
        ("retrieval", "/api/v1/retrieval/query/collection", {
            "collection_names": [cid], "query": "access-test sentinel", "k": 3,
        }),
        ("file", "/api/v1/files/" + fid + "/content", None),
    ]
    results = []
    for label, route, body in routes:
        code, content = call(base, route, token=token, data=body)
        text = content.decode("utf-8", errors="replace")
        result = {"route": label, "status": code,
                  "canary_present": CANARY in text,
                  "sha256": hashlib.sha256(content).hexdigest()}
        if label == "retrieval" and code == 200:
            result["documents"] = json.loads(text).get("documents")
        results.append(result)
        print(label, code, "canary present:", result["canary_present"])
    del token
    output.write_text(json.dumps({"collection_id": cid, "file_id": fid,
                                  "results": results}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
