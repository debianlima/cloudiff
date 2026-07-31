#!/usr/bin/env python3
import sys
from pathlib import Path

env_file = Path(sys.argv[1])
pairs = sys.argv[2:]

data = {}
order = []

if env_file.exists():
    for line in env_file.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            order.append((None, line))
            continue
        k, v = line.split("=", 1)
        if k not in data:
            order.append((k, None))
        data[k] = v

for p in pairs:
    k, v = p.split("=", 1)
    if k not in data:
        order.append((k, None))
    data[k] = v

out = []
seen = set()
for k, raw in order:
    if k is None:
        out.append(raw)
    elif k not in seen:
        out.append(f"{k}={data[k]}")
        seen.add(k)

for k, v in data.items():
    if k not in seen:
        out.append(f"{k}={v}")

env_file.write_text("\n".join(out).rstrip() + "\n")
