#!/usr/bin/env python3
import json, os, socket, subprocess, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("CLOUDIF_METRICS_HOST", "0.0.0.0")
PORT = int(os.environ.get("CLOUDIF_METRICS_PORT", "18096"))

def run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return {"rc": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    except Exception as e:
        return {"rc": 999, "stdout": "", "stderr": str(e)}

def network_summary():
    """Return cumulative counters for physical/upstream interfaces only."""
    base = "/sys/class/net"
    ignored_prefixes = ("lo", "docker", "br-", "veth", "virbr", "tun", "tap")
    interfaces = []
    rx_total = tx_total = 0
    try:
        for name in sorted(os.listdir(base)):
            if name == "lo" or name.startswith(ignored_prefixes[1:]):
                continue
            path = os.path.join(base, name)
            try:
                with open(os.path.join(path, "operstate"), encoding="utf-8") as stream:
                    state = stream.read().strip()
                if state not in {"up", "unknown"}:
                    continue
                with open(os.path.join(path, "statistics", "rx_bytes"), encoding="utf-8") as stream:
                    rx = int(stream.read().strip())
                with open(os.path.join(path, "statistics", "tx_bytes"), encoding="utf-8") as stream:
                    tx = int(stream.read().strip())
            except (OSError, ValueError):
                continue
            interfaces.append({"name": name, "rx_bytes": rx, "tx_bytes": tx})
            rx_total += rx
            tx_total += tx
    except OSError:
        pass
    return {"rx_bytes": rx_total, "tx_bytes": tx_total, "interfaces": interfaces}

def docker_summary():
    if run(["bash", "-lc", "command -v docker"]).get("rc") != 0:
        return {"available": False, "containers": []}

    out = run(["bash", "-lc", "docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}'"], 10)
    containers = []
    for line in out["stdout"].splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            containers.append({"name": parts[0], "image": parts[1], "status": parts[2]})
    return {"available": True, "count": len(containers), "containers": containers[:200]}

def metrics():
    mem = run(["bash", "-lc", "free -b | awk 'NR==2{print $2,$3,$4,$6,$7}'"])
    disk = run(["bash", "-lc", "df -B1 --output=source,fstype,size,used,avail,pcent,target / | tail -n +2"])
    load = run(["bash", "-lc", "cat /proc/loadavg"])
    uptime = run(["bash", "-lc", "cat /proc/uptime"])
    ips = run(["bash", "-lc", "ip -br addr | sed -n '1,40p'"])
    docker = docker_summary()
    network = network_summary()

    mem_data = {}
    if mem["stdout"]:
        vals = mem["stdout"].split()
        if len(vals) >= 5:
            mem_data = {
                "total": int(vals[0]),
                "used": int(vals[1]),
                "free": int(vals[2]),
                "buff_cache": int(vals[3]),
                "available": int(vals[4]),
            }

    disk_data = {}
    if disk["stdout"]:
        vals = disk["stdout"].split()
        if len(vals) >= 7:
            disk_data = {
                "source": vals[0],
                "fstype": vals[1],
                "size": int(vals[2]),
                "used": int(vals[3]),
                "avail": int(vals[4]),
                "pcent": vals[5],
                "target": vals[6],
            }

    return {
        "ok": True,
        "host": socket.gethostname(),
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "memory": mem_data,
        "disk_root": disk_data,
        "loadavg": load["stdout"],
        "uptime": uptime["stdout"],
        "ips": ips["stdout"],
        "network": network,
        "docker": docker,
    }

class H(BaseHTTPRequestHandler):
    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ["/", "/health"]:
            return self.send_json(200, {"ok": True, "service": "cloudif-node-metrics", "host": socket.gethostname()})
        if self.path.startswith("/metrics"):
            return self.send_json(200, metrics())
        return self.send_json(404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt, *args):
        print(time.strftime("[%Y-%m-%dT%H:%M:%S]"), self.client_address[0], fmt % args, flush=True)

if __name__ == "__main__":
    print(f"CloudIF node metrics listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
