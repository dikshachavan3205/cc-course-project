"""Tiny web server for the ChronoNet demo (stdlib only, Python 3.9-safe).

Serves sample_data/site/index.html + style.css on port 80 (CHRONONET_WEB_PORT).
The site files live in the run's S3 checkpoint folder
(checkpoints/<run_id>/sample_data/site/) so a replacement instance restores
and serves the SAME page. index.html is a template: {{VM_ID}}, {{STEP}} etc.
are filled in on every request from this instance's identity and the
sample_output.log it holds.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(APP_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import boto3  # noqa: E402

from shared.constants import AWS_REGION, S3_CHECKPOINT_BUCKET, S3_CHECKPOINT_PREFIX  # noqa: E402

RUN_ID = os.environ.get("CHRONONET_RUN_ID", "local")
VM_ID = os.environ.get("CHRONONET_VM_ID", "unknown-vm")
SAMPLE_DIR = os.path.join(REPO_ROOT, "sample_data")
SITE_DIR = os.path.join(SAMPLE_DIR, "site")
LOG_FILE = os.path.join(SAMPLE_DIR, "sample_output.log")
DEFAULT_DIR = os.path.join(APP_DIR, "site_default")
FILES = ("index.html", "style.css")
PREFIX = f"{S3_CHECKPOINT_PREFIX}/{RUN_ID}/sample_data/site"


def sync_site() -> None:
    """Restore the site from S3 if the run already has one; else seed + upload defaults."""
    os.makedirs(SITE_DIR, exist_ok=True)
    s3 = boto3.client("s3", region_name=AWS_REGION)
    restored = 0
    for name in FILES:
        try:
            s3.download_file(S3_CHECKPOINT_BUCKET, f"{PREFIX}/{name}", os.path.join(SITE_DIR, name))
            restored += 1
            print(f"[web] restored {name} <- s3://{S3_CHECKPOINT_BUCKET}/{PREFIX}/{name}", flush=True)
        except Exception:  # noqa: BLE001
            pass
    if restored < len(FILES):
        for name in FILES:
            dest = os.path.join(SITE_DIR, name)
            if not os.path.exists(dest):
                shutil.copy(os.path.join(DEFAULT_DIR, name), dest)
            try:
                s3.upload_file(dest, S3_CHECKPOINT_BUCKET, f"{PREFIX}/{name}")
            except Exception as exc:  # noqa: BLE001
                print(f"[web] upload failed {name}: {exc}", flush=True)
        print("[web] no site in S3 for this run - seeded default site and uploaded it", flush=True)


def _log_lines() -> list:
    try:
        with open(LOG_FILE) as f:
            return [l.rstrip("\n") for l in f if l.strip() and not l.startswith("#")]
    except Exception:  # noqa: BLE001
        return []


def render() -> bytes:
    with open(os.path.join(SITE_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read()
    lines = _log_lines()
    last = lines[-1] if lines else "(no sample data yet - first checkpoint pending)"
    m = re.match(r"step=(\d+)", last)
    vals = {
        "VM_ID": VM_ID, "RUN_ID": RUN_ID,
        "INSTANCE_TYPE": os.environ.get("CHRONONET_INSTANCE_TYPE", "?"),
        "MARKET": os.environ.get("CHRONONET_MARKET", "?"),
        "STEP": m.group(1) if m else "-", "LOG_LINES": str(len(lines)),
        "LAST_LINE": last, "NOW": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    for k, v in vals.items():
        html = html.replace("{{" + k + "}}", v)
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body, ctype = render(), "text/html; charset=utf-8"
        elif path == "/style.css":
            with open(os.path.join(SITE_DIR, "style.css"), "rb") as f:
                body, ctype = f.read(), "text/css; charset=utf-8"
        elif path == "/health":
            body, ctype = VM_ID.encode(), "text/plain"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet
        pass


def main() -> None:
    sync_site()
    port = int(os.environ.get("CHRONONET_WEB_PORT", "80"))
    print(f"[web] {VM_ID} serving site on :{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
