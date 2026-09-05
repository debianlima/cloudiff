# CloudIFF Remote Access — 443-only relay

The global WAN contract is strict: only TCP/80 and TCP/443 are public. **Remote access itself uses only TCP/443**. No PostgreSQL, Forgejo SSH, FRP port range, preview runtime port, tenant port, or administrative SSH/22 is published in the WAN firewall.

Data path:

1. pfSense keeps its existing WAN `443 -> proxy:443` rule.
2. `cloudif-443-relay.service` (`sslh`) distinguishes TLS/HTTPS from the SSH banner.
3. TLS goes to Nginx Proxy Manager on loopback `127.0.0.1:10443`.
4. SSH goes to the dedicated CloudIFF gateway on loopback `127.0.0.1:10022`.
5. The SSH gateway accepts only one-time project lease keys issued by the Authentik-protected Portal.
6. `permitopen=` options returned by the Portal restrict each key to the internal targets of that project.
7. A 30-second reaper terminates gateway sessions whose lease expired or was released.
8. For Hospedagem-only targets, a machine connector opens an outbound SSH connection on the same public 443 and creates loopback-only `RemoteForward` listeners only while an active lease needs them.

The gateway account is a temporary pool identity (`cifremote001..256`), not the human identity.
The browser-authenticated human identity remains in the Portal lease/audit record. A one-time Ed25519
private key is delivered only in the authenticated activation response and is never stored server-side.

Current tunneled targets:
- Forgejo SSH: internal `10.62.91.2:2222`, with normal Forgejo SSH key authentication downstream.
- PostgreSQL/Supabase: the project's tenant-specific `POSTGRES_PORT` on `10.62.92.7`; the public leg is encrypted by SSH.

Web/MCP/Studio/Komodo/Preview/Homologation/Production keep their existing HTTPS endpoints and do not
receive additional public listeners. Faro is not part of this path.
