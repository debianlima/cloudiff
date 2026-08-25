---
name: cloudiff-authentik-oidc
versao: 1.0.0
tipo: dominio
description: Configure or review CloudIFF identity flows with Authentik OIDC, explicit audiences, short-lived tokens, service
  clients, group-to-role mapping, and defense in depth. Use for portal, MCP, PWA, API, agent, or external client authentication.
origem:
  tipo: aprendizado-preexistente-cloudiff
  release_operacional: cloudiff-project-0.1.1-20260824
  sha256_original: 1f1509c37ee6596832e15f3269784e4acab727d08121a6a985a596ba9b616a81
escopo: autenticação OIDC/AuthentiK, identidade, sessão e autorização CloudIFF
portao: login real; callback válido; sessão válida; wrong-audience/forged-header/cross-tenant rejeitados
---
# CloudIFF Authentik and OIDC
- Use Authorization Code with PKCE for interactive clients and client credentials or signed workload identity for machine clients. Do not use shared user passwords as application credentials.
- Validate issuer, audience, signature, expiration, not-before, nonce/state, redirect URI, and required scopes. Keep access tokens short-lived and rotate client secrets.
- Map immutable subject IDs and trusted groups to CloudIFF roles. Do not trust role, tenant, project, or delegated-user headers from arbitrary network clients.
- At the edge, remove inbound identity headers and set them only after successful Authentik verification. At the application, still require explicit identity for sensitive internal routes.
- Never expose refresh tokens to browser storage or logs. Use secure, HttpOnly, SameSite cookies where sessions are required.
- Separate human clients, MCP clients, service agents, and health checks. Give each a distinct client ID, audience, scope, quota, and audit trail.
- Test missing/expired/wrong-audience token, forged identity headers, role downgrade, cross-tenant access, callback tampering, logout, key rotation, and Authentik outage behavior.
