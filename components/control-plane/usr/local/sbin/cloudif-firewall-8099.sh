#!/usr/bin/env bash
set -euo pipefail

NPM_IP="10.62.91.3"
PORT="8099"

while iptables -S INPUT | grep -q -- "--dport $PORT"; do
  RULE="$(iptables -S INPUT | grep -- "--dport $PORT" | head -1 | sed 's/^-A /-D /')"
  iptables $RULE || break
done

iptables -I INPUT 1 -p tcp -s "$NPM_IP" --dport "$PORT" -j ACCEPT
iptables -I INPUT 2 -p tcp -s 127.0.0.1/32 --dport "$PORT" -j ACCEPT
iptables -I INPUT 3 -p tcp -i lo --dport "$PORT" -j ACCEPT
iptables -I INPUT 4 -p tcp --dport "$PORT" -j DROP
