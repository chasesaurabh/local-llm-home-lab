"""Generate synthetic PNGs or submit one bounded local vision request."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import zlib

ROOT = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="backslashreplace")
MODEL = "qwen3-vl:2b"
WIDTH, HEIGHT = 640, 360
GLYPHS = {
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
}


def png(label):
    pixels = bytearray([255] * WIDTH * HEIGHT * 3)

    def point(x, y, rgb):
        i = (y * WIDTH + x) * 3
        pixels[i:i + 3] = bytes(rgb)

    for y in range(100, 250):
        for x in range(70, 220):
            point(x, y, (200, 30, 30))
    for y in range(100, 251):
        for x in range(360, 511):
            if (x - 435) ** 2 + (y - 175) ** 2 <= 75 ** 2:
                point(x, y, (30, 80, 200))
    for pos, char in enumerate(label):
        for row, bits in enumerate(GLYPHS[char]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    for dy in range(8):
                        for dx in range(8):
                            point(190 + pos * 48 + col * 8 + dx,
                                  20 + row * 8 + dy, (0, 0, 0))

    def chunk(kind, data):
        crc = zlib.crc32(kind + data) & 0xffffffff
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    rows = b"".join(
        b"\0" + pixels[y * WIDTH * 3:(y + 1) * WIDTH * 3]
        for y in range(HEIGHT)
    )
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def fixtures():
    records = []
    for name, label in [("clear.png", "BOX42"), ("partial.png", "BOX")]:
        path = ROOT / name
        if path.exists():
            raise SystemExit("Preserve existing fixtures before regenerating")
        data = png(label)
        path.write_bytes(data)
        records.append({"file": name, "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data), "width": WIDTH, "height": HEIGHT})
    (ROOT / "fixtures.json").write_text(json.dumps(records, indent=2), "utf-8")
    print(json.dumps(records, indent=2))


def ask(image_name, case, output):
    prompts = {
        "visible": "Describe the visible shapes, their colors and left/right "
                   "positions. Read the exact visible label. Do not guess.",
        "absent": "What is the object's manufacturer serial number? "
                  "If no manufacturer serial number is shown, say not visible. "
                  "Do not treat a generic label as a manufacturer serial number.",
        "partial": "Read only the visible label. Are any additional suffix "
                   "characters visible? Do not infer missing text.",
    }
    if image_name not in {"clear.png", "partial.png"}:
        raise SystemExit("Use a generated fixture filename")
    path = ROOT / image_name
    image = base64.b64encode(path.read_bytes()).decode()
    body = {
        "model": MODEL, "stream": False, "think": False,
        "messages": [{"role": "user", "content": prompts[case],
                      "images": [image]}],
        "options": {"temperature": 0, "seed": 7,
                    "num_ctx": 4096, "num_predict": 256},
        "keep_alive": "2m",
    }
    target = Path(output)
    if target.exists():
        raise SystemExit("Preserve the previous result")
    req = Request("http://127.0.0.1:11434/api/chat",
                  data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urlopen(req, timeout=120) as response:
            result = json.load(response)
    except (HTTPError, URLError) as exc:
        result = {"error": str(exc)}
        if isinstance(exc, HTTPError):
            result.update(status=exc.code,
                          body=exc.read().decode(errors="replace"))
    record = {"request": body, "response": result,
              "elapsed_seconds": time.monotonic() - start,
              "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    target.write_text(json.dumps(record, indent=2), "utf-8")
    if "error" in result:
        raise SystemExit("Request failed; inspect " + str(target))
    print(result["message"]["content"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["fixtures", "ask"])
    parser.add_argument("--image", default="clear.png")
    parser.add_argument("--case", choices=["visible", "absent", "partial"],
                        default="visible")
    parser.add_argument("--output", default="vision-result.json")
    args = parser.parse_args()
    if args.operation == "fixtures":
        fixtures()
    else:
        ask(args.image, args.case, args.output)
