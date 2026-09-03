"""Fetch QC backtest runtime stats + chart series přes read API (Free-tier safe)."""
import hashlib, time, base64, json, urllib.request, urllib.error

USER_ID = "515881"
API_TOKEN = "8e5780f1aa15183cd4b17f07a08a58a8c0baa185a10432f6e674ebfe7c5e2f3a"
BASE = "https://www.quantconnect.com/api/v2"

def call(ep, payload=None):
    ts = str(int(time.time()))
    h = hashlib.sha256(f"{API_TOKEN}:{ts}".encode()).hexdigest()
    auth = base64.b64encode(f"{USER_ID}:{h}".encode()).decode()
    data = json.dumps(payload).encode() if payload is not None else b"{}"
    req = urllib.request.Request(f"{BASE}/{ep}", data=data, method="POST")
    for k, v in {"Authorization": f"Basic {auth}", "Timestamp": ts,
                 "Content-Type": "application/json"}.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, e.read().decode()

def project_id(name):
    _, r = call("projects/read")
    for p in r.get("projects", []):
        if p.get("name") == name:
            return p["projectId"]
    return None

def latest_backtest(pid):
    _, r = call("backtests/list", {"projectId": pid})
    bts = r.get("backtests", [])
    if not bts:
        return None
    return sorted(bts, key=lambda x: x.get("created", 0))[-1]

def runtime_stats(pid, bid):
    _, r = call("backtests/read", {"projectId": pid, "backtestId": bid})
    return r.get("backtest", {}).get("runtimeStatistics", {})

def chart_series(pid, bid, chart_name):
    """vrací dict series_name -> {timestamp:int -> value:float}"""
    _, r = call("backtests/chart/read", {"projectId": pid, "backtestId": bid, "name": chart_name})
    chart = r.get("chart") or {}
    series = chart.get("series") or chart.get("Series") or {}
    out = {}
    for sn, sv in series.items():
        vals = sv.get("values") or sv.get("Values") or []
        d = {}
        for pt in vals:
            if isinstance(pt, dict):
                x, y = pt.get("x"), pt.get("y")
            else:
                x, y = pt[0], pt[1]
            if x is not None and y is not None:
                d[int(x)] = float(y)
        out[sn] = d
    return out
