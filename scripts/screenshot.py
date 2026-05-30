#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""
Capture Retnza dashboard screenshots via Chrome DevTools Protocol.
Handles Next.js SPA lifecycle properly.
"""

import json, time, subprocess, tempfile, base64, sys, os, re
from pathlib import Path
import urllib.request
import websocket

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = "http://localhost:3000"
API = "http://localhost:8000/api/v1"
OUT = Path(__file__).resolve().parent.parent / "screenshots"
AUTH = ("admin@retnza.local", "admin123")

PAGES = [
    ("dashboard",      "/dashboard",        "Executive Dashboard Overview"),
    ("queue",          "/queue",             "CRM Action Queue"),
    ("subscriber",     "/subscribers/1",     "Subscriber Detail View"),
    ("campaigns",      "/campaigns",         "Campaign Playbook"),
    ("ecosystem",      "/ecosystem",         "Ecosystem Analytics"),
    ("health",         "/health",            "Model Health Dashboard"),
    ("model",          "/model",             "Model Monitoring"),
    ("behavioral",     "/behavioral-segments", "Behavioral Segmentation"),
    ("evidence",       "/evidence",           "Evidence & Insights"),
]


def login():
    data = json.dumps({"email": AUTH[0], "password": AUTH[1]}).encode()
    req = urllib.request.Request(f"{API}/auth/login", data=data,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["access_token"]


class CDP:
    def __init__(self):
        self.ws = None
        self._id = 0

    def start_chrome(self, port=9222):
        self.user_dir = tempfile.mkdtemp(prefix="retnza-")
        self.proc = subprocess.Popen([
            CHROME, f"--remote-debugging-port={port}",
            "--remote-allow-origins=*", f"--user-data-dir={self.user_dir}",
            "--no-first-run", "--no-default-browser-check",
            "--window-size=1920,1080",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        self.port = port

    def connect(self):
        resp = urllib.request.urlopen(f"http://localhost:{self.port}/json")
        targets = json.loads(resp.read())
        url = targets[0]["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(url, timeout=60)
        self.ws.settimeout(0.5)  # Non-blocking recv

    def cmd(self, method, params=None):
        """Send CDP command and wait for matching response."""
        self._id += 1
        payload = json.dumps({"id": self._id, "method": method, "params": params or {}})
        self.ws.send(payload)
        # Drain events until we get our response
        while True:
            try:
                msg = json.loads(self.ws.recv())
                if msg.get("id") == self._id:
                    return msg.get("result")
            except websocket.WebSocketTimeoutException:
                continue
            except (json.JSONDecodeError, websocket.WebSocketException):
                continue
            except Exception:
                continue

    def _drain_events(self, timeout=2):
        """Drain any pending events."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                self.ws.recv()
            except:
                return

    def goto(self, url):
        """Navigate and wait for SPA to render."""
        self.cmd("Page.enable")
        self.cmd("Page.navigate", {"url": url})
        # Wait for page to render
        time.sleep(5)
        # Wait for readyState == complete
        for _ in range(30):
            try:
                r = self.cmd("Runtime.evaluate", {
                    "expression": "document.readyState === 'complete'",
                    "returnByValue": True,
                })
                if r and r.get("result", {}).get("value"):
                    break
            except:
                pass
            time.sleep(1)
        time.sleep(3)  # Extra wait for data fetches

    def set_token(self, token):
        """Set auth token in localStorage."""
        self.goto(f"{BASE}/login")
        self.cmd("Runtime.evaluate", {
            "expression": f'localStorage.setItem("retnza_token", "{token}")',
        })
        self.cmd("Runtime.evaluate", {
            "expression": 'localStorage.setItem("retnza_locale", "en")',
        })

    def capture(self, path):
        """Take screenshot and save to path."""
        r = self.cmd("Page.captureScreenshot", {"format": "png"})
        if r and "data" in r:
            with open(path, "wb") as f:
                f.write(base64.b64decode(r["data"]))
            return True
        return False

    def close(self):
        try:
            if self.ws: self.ws.close()
        except: pass
        try:
            self.proc.terminate()
            self.proc.wait()
        except: pass


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.png"): f.unlink()

    token = login()
    print(f"✓ Token: {token[:24]}...")

    cd = CDP()
    cd.start_chrome()
    print("✓ Chrome launched")

    try:
        cd.connect()
        print("✓ CDP connected")

        cd.set_token(token)
        print("✓ Auth configured")

        results = []
        for name, path, caption in PAGES:
            url = f"{BASE}{path}"
            print(f"\n--- {name} ---")
            cd.goto(url)
            fp = OUT / f"{name}.png"
            if cd.capture(fp):
                kb = fp.stat().st_size // 1024
                print(f"  ✓ ({kb} KB)")
                results.append({"file": f"{name}.png", "caption": caption})
            else:
                print(f"  ✗ Failed")
            time.sleep(1)

        # Save manifest
        meta = {"count": len(results), "screenshots": results}
        with open(OUT / "manifest.json", "w") as f:
            json.dump(meta, f, indent=2)

        print(f"\n✓ Done: {len(results)}/{len(PAGES)}")
        for r in results:
            print(f"  - {r['file']}: {r['caption']}")

    finally:
        cd.close()
        print("✓ Chrome closed")


if __name__ == "__main__":
    main()
