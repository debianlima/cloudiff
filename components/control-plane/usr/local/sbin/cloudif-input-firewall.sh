#!/usr/bin/env bash
set -euo pipefail
CHAIN=CLOUDIF_INPUT
iptables -N "$CHAIN" 2>/dev/null || true
iptables -F "$CHAIN"
iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
iptables -A "$CHAIN" -i lo -j RETURN
# Portal e APIs: somente NPM e o próprio host.
for SRC in 10.62.91.3/32 10.62.92.7/32; do
  iptables -A "$CHAIN" -p tcp -s "$SRC" -m multiport --dports 18090:18094,18099,8099 -j RETURN
done
iptables -A "$CHAIN" -p tcp -m multiport --dports 18090:18094,18099,8099 -j DROP
# Métricas: Forja/coletor, NPM e host local.
for SRC in 10.62.91.2/32 10.62.91.3/32 10.62.92.7/32; do
  iptables -A "$CHAIN" -p tcp -s "$SRC" --dport 18096 -j RETURN
done
iptables -A "$CHAIN" -p tcp --dport 18096 -j DROP
# Kong, PostgreSQL e Supavisor: somente redes técnicas.
for NET in 10.62.91.0/24 10.62.92.0/24; do
  iptables -A "$CHAIN" -p tcp -s "$NET" -m multiport --dports 8101,8102,8110,54330,54331,54400,65410,65430,65431 -j RETURN
done
iptables -A "$CHAIN" -p tcp -m multiport --dports 8101,8102,8110,54330,54331,54400,65410,65430,65431 -j DROP
iptables -A "$CHAIN" -j RETURN
iptables -C INPUT -j "$CHAIN" 2>/dev/null || iptables -I INPUT 1 -j "$CHAIN"
# Acesso de saída ao DNS/AD 10.68.128.252 permanece permitido; OUTPUT não é filtrado.
