# CloudIFF Remote Access Edge

Control plane: FRP-Panel v0.1.37, pinned to commit `1a58b856d7de19de8669b7072872986d2fa1604a`.
The amd64 release binary is verified with SHA-256 `a64a8dad08f798710b3319b77370d889a81de03ea3773b9f95c65fb0deeba95d` before installation.

Topology:
- `proxy` runs FRP-Panel Master plus its built-in FRP server.
- `runtime` and `control-plane` run FRP-Panel clients with remote shell/functions disabled.
- WAN TCP `24000-24999` is forwarded once to the proxy; FRPS itself permits only this range.
- The Portal owns project ACLs, leases, TTL and user presentation; FRP-Panel is not exposed as the student UI.
- Broker tokens and node secrets live only in root-readable `/etc/cloudif/*.env` files.
- PostgreSQL raw access remains disabled until a TLS gateway is independently verified.

The Portal cleanup timer revokes expired proxies independently of browser activity.
