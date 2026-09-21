import json, subprocess, time, sys, os, base64
import urllib.request
import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9334
PROFILE = os.path.join(os.environ.get("TEMP", "."), "judge_chrome_profile3")

def start_chrome():
    os.makedirs(PROFILE, exist_ok=True)
    args = [CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
            "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            "--remote-allow-origins=*",
            "--window-size=1536,1024"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def wait_for_devtools(timeout=15):
    for _ in range(timeout*4):
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
            return json.loads(r.read())
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("chrome devtools not up")

def new_tab(url):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{url}", method="PUT")
    r = urllib.request.urlopen(req, timeout=5)
    return json.loads(r.read())

class Tab:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=20)
        self.id = 0
    def send(self, method, params=None):
        self.id += 1
        mid = self.id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                return msg
    def wait_event(self, method, timeout=10):
        self.ws.settimeout(timeout)
        t0 = time.time()
        while time.time()-t0 < timeout:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get("method") == method:
                return msg

if __name__ == "__main__":
    action = sys.argv[1]
    if action == "start":
        p = start_chrome()
        info = wait_for_devtools()
        print("started", info.get("Browser"))
    elif action == "shot":
        url = sys.argv[2]
        outpath = sys.argv[3]
        w = int(sys.argv[4]) if len(sys.argv) > 4 else 1536
        h = int(sys.argv[5]) if len(sys.argv) > 5 else 1024
        wait_s = float(sys.argv[6]) if len(sys.argv) > 6 else 2.0
        tabinfo = new_tab("about:blank")
        tab = Tab(tabinfo["webSocketDebuggerUrl"])
        tab.send("Page.enable")
        tab.send("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False})
        tab.send("Page.navigate", {"url": url})
        tab.wait_event("Page.loadEventFired", timeout=20)
        time.sleep(wait_s)
        res = tab.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        data = res["result"]["data"]
        with open(outpath, "wb") as f:
            f.write(base64.b64decode(data))
        print("saved", outpath)
    elif action == "eval":
        # eval.py <ws_target_id_or_url> not used; instead pass a persistent tab: use 'evalnav'
        pass
